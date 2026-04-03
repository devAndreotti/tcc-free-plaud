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
import webview


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
        title='Assistente IA',
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
