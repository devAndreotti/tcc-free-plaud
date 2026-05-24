# Estado do Frontend (Frontend State)

Este documento detalha o estado atual dos elementos do frontend da aplicação.

## Pilha Tecnológica (Tech Stack)
- **Framework**: React 18+ com TypeScript.
- **Build Tool**: Vite.
- **Estilização**: CSS Modules / Vanilla CSS (conforme especificado em `App.css` e `.css` globais).

## Visão Geral (App.tsx)
O componente principal (`App.tsx`) rege o layout em duas seções fundamentais:
1. Uma **Barra Lateral (Sidebar)** à esquerda para navegação.
2. Uma **Área de Conteúdo Principal** que pode alternar entre duas _views_ (`AppView`):
   - `chat`: Tela principal com bolhas de mensagem (`MessageBubble`), área de input de usuário (`ChatInput`) e tela de boas vindas caso não existam mensagens.
   - `graph`: A interface "Grafos" (`GraphView`), que lida com a renderização visual das conexões e pastas do Vault selecionado.

## Principais Componentes e Contextos (`UI/src/`)

### Componentes Visuais (`components/`)
- **`Sidebar.tsx` & `HamburgerMenu.tsx`**: Menus de navegação recém migrados para uma arquitetura vertical, permitindo alternar visualmente as seções e abrir configurações.
- **`Header.tsx`**: Barra de cabeçalho superior que gerencia botões para alternar as views (Chat vs Grafo) e acessar o painel de configurações.
- **`MessageBubble.tsx` & `ChatInput.tsx`**: Conjunto de renderização e envio de mensagens e arquivos no fluxo do chat.
- **`SettingsModal.tsx`**: Painel modal que permite acessar e configurar os caminhos do Vault.
- **`GraphView.tsx`**: Renderiza os arquivos Markdown carregados como nós. Em progresso para visualizar metadados.

### Contextos (`contexts/`)
- **`VaultContext.tsx`**: Estado global em React Context que mantem em memória as informações do repositório `.md` atual, incluindo o caminho do _Vault_ e os arquivos cacheados após serem scaneados pela camada Python.

### Comunicação com Backend (`services/bridge.ts`)
A `bridge.ts` é uma camada isomórfica que permite ao frontend operar livremente durante o desenvolvimento. 
- **Modo Desktop (`window.pywebview` presente)**: Repassa todas as chamadas para o Python.
- **Modo Desenvolvimento (Navegador, porta padrão Vite)**: Intercepta e simula requisições com _timers_ de delay (mocks de `scanVault`, mensagens padrão e persistência _fake_), agilizando modificações de UI sem necessidade do PyWebView rodando.

## Estado Atual da Interface
A interface do usuário já possui sua estrutura base (CSS e navegação vertical/sidebar) construída. As funções reativas de enviar/receber mensagem e abrir seleção de pastas estão implementadas na ponte React-Python e o frontend já é capaz de gerenciar múltiplos estados independentes. O componente GraphView está posicionado para receber as atualizações visuais dos grafos.
