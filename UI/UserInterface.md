# Assistente IA — Interface Desktop

Interface visual de chat com IA, construída em **React + TypeScript** e empacotada como aplicação desktop Windows via **PyWebView**. No modo desktop, o chat chama o backend Python real do corpus; no navegador de desenvolvimento, mantém mock local.

---

## Sumário

1. [Visão Geral](#1-visão-geral)
2. [Pré-requisitos](#2-pré-requisitos)
3. [Estrutura do Projeto](#3-estrutura-do-projeto)
4. [Modos de Execução](#4-modos-de-execução)
   - [Desenvolvimento (browser)](#41-desenvolvimento-browser)
   - [Desktop com Python](#42-desktop-com-python)
   - [Executável compilado (.exe)](#43-executável-compilado-exe)
5. [Arquitetura](#5-arquitetura)
   - [Componentes React](#51-componentes-react)
   - [Serviço Bridge](#52-serviço-bridge)
   - [Ponto de Entrada Python](#53-ponto-de-entrada-python)
6. [Como Integrar o Backend Python](#6-como-integrar-o-backend-python)
7. [Design System](#7-design-system)
8. [Referência de Scripts](#8-referência-de-scripts)

---

## 1. Visão Geral

O projeto é dividido em duas partes que se comunicam:

```
┌──────────────────────────────────────────┐
│  Interface (React + TypeScript)          │
│  ─ Renderizada dentro de uma janela      │
│    nativa Windows (sem abrir browser)    │
│  ─ Envia mensagens ao Python via bridge  │
└──────────────┬───────────────────────────┘
               │  window.pywebview.api
               ▼
┌──────────────────────────────────────────┐
│  Backend (Python)                        │
│  ─ Gerenciado por PyWebView              │
│  ─ Expõe métodos à interface via Api     │
│  ─ Integração com IA: a implementar      │
└──────────────────────────────────────────┘
```

Em **desenvolvimento**, o frontend roda em `http://localhost:5173` com hot reload. O backend Python não é necessário — respostas mock são usadas automaticamente.

Em **produção**, o Python executa `main.py`, que abre uma janela nativa carregando o build do React (`dist/index.html`).

---

## 2. Pré-requisitos

### Para desenvolvimento da interface:
| Ferramenta | Versão mínima | Como obter |
|---|---|---|
| Node.js | 18+ | https://nodejs.org |
| npm | 9+ | Incluído com Node.js |

### Para rodar como app desktop:
| Ferramenta | Versão mínima | Como obter |
|---|---|---|
| Python | 3.10+ | https://python.org |
| Microsoft Edge WebView2 | qualquer | Já instalado no Windows 10/11 |

### Para gerar o `.exe`:
| Ferramenta | Como instalar |
|---|---|
| PyInstaller | `pip install pyinstaller` |

---

## 3. Estrutura do Projeto

```
UI/
│
├── main.py                   # Ponto de entrada Python (PyWebView)
├── requirements.txt          # Dependências Python
├── assistente_ia.spec        # Configuração do PyInstaller
├── build_app.bat             # Script de build completo (React + .exe)
├── vite.config.ts            # Configuração do Vite (base: './' obrigatório)
├── index.html                # HTML raiz (lang="pt-BR", meta description)
│
├── dist/                     # Build do React (gerado por npm run build)
│   ├── index.html
│   └── assets/
│
└── src/
    ├── main.tsx              # Entry point do React
    ├── App.tsx               # Componente raiz + lógica de estado do chat
    ├── App.css               # Estilos de todos os componentes
    ├── index.css             # Design tokens, reset global, animações
    │
    ├── services/
    │   └── bridge.ts         # Camada de comunicação React ↔ Python
    │
    └── components/
        ├── Icons.tsx         # Ícones SVG como componentes React
        ├── Header.tsx        # Cabeçalho: logo + botão Grafo
        ├── WelcomeScreen.tsx # Tela inicial (sem mensagens)
        ├── MessageBubble.tsx # Bolhas de mensagem + indicador de digitação
        └── ChatInput.tsx     # Campo de texto, anexo de arquivo, microfone
```

---

## 4. Modos de Execução

### 4.1 Desenvolvimento (browser)

Ideal para trabalhar na interface sem precisar do Python.
Respostas mock são usadas automaticamente.

```bash
# Instalar dependências (apenas na primeira vez)
npm install

# Iniciar servidor de desenvolvimento
npm run dev
```

Acesse `http://localhost:5173` no navegador. O hot reload atualiza a tela automaticamente ao salvar arquivos.

---

### 4.2 Desktop com Python

Executa o app como uma janela nativa do Windows, sem abrir navegador.
Requer que o build do React exista em `dist/`.

```bash
# Passo 1: Instalar dependências Python (apenas na primeira vez)
pip install -r requirements.txt

# Passo 2: Gerar o build do React
npm run build

# Passo 3: Executar o app desktop
python main.py
```

> **Nota:** O `dist/` precisa ser regerado com `npm run build` toda vez que você alterar o código do React.

---

### 4.3 Executável compilado (.exe)

Gera um `.exe` standalone que pode ser distribuído e executado em qualquer Windows sem instalar Python, Node.js ou dependências.

**Opção A — Script automático (recomendado):**
```bash
build_app.bat
```
O script executa os três passos em sequência e exibe o resultado.

**Opção B — Manual:**
```bash
# 1. Build do React
npm run build

# 2. Instalar PyInstaller se necessário
pip install pyinstaller

# 3. Compilar o executável
pyinstaller assistente_ia.spec --clean --noconfirm
```

O executável é gerado em:
```
dist/
└── AssistenteIA/
    └── AssistenteIA.exe   ← distribuível
```

> **Importante:** Distribua a pasta `AssistenteIA/` inteira, não apenas o `.exe`.

---

## 5. Arquitetura

### 5.1 Componentes React

| Componente | Arquivo | Responsabilidade |
|---|---|---|
| `App` | `App.tsx` | Estado global do chat, orquestra os demais componentes |
| `Header` | `Header.tsx` | Topbar com logo animado e botão Grafo |
| `WelcomeScreen` | `WelcomeScreen.tsx` | Tela inicial exibida quando não há mensagens |
| `MessageBubble` | `MessageBubble.tsx` | Bolha individual de mensagem (usuário ou assistente) |
| `TypingIndicator` | `MessageBubble.tsx` | Animação de "digitando..." enquanto aguarda resposta |
| `ChatInput` | `ChatInput.tsx` | Textarea com auto-resize, controle de arquivo e botões |
| `Icons` | `Icons.tsx` | Ícones SVG inline (sem dependência de biblioteca externa) |

**Fluxo de dados no React:**

```
ChatInput (usuário digita e envia)
    │
    ▼
App.tsx — handleSendMessage()
    │  Adiciona mensagem do usuário no estado
    │  Chama bridge.sendMessage()
    │
    ▼
bridge.ts — detecta ambiente e roteia
    │  PyWebView disponível? → window.pywebview.api.sendMessage()
    │  Dev mode?             → mockSendMessage() (resposta simulada)
    │
    ▼
App.tsx — recebe a resposta
    │  Adiciona mensagem do assistente no estado
    │
    ▼
MessageBubble — renderiza na tela
```

---

### 5.2 Serviço Bridge

**Arquivo:** `src/services/bridge.ts`

A bridge é a única camada que conhece o ambiente de execução. Ela isola completamente o restante do código React de qualquer detalhe de comunicação com Python.

```typescript
// Uso em qualquer componente React:
import { bridge } from './services/bridge';

const resposta = await bridge.sendMessage("texto do usuário", "arquivo.pdf");
```

**Detecção automática de ambiente:**

```
Rodando npm run dev? → window.pywebview não existe → usa mock
Rodando python main.py? → window.pywebview.api disponível → chama Python
```

**Propriedades exportadas:**

| Propriedade | Tipo | Descrição |
|---|---|---|
| `bridge.sendMessage(msg, arquivo?)` | `Promise<string>` | Envia mensagem e aguarda resposta |
| `bridge.isDesktop` | `boolean` | `true` se rodando dentro do PyWebView |

---

### 5.3 Ponto de Entrada Python

**Arquivo:** `main.py`

Responsável por:
1. Instanciar a classe `Api` (bridge do lado Python)
2. Localizar o `dist/index.html` (funciona em dev e no `.exe` compilado)
3. Criar e exibir a janela nativa via PyWebView

**Classe `Api`:**
```python
class Api:
    def sendMessage(self, message: str, attachment: str = None) -> str:
        # Chamado automaticamente pelo JavaScript quando o usuário envia mensagem
        # Retorna uma string que aparece como resposta do assistente na tela
        ...
```

**Resolução de caminhos:**
```python
def get_html_path() -> str:
    if getattr(sys, 'frozen', False):
        base_path = sys._MEIPASS   # .exe compilado: arquivos estão em _MEIPASS
    else:
        base_path = os.path.dirname(__file__)  # desenvolvimento: pasta do script
    return os.path.join(base_path, 'dist', 'index.html')
```

---

## 6. Como Integrar o Backend Python

Toda a integração acontece em um único lugar: **`main.py`**, na classe `Api`.

### Passo 1 — Implemente o método `sendMessage`

Abra `main.py` e substitua o placeholder pelo seu código real:

```python
class Api:
    def sendMessage(self, message: str, attachment: str = None) -> str:
        """
        Este método é chamado pelo React toda vez que o usuário envia uma mensagem.
        Ele DEVE retornar uma string: o texto que aparecerá como resposta na tela.
        """

        # Exemplo com uma função de IA hipotética:
        resposta = minha_ia.processar(message)
        return resposta
```

> **Regra importante:** O método deve **sempre retornar uma `str`**. O React exibe esse valor diretamente como mensagem do assistente.

---

### Passo 2 — Adicione novos métodos conforme necessário

Você pode adicionar quantos métodos quiser na classe `Api`. Cada um ficará disponível no JavaScript como `window.pywebview.api.nomeDoMetodo()`.

**Python (`main.py`):**
```python
class Api:
    def sendMessage(self, message: str, attachment: str = None) -> str:
        ...

    def processAudio(self, audio_path: str) -> str:
        """Novo método: processa áudio e retorna transcrição."""
        transcricao = meu_modelo_de_audio.transcrever(audio_path)
        return transcricao

    def getHistory(self) -> list:
        """Retorna histórico de conversas salvo no disco."""
        return carregar_historico()
```

**TypeScript (`bridge.ts`) — adicione a declaração de tipo:**
```typescript
interface PythonApi {
  sendMessage: (message: string, attachment?: string) => Promise<string>;

  // Novos métodos:
  processAudio: (audioPath: string) => Promise<string>;
  getHistory: () => Promise<{ role: string; content: string }[]>;
}
```

**TypeScript (`bridge.ts`) — exponha no objeto `bridge`:**
```typescript
export const bridge = {
  sendMessage: async (...) => { ... },

  // Novos métodos:
  processAudio: async (audioPath: string): Promise<string> => {
    if (isDesktopApp && window.pywebview?.api) {
      return window.pywebview.api.processAudio(audioPath);
    }
    return '[Mock] Áudio processado.';
  },
};
```

---

### Passo 3 — Inicialização do backend (opcional)

Se o backend precisar de inicialização (carregar modelo, conectar banco de dados, etc.), use o evento `started` do PyWebView:

```python
def on_app_started(window):
    """Executado após a janela ser criada e a interface carregada."""
    # Carregue modelos pesados aqui, não antes de abrir a janela
    meu_modelo = carregar_modelo_ia()
    api.modelo = meu_modelo
    print("[Backend] Modelo de IA carregado.")

if __name__ == '__main__':
    api = Api()
    html_path = get_html_path()

    window = webview.create_window(
        title='Assistente IA',
        url=html_path,
        js_api=api,
        width=1100,
        height=700,
        min_size=(800, 600),
    )

    webview.start(on_app_started, window, debug=False)
```

---

### Passo 4 — Chamar Python a partir do React

No React, use sempre o `bridge`:

```typescript
// Em qualquer componente ou hook:
import { bridge } from '../services/bridge';

// Chamada simples:
const resposta = await bridge.sendMessage("Olá!");

// Com arquivo:
const resposta = await bridge.sendMessage("Analise este arquivo", arquivo.name);
```

> O `bridge` cuida automaticamente de usar o PyWebView em produção e o mock em desenvolvimento. Você nunca precisa acessar `window.pywebview` diretamente.

---

## 7. Design System

A interface usa variáveis CSS centralizadas em `src/index.css`:

| Categoria | Variável | Valor |
|---|---|---|
| **Fundo principal** | `--bg-primary` | `#0a0a0a` |
| **Superfícies** | `--bg-surface` | `#1a1a1a` |
| **Input** | `--bg-input` | `#1e1e1e` |
| **Acento azul** | `--accent-blue` | `#2563eb` |
| **Gradiente** | `--accent-gradient` | azul escuro → azul |
| **Texto primário** | `--text-primary` | `#ffffff` |
| **Texto secundário** | `--text-secondary` | `#a1a1aa` |
| **Fonte** | `--font-family` | Inter (Google Fonts) |

Para alterar cores ou espaçamentos globalmente, edite apenas as variáveis em `src/index.css`.

---

## 8. Referência de Scripts

| Comando | Descrição |
|---|---|
| `npm install` | Instala dependências do Node.js (apenas na primeira vez) |
| `npm run dev` | Inicia servidor de desenvolvimento com hot reload |
| `npm run build` | Gera o build de produção em `dist/` |
| `npm run lint` | Executa o ESLint para verificar erros no código |
| `pip install -r requirements.txt` | Instala dependências Python |
| `python main.py` | Executa o app desktop (requer `dist/` gerado) |
| `pyinstaller assistente_ia.spec --clean` | Compila o `.exe` manualmente |
| `build_app.bat` | Executa build do React + compilação do `.exe` em sequência |
