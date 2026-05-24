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

Para integrar o backend no futuro, implemente os métodos da classe Api.
─────────────────────────────────────────────────────────────────
"""

import os
import sys
import json
import uuid
from datetime import datetime
from pathlib import Path
import webview

# Caminho do arquivo de configuração persistido em appdata
CONFIG_PATH = Path(os.environ.get('APPDATA', Path.home())) / 'Brainiac' / 'config.json'


class Api:
    """
    API exposta ao JavaScript via PyWebView.

    Cada método público desta classe fica disponível no frontend
    como: window.pywebview.api.nomeDoMetodo(args)

    TODO: Integrar com o backend de IA quando estiver pronto.
    """

    def sendMessage(self, message: str, attachment: str = None) -> str:
        """
        Recebe mensagem do usuário enviada pelo frontend React.

        Args:
            message:    Texto digitado pelo usuário.
            attachment: Nome do arquivo anexado (opcional).

        Returns:
            Texto da resposta a ser exibida no chat.
        """
        # TODO: Substituir por chamada real ao backend de IA
        print(f"[Backend] Mensagem recebida: {message!r}")
        if attachment:
            print(f"[Backend] Arquivo anexado: {attachment!r}")

        # Resposta placeholder até o backend ser implementado
        return "Backend Python conectado! A integração com a IA será implementada em breve."

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
