"""
main.py — Ponto de entrada do Assistente IA (aplicação desktop)
─────────────────────────────────────────────────────────────────
Usa PyWebView para exibir a interface React em uma janela nativa
do Windows, sem abrir um navegador.

Fluxo de execução:
  1. Python inicia e instancia a classe Api
  2. PyWebView cria uma janela nativa (usa Edge WebView2 internamente)
  3. A janela carrega o build do React (dist/index.html)
  4. O JavaScript acessa funções Python via window.pywebview.api

Integração atual:
  - chat chama o RAG real do corpus já indexado
  - vault selecionado pode ser indexado no corpus local
  - chave de API é salva em pipeline/.env, fora do Git
─────────────────────────────────────────────────────────────────
"""

import os
import sys
import json
import uuid
from datetime import datetime
from pathlib import Path

try:
    import webview
except ImportError:  # Permite importar este módulo em testes sem PyWebView instalado.
    webview = None

REPO_ROOT = Path(__file__).resolve().parents[1]
PIPELINE_SRC = REPO_ROOT / 'pipeline' / 'src'
if PIPELINE_SRC.exists() and str(PIPELINE_SRC) not in sys.path:
    sys.path.insert(0, str(PIPELINE_SRC))

from free_plaud.app.config import get_settings
from free_plaud.app.doctor import run_doctor
from free_plaud.app.local_env import answer_api_key_is_configured, load_local_env, local_env_path_for, save_answer_api_key
from free_plaud.app.settings_catalog import save_catalog_setting, settings_catalog_payload
from free_plaud.app.settings_presets import apply_settings_preset, list_settings_presets, preview_settings_preset
from free_plaud.corpus.runtime import CorpusRuntime
from free_plaud.retrieval.models import AskResponse
from free_plaud.tui.actions import ask_corpus, corpus_status_from_tui, index_corpus_folder

load_local_env()

# Caminho do arquivo de configuração persistido em appdata
CONFIG_PATH = Path(os.environ.get('APPDATA', Path.home())) / 'Brainiac' / 'config.json'


