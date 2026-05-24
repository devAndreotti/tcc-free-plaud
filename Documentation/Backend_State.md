# Estado do Backend (Backend State)

Este documento descreve o estado atual do backend da aplicação.

## Ponto de Entrada: `UI/main.py`

O arquivo `UI/main.py` é o núcleo do backend da aplicação. Ele é responsável por:
1. Iniciar uma janela nativa do Windows utilizando a biblioteca `webview` (PyWebView).
2. Fornecer uma classe `Api` cujos métodos são expostos diretamente ao ambiente JavaScript na variável global `window.pywebview.api`.
3. Carregar o arquivo `index.html` compilado da pasta `dist/` do React.

## Métodos Expostos (Classe `Api`)

A comunicação frontend-backend é feita através dos seguintes métodos implementados na classe `Api`:

- `sendMessage(message, attachment=None)`: Recebe as mensagens de chat e anexos. Atualmente retorna um texto de _mock_ informando que o backend Python está conectado, mas ainda aguarda a implementação real do modelo de IA.
- `selectFolder()`: Abre uma janela nativa do sistema operacional (utilizando `tkinter.filedialog`) para que o usuário selecione o diretório do seu "Vault" (Pasta local com arquivos Markdown).
- `scanVault(folder_path)`: Realiza a varredura (scan) recursiva do diretório selecionado em busca de arquivos `.md`. Retorna uma lista de nós contendo metadados como `id`, `name`, `path`, `size` e a data de modificação (`modified`).
- `saveVaultPath(path)`: Persiste o diretório do Vault no ambiente de configuração local do usuário (`%APPDATA%/Brainiac/config.json`) garantindo que a seleção da pasta permaneça salva nas próximas execuções.
- `loadVaultPath()`: Carrega o caminho do Vault salvo no arquivo `config.json`.

## Estado de Integração da IA
A casca para integrar o banco de dados vetorial, LLM, _embeddings_ e agentes já está preparada em termos arquiteturais, mas o código atual em `main.py` ainda possui implementações _mockadas_ em `sendMessage`, aguardando a finalização dos módulos de _ingestion_ (ingestão) de dados e da Retrieval-Augmented Generation (RAG).
