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
import threading
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

from escolio.app.config import get_settings
from escolio.app.doctor import run_doctor
from escolio.app.local_env import answer_api_key_is_configured, load_local_env, local_env_path_for, save_answer_api_key
from escolio.app.settings_catalog import save_catalog_setting, save_catalog_settings, settings_catalog_payload
from escolio.app.settings_presets import apply_settings_preset, list_settings_presets, preview_settings_preset
from escolio.benchmark.service import run_benchmark_compare
from escolio.corpus.ask import corpus_vocabulary_stems
from escolio.corpus.dropped import DroppedFileIndexer
from escolio.corpus.jobs import cancel_index_job, get_index_job, start_index_job
from escolio.corpus.runtime import CorpusRuntime
from escolio.notes.service import delete_note, get_note_detail, list_notes, reindex_note
from escolio.providers.answer import test_answer_provider
from escolio.providers.model_discovery import list_answer_models
from escolio.retrieval.models import AskResponse
from escolio.storage.sqlite import init_sqlite
from escolio.tui.actions import ask_corpus, corpus_roots_from_tui, corpus_status_from_tui, index_corpus_folder
from escolio.tui.audio_actions import (
    cancel_audio_capture,
    cancel_voice_model_download,
    get_audio_capture,
    get_voice_model_download,
    list_voice_models,
    start_audio_capture,
    start_voice_model_download,
    stop_audio_capture,
)
from escolio.ingest.watcher_manager import watcher_manager

load_local_env()

# Caminho do arquivo de configuração persistido em appdata
CONFIG_PATH = Path(os.environ.get('APPDATA', Path.home())) / 'Brainiac' / 'config.json'
ASK_STRATEGIES = {'lexical', 'vector', 'hybrid'}


