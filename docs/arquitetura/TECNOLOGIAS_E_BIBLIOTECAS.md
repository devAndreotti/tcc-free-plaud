# Stack Tecnológica e Bibliotecas - Free Plaud

Documento de referência das linguagens, runtimes, bibliotecas e componentes de infraestrutura da arquitetura do Free Plaud.

---

## 1. Linguagens e Runtimes

- **Python 3.12**: Runtime principal do backend, pipeline de ingestão, orquestração RAG e módulo de benchmark.
- **TypeScript / JavaScript (ESNext)**: Linguagem do frontend desktop (React). Garante tipagem estática e contratos alinhados com o backend.
- **CUDA 12.8**: Runtime de aceleração por hardware (GPU Nvidia) para transcrição de áudio e inferência local de embeddings/LLMs.

---

## 2. Camada de Apresentação (Frontend & CLI / TUI)

- **Typer**: Framework para construção da CLI baseada em *type hints* do Python.
- **Rich**: Biblioteca para formatação, tabelas, barras de progresso e estilização avançada no terminal.
- **Textual**: Framework para interfaces TUI completas no terminal com suporte a eventos assíncronos, janelas e painéis divididos (Ask, Notes, Benchmark).
- **React 19**: Biblioteca de interfaces declarativas para a interface gráfica desktop.
- **PyWebView / Edge Bridge (WebView2)**: Shell leve para renderização do bundle React via WebView nativa do Windows (Edge/Chromium), comunicando com o runtime Python via ponte JS.

---

## 3. Ingestão e Processamento Multimodal

- **Whisper / Faster-Whisper**: Modelo de ASR (*Automatic Speech Recognition*) para transcrição local de áudio acelerado por GPU.
- **PyPDF**: Biblioteca para extração de texto e metadados de documentos PDF.
- **Pydantic / pydantic-settings**: Validação de contratos de dados, serialização de notas Markdown e parsing tipado de variáveis de ambiente/configuração.
- **pt-BR Normalizer**: Pipeline de limpeza e normalização de texto para tratamento de peculiaridades gramaticais e remoção de vícios de fala em português brasileiro.

---

## 4. Recuperação Híbrida e Armazenamento (RAG Core)

- **SQLite + FTS5**: Banco relacional embutido com módulo Full-Text Search (FTS5) para busca léxica precisa (BM25), armazenamento de metadados, chunks e offsets de citação.
- **ChromaDB**: Banco vetorial local e embarcado para indexação e busca semântica densa de chunks de texto.
- **SentenceTransformers**: Biblioteca para carregamento e inferência de modelos de embeddings locais.
- **RRF (Reciprocal Rank Fusion)**: Algoritmo de ordenação e mesclagem que combina os rankings léxico (SQLite FTS5) e vetorial (ChromaDB) para busca híbrida robusta.

---

## 5. Execução de LLMs e Provedores de IA

- **Ollama**: Servidor local para execução e inferência de modelos abertos (Llama, Mistral, Qwen, DeepSeek).
- **LM Studio**: Alternativa local com API REST compatível com OpenAI.
- **APIs de Provedores Proprietários**: Integração via HTTP/SDKs para modelos externos (OpenAI, Anthropic, Google Gemini).

---

## 6. Ferramental de Desenvolvimento e Testes

- **uv**: Gerenciador de pacotes e ambientes virtuais rápido escrito em Rust.
- **Pytest**: Framework para testes unitários, testes de integração e execução automatizada da suite de benchmark de RAG.