class Api:
    """
    API exposta ao JavaScript via PyWebView.

    Cada método público desta classe fica disponível no frontend
    como: window.pywebview.api.nomeDoMetodo(args)
    """

    def __init__(self) -> None:
        self.runtime = CorpusRuntime()

    def _format_ask_response(self, response: AskResponse) -> str:
        if response.no_answer:
            lines = ['Não encontrei resposta no corpus indexado.']
            if response.reason_for_no_answer:
                lines.extend(['', f'motivo: {response.reason_for_no_answer}'])
            if response.limitations:
                lines.append('')
                lines.extend(f'- {item}' for item in response.limitations)
            lines.append('')
            lines.append(f'latencia_ms: {response.latency_ms}')
            return '\n'.join(lines)

        lines = [response.answer or '']
        if response.citations:
            lines.extend(['', 'Fontes:'])
            for citation in response.citations[:5]:
                source = citation.source_path or citation.note_id
                snippet = citation.snippet.replace('\n', ' ').strip()
                lines.append(f'- {source} | {citation.chunk_id} | {snippet}')
        if response.limitations:
            lines.extend(['', 'Limitações:'])
            lines.extend(f'- {item}' for item in response.limitations)
        lines.extend(['', f'latencia_ms: {response.latency_ms}'])
        return '\n'.join(lines)

    def sendMessage(self, message: str, attachment: str = None) -> str:
        """
        Recebe mensagem do usuário enviada pelo frontend React.

        Args:
            message:    Texto digitado pelo usuário.
            attachment: Nome do arquivo anexado (opcional).

        Returns:
            Texto da resposta a ser exibida no chat.
        """
        print(f"[Backend] Mensagem recebida: {message!r}")
        if attachment:
            print(f"[Backend] Arquivo anexado ignorado no V1: {attachment!r}")

        settings = get_settings()
        response = ask_corpus(message, settings.default_ask_strategy, runtime=self.runtime)
        return self._format_ask_response(response)

    def indexVault(self, folder_path: str) -> dict:
        """
        Indexa recursivamente a pasta selecionada no corpus local.
        """
        result = index_corpus_folder(Path(folder_path).expanduser(), runtime=self.runtime)
        return {
            'ok': result.status in {'success', 'partial'},
            'status': result.status,
            'total_found': result.total_found,
            'indexed_count': result.indexed_count,
            'unchanged_count': result.unchanged_count,
            'failed_count': result.failed_count,
            'skipped_count': result.skipped_count,
        }

    def getBackendSettings(self) -> dict:
        settings = get_settings()
        status = corpus_status_from_tui(settings=settings)
        doctor = run_doctor(settings=settings)
        return {
            'answer_provider': settings.answer_provider,
            'answer_model': settings.answer_model,
            'answer_base_url': settings.answer_base_url,
            'answer_api_key_configured': answer_api_key_is_configured(settings=settings),
            'local_env_path': str(local_env_path_for(settings)),
            'default_ask_strategy': settings.default_ask_strategy,
            'notes_count': status.notes_count,
            'sqlite_chunks_count': status.sqlite_chunks_count,
            'vector_chunks_count': status.vector_chunks_count,
            'settings_catalog': settings_catalog_payload(settings),
            'settings_presets': [preset.model_dump(mode='json') for preset in list_settings_presets()],
            'doctor': doctor.model_dump(mode='json'),
        }

    def getDoctor(self) -> dict:
        return run_doctor().model_dump(mode='json')

    def listSettingsPresets(self) -> list[dict]:
        return [preset.model_dump(mode='json') for preset in list_settings_presets()]

    def previewSettingsPreset(self, name: str) -> dict:
        preview = preview_settings_preset(name)
        return {
            'preset': preview.preset.model_dump(mode='json'),
            'values': preview.values,
            'changes': {key: change.model_dump(mode='json') for key, change in preview.changes.items()},
        }

    def applySettingsPreset(self, name: str) -> dict:
        result = apply_settings_preset(name)
        self.runtime.clear()
        return {
            'ok': True,
            'preset': result.preset.model_dump(mode='json'),
            'values': result.values,
            'changes': {key: change.model_dump(mode='json') for key, change in result.changes.items()},
        }

    def saveApiKey(self, api_key: str) -> dict:
        path = save_answer_api_key(api_key)
        return {
            'ok': True,
            'configured': bool(api_key.strip()),
            'local_env_path': str(path),
        }

    def saveBackendSetting(self, key: str, value) -> dict:
        save_catalog_setting(key, value)
        self.runtime.clear()
        return {'ok': True}

    def selectFolder(self) -> str:
        """
        Abre o seletor nativo de pasta do Windows.

        Returns:
            Caminho absoluto da pasta selecionada, ou '' se o usuário cancelar.
        """
        import tkinter as tk
        from tkinter import filedialog

        # Janela raiz oculta (necessária para o filedialog funcionar)
        root = tk.Tk()
        root.withdraw()
        root.wm_attributes('-topmost', True)  # Garante que o diálogo aparece na frente

        folder = filedialog.askdirectory(title="Selecionar pasta de destino (Vault)")
        root.destroy()

        print(f"[Backend] Vault selecionado: {folder!r}")
        return folder or ''

    def scanVault(self, folder_path: str) -> list:
        """
        Varre a pasta do vault recursivamente em busca de arquivos .md.

        Args:
            folder_path: Caminho absoluto da pasta do vault.

        Returns:
            Lista de dicionários com id, name, path, size e modified de cada .md.
        """
        vault = Path(folder_path)
        if not vault.is_dir():
            print(f"[Backend] Vault inválido: {folder_path!r}")
            return []

        nodes = []
        for md_file in vault.rglob('*.md'):
            try:
                stat = md_file.stat()
                # Caminho relativo ao vault (usa barras normais para consistência)
                relative = md_file.relative_to(vault).as_posix()
                nodes.append({
                    'id': str(uuid.uuid4()),
                    'name': md_file.stem,                           # nome sem .md
                    'path': relative,                              # caminho relativo
                    'size': stat.st_size,                          # bytes
                    'modified': datetime.fromtimestamp(
                        stat.st_mtime
                    ).isoformat(timespec='seconds'),               # ISO 8601
                })
            except (OSError, PermissionError) as exc:
                print(f"[Backend] Ignorando {md_file}: {exc}")

        print(f"[Backend] Vault escaneado: {len(nodes)} arquivo(s) .md encontrado(s)")
        return nodes

    def saveVaultPath(self, path: str) -> bool:
        """
        Persiste o caminho do vault em config.json.

        Args:
            path: Caminho absoluto do vault (string vazia para limpar).

        Returns:
            True em caso de sucesso, False em caso de erro.
        """
        try:
            CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
            data = {}
            if CONFIG_PATH.exists():
                data = json.loads(CONFIG_PATH.read_text(encoding='utf-8'))
            data['vault_path'] = path
            CONFIG_PATH.write_text(
                json.dumps(data, ensure_ascii=False, indent=2),
                encoding='utf-8'
            )
            print(f"[Backend] Vault path salvo: {path!r}")
            return True
        except Exception as exc:
            print(f"[Backend] Erro ao salvar vault path: {exc}")
            return False

    def loadVaultPath(self) -> str:
        """
        Carrega o caminho do vault salvo na sessão anterior.

        Returns:
            Caminho absoluto do vault, ou '' se nunca foi configurado.
        """
        try:
            if CONFIG_PATH.exists():
                data = json.loads(CONFIG_PATH.read_text(encoding='utf-8'))
                return data.get('vault_path', '')
        except Exception as exc:
            print(f"[Backend] Erro ao carregar vault path: {exc}")
        return ''


def get_html_path() -> str:
    """
    Retorna o caminho absoluto para o dist/index.html do React.

    Funciona tanto em desenvolvimento (rodando main.py diretamente)
    quanto no executável compilado pelo PyInstaller.
    """
    if getattr(sys, 'frozen', False):
        # Executando como .exe compilado: arquivos extraídos em sys._MEIPASS
        base_path = sys._MEIPASS
    else:
        # Executando diretamente com Python em desenvolvimento
        base_path = os.path.dirname(os.path.abspath(__file__))

    html_path = os.path.join(base_path, 'dist', 'index.html')

    if not os.path.exists(html_path):
        raise FileNotFoundError(
            f"Build do React não encontrado em: {html_path}\n"
            "Execute 'npm run build' dentro da pasta UI antes de iniciar o app."
        )

    return html_path


if __name__ == '__main__':
    if webview is None:
        print('ERRO: pywebview nao instalado. Execute: pip install -r UI/requirements.txt')
        sys.exit(1)

    api = Api()

    try:
        html_path = get_html_path()
    except FileNotFoundError as e:
        print(f"ERRO: {e}")
        sys.exit(1)

    # Cria a janela nativa do desktop
    window = webview.create_window(
        title='Evil Plaud',
        url=html_path,
        js_api=api,          # Expõe a classe Api ao JavaScript
        width=1100,
        height=700,
        min_size=(800, 600),
        resizable=True,
        text_select=False,   # Desativa seleção de texto como em apps nativos
        confirm_close=False,
    )

    # Inicia o loop de eventos do PyWebView
    # debug=True exibe DevTools (útil durante desenvolvimento)
    webview.start(debug=False)