class Api:
    """
    API exposta ao JavaScript via PyWebView.

    Cada método público desta classe fica disponível no frontend
    como: window.pywebview.api.nomeDoMetodo(args)
    """

    def __init__(self) -> None:
        self.runtime = CorpusRuntime()
        self.dropped_files = DroppedFileIndexer(runtime=self.runtime)

    def _warmup(self) -> None:
        """Abre o Chroma, carrega o embedding e o vocabulário do corpus antes da primeira pergunta (~8 s a frio)."""
        try:
            self.runtime.get_vector_store()
            self.runtime.get_embedder().embed(['aquecimento'])
            connection = init_sqlite(get_settings().sqlite_path)
            try:
                corpus_vocabulary_stems(connection)  # vocabulário do filtro de termos ausentes
            finally:
                connection.close()
        except Exception as exc:  # aquecer é otimização: se falhar, a primeira pergunta paga o custo
            print(f'[Backend] Aquecimento falhou: {exc}')

    def _stage_dropped_files(self, event: dict) -> None:
        """Handler Python do drop: só ele recebe o caminho completo (pywebviewFullPath)."""
        files = (event.get('dataTransfer') or {}).get('files') or []
        self.dropped_files.stage([f['pywebviewFullPath'] for f in files if f.get('pywebviewFullPath')])

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

    def askCorpus(self, message: str, strategy: str | None = None, source_root: str | None = None) -> dict:
        """Pergunta ao corpus e devolve a resposta estruturada (afirmações, citações, limitações).

        source_root restringe a busca às notas sob essa pasta indexada; None usa o corpus inteiro.
        """
        settings = get_settings()
        resolved = strategy if strategy in ASK_STRATEGIES else settings.default_ask_strategy
        response = ask_corpus(message, resolved, runtime=self.runtime, source_root=source_root or None)
        payload = response.model_dump(mode='json', exclude={'debug'})
        payload['strategy'] = resolved
        payload['top_k'] = settings.retrieval_top_k
        payload['answer_provider'] = settings.answer_provider
        return payload

    def listCorpusRoots(self) -> list[dict]:
        """Pastas indexadas com notas, para o seletor de pasta do chat."""
        return corpus_roots_from_tui()

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

    def startIndexJob(self, folder_path: str, rebuild: bool = False) -> dict:
        snapshot = start_index_job(Path(folder_path).expanduser(), rebuild=rebuild, runtime=self.runtime)
        return snapshot.model_dump(mode='json')

    def getIndexJob(self, job_id: str) -> dict:
        return get_index_job(job_id).model_dump(mode='json')

    def cancelIndexJob(self, job_id: str) -> dict:
        return cancel_index_job(job_id).model_dump(mode='json')

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

    def testAnswerProvider(self) -> dict:
        return test_answer_provider().model_dump(mode='json')

    def listAnswerModels(self) -> dict:  # NOSONAR - contrato publico do PyWebView consumido pelo front.
        return list_answer_models().model_dump(mode='json')

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

    def saveBackendSettings(self, values: dict) -> dict:
        save_catalog_settings(values)
        self.runtime.clear()
        return self.getBackendSettings()

    def listNotes(self) -> list[dict]:
        return [note.model_dump(mode='json') for note in list_notes()]

    def getNoteDetail(self, note_id: str) -> dict:
        return get_note_detail(note_id).model_dump(mode='json')

    def deleteNote(self, note_id: str, confirmation: str = '') -> dict:
        if confirmation != 'APAGAR':
            return {
                'ok': False,
                'status': 'confirmation_required',
                'message': 'Digite APAGAR para confirmar.',
            }
        result = delete_note(note_id, vector_store=self.runtime.get_vector_store())
        return result.model_dump(mode='json')

    def reindexNote(self, note_id: str) -> dict:
        result = reindex_note(note_id, runtime=self.runtime)
        return result.model_dump(mode='json')

    def runBenchmarkCompare(self, suite_path: str) -> dict:
        return run_benchmark_compare(Path(suite_path), runtime=self.runtime)

    def _native_dialog(self, dialog_type, **kwargs) -> str:
        """
        Abre um dialogo nativo do proprio PyWebView (janela ja existente).

        Usa `webview.windows[0].create_file_dialog` em vez de um `tkinter.Tk()`
        paralelo: o Tkinter roda sua propria mainloop, que disputa a thread de
        UI com o WebView2 e, dependendo do Tcl/Tk instalado, o seletor de pasta
        (`askdirectory`) cai num fallback generico que lista arquivos junto das
        pastas — o que aparentava "selecionar arquivo" em vez de pasta.

        Returns:
            Caminho escolhido, ou '' se o dialogo foi cancelado/indisponivel.
        """
        if webview is None or not webview.windows:
            return ''
        result = webview.windows[0].create_file_dialog(dialog_type, **kwargs)
        return result[0] if result else ''

    def selectBenchmarkSuite(self) -> str:
        if webview is None:
            return ''
        return self._native_dialog(
            webview.OPEN_DIALOG,
            file_types=('Arquivos JSON (*.json)', 'Todos os arquivos (*.*)'),
        )

    def selectFolder(self) -> str:
        """
        Abre o seletor nativo de pasta do Windows.

        Returns:
            Caminho absoluto da pasta selecionada, ou '' se o usuário cancelar.
        """
        if webview is None:
            return ''
        folder = self._native_dialog(webview.FOLDER_DIALOG)
        print(f"[Backend] Vault selecionado: {folder!r}")
        return folder

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

    def startWatcher(self, folder_path: str) -> dict:
        """Inicia monitoramento continuo da pasta para auto-ingestao de novos arquivos."""
        return watcher_manager.start(folder_path, self.dropped_files)

    def stopWatcher(self) -> dict:
        """Para o monitoramento continuo ativo, se houver."""
        return watcher_manager.stop()

    def getWatcherStatus(self) -> dict:
        """Retorna se ha monitoramento ativo e qual diretorio esta sendo observado."""
        return watcher_manager.status()

    def indexDroppedFiles(self, names: list[str]) -> dict:
        """Indexa no corpus os arquivos soltos na área de soltar, identificados pelo nome."""
        return self.dropped_files.enqueue(list(names)).model_dump(mode='json')

    def pollDroppedFiles(self) -> list:
        """Drena os resultados da indexação de arquivos soltos."""
        return [event.model_dump(mode='json') for event in self.dropped_files.poll_events()]

    def startAudioCapture(self) -> dict:
        """Inicia gravacao do microfone padrao do sistema e devolve o job_id."""
        return start_audio_capture().model_dump(mode='json')

    def getAudioCapture(self, job_id: str) -> dict:
        """Consulta status/resultado de um job de gravacao+transcricao."""
        return get_audio_capture(job_id).model_dump(mode='json')

    def stopAudioCapture(self, job_id: str) -> dict:
        """Encerra a gravacao e enfileira a transcricao local."""
        return stop_audio_capture(job_id).model_dump(mode='json')

    def cancelAudioCapture(self, job_id: str) -> dict:
        """Cancela gravacao ou transcricao em andamento."""
        return cancel_audio_capture(job_id).model_dump(mode='json')

    def listVoiceModels(self) -> list[dict]:
        """Lista os modelos de voz do catalogo com metadados de UI e estado instalado."""
        return list_voice_models()

    def startVoiceModelDownload(self, model_id: str) -> dict:
        """Inicia o download em background de um modelo de voz e devolve o job_id."""
        return start_voice_model_download(model_id).model_dump(mode='json')

    def getVoiceModelDownload(self, job_id: str) -> dict:
        """Consulta progresso/status de um job de download de modelo de voz."""
        return get_voice_model_download(job_id).model_dump(mode='json')

    def cancelVoiceModelDownload(self, job_id: str) -> dict:
        """Cancela um download de modelo de voz em andamento."""
        return cancel_voice_model_download(job_id).model_dump(mode='json')

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
        title='Escólio',
        url=html_path,
        js_api=api,          # Expõe a classe Api ao JavaScript
        width=1100,
        height=700,
        min_size=(800, 600),
        resizable=True,
        text_select=False,   # Desativa seleção de texto como em apps nativos
        confirm_close=False,
    )

    # Drop de arquivos: o pywebview só expõe o caminho completo a um handler Python.
    from webview.dom import DOMEventHandler

    def _bind_drop() -> None:
        window.dom.document.events.drop += DOMEventHandler(api._stage_dropped_files, prevent_default=True)

    window.events.loaded += _bind_drop
    threading.Thread(target=api._warmup, name='warmup', daemon=True).start()

    # Inicia o loop de eventos do PyWebView
    # debug=True exibe DevTools (útil durante desenvolvimento)
    webview.start(debug=False)
