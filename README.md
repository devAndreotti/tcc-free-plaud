# Escólio

(antes chamado free-plaud)

Sistema desktop local-first para captura multimodal, estruturacao automatica em Markdown e recuperacao semantica de conhecimento pessoal em portugues brasileiro.

## Status do Projeto

O projeto concluiu integralmente seu ciclo de desenvolvimento e validacao experimental (Sprints 00 a 09):

- **Core RAG Hibrido Operacional:** Persistencia dupla em SQLite FTS5 (BM25) e ChromaDB (vetorial) com fusao Reciprocal Rank Fusion (RRF, $k=60$) e citacoes estritas por span (`start_char`, `end_char`) sem alucinacao.
- **Captura e Transcricao de Audio Local:** Ingestao direta de microfone com Voice Activity Detection (Silero VAD ONNX) e modelos locais Whisper (`faster-whisper`), com download assincrono e selecao de idioma/auto-deteccao pela UI.
- **Compressao Vetorial TurboQuant:** Quantizacao escalar int8 em tempo de execucao, reduzindo consumo de memoria de embeddings densos em ~75%.
- **Quad-Interface Unificada:** 4 interfaces funcionais compartilhando o mesmo runtime do corpus:
  1. CLI Typer (`escolio.cli`, `es.ps1`)
  2. Menu Terminal Numerado (Rich)
  3. Textual TUI reativa (`escolio.tui.app`)
  4. App Desktop Standalone (PyWebView + React 19 + TypeScript + Vite + Tailwind)
- **Suite E2E & Ratchet de Cobertura:** Suíte completa de testes unitários e de integração com cobertura travada em **89.0%** no Quality Gate.
- **Empacotamento Desktop Standalone:** Executavel Windows `.exe` standalone com Edge WebView2 gerado via PyInstaller.

## Problema e Proposta

Profissionais e estudantes capturam informacao em audio, imagem, PDF e texto, mas perdem boa parte desse conhecimento porque transformar esse material em notas pesquisaveis exige disciplina manual alta demais.

O `Escólio` implementa um pipeline privado e soberano que:
1. Ingesta fontes textuais (PDF, TXT, MD), vaults Obsidian e gravacoes de audio do microfone.
2. Estrutura o conteudo automaticamente em notas Markdown canonicas com frontmatter rico.
3. Indexa e fatia em chunks com preservacao de offsets de caracteres para rastreabilidade de citacao.
4. Recupera e responde a perguntas em pt-BR via fusao hibrida RRF com comprovacao de fonte obrigatoria (ou abstencao estruturada com `no_answer` quando a evidencia for insuficiente).

## Operacao Local Rapida

A partir da raiz do projeto, use os comandos rapidos no PowerShell:

```powershell
.\es.ps1 app      # Abre o App Desktop integrado (PyWebView + React 19)
.\es.ps1 tui      # Abre a interface de terminal Textual
.\es.ps1 menu     # Abre o menu interativo numerado no terminal
.\es.ps1 doctor   # Executa diagnostico estruturado do ambiente local
.\es.ps1 bench    # Executa a bateria de benchmark comparativo
.\es.ps1 test     # Roda a suite de testes automatizados
.\es.ps1 release  # Compila e gera o executavel standalone desktop (.exe e .zip)
```

No Linux / macOS / WSL (bash):

```bash
./es app
./es tui
./es menu
./es doctor
./es bench
./es test
./es release
```

Para desenvolvimento apenas do frontend com bridge mockada no navegador:

```powershell
.\es.ps1 front
```

## Segredos e Provedores de Resposta

O `Escólio` foi desenhado para privacidade total:
- **Embeddings e Transcricao de Voz:** 100% locais (Hugging Face, faster-whisper, Silero VAD, CUDA 12 ou CPU).
- **Provedores de LLM para Resposta:** Apontam para provedores locais (Ollama, LM Studio) ou remotos compativeis com OpenAI.

Chaves de API ficam salvas exclusivamente em `pipeline/.env` (fora do Git):

```env
ESCOLIO_ANSWER_API_KEY=sua-chave
```

## Estrutura do Repositorio

```text
Escólio/
├── pipeline/src/escolio/   # Core do backend (Python 3.12 via uv)
│   ├── app/                   # Configuracoes Pydantic, catalogo, doctor e audio service
│   ├── ingest/                # Extratores PDF/TXT/MD, cleaner Obsidian, watcher e downloads
│   ├── notes/                 # Estruturador canonico, normalizador pt-BR e repositorio
│   ├── retrieval/             # Chunking por offsets, BM25 FTS5, vetorial e fusao RRF
│   ├── providers/             # Adapters Whisper, Silero VAD, TurboQuant e LLMs
│   ├── storage/               # SQLite FTS5 relacional e ChromaDB vetorial
│   ├── corpus/                # CorpusRuntime unificado, ask engine e jobs de fila
│   ├── benchmark/             # Avaliador experimental (MRR, Recall@k, latencia)
│   └── tui/                   # Aplicacao reativa Textual (Ask, Notes, Benchmark, Settings)
├── UI/                        # Frontend React 19 + TypeScript + PyWebView
│   ├── src/components/        # Chat, Fila, Notes, Benchmark, Select, Modal de Settings
│   ├── e2e/                   # Suite de testes Playwright end-to-end
│   └── main.py                # Entrypoint desktop PyWebView (Edge WebView2)
├── docs/                      # Especificacoes tecnicas, arquitetura, experimentos e monografia
│   ├── spec-kit/              # Especificacoes e planos de execucao auditados
│   ├── experimentos/          # Experimentos empiricos (15 calibracao RRF)
│   └── tcc/                   # Monografia (docs/tcc/texto/TCC.md) e slides (docs/tcc/slides/)
├── Sprints/                   # Historico documental detalhado (Sprints 00 a 09)
├── es.ps1                     # Launcher canonico PowerShell
└── es                         # Launcher bash para Unix/WSL
```

## Documentacao Principal

- Monografia Academica do TCC: [`docs/tcc/texto/TCC.md`](docs/tcc/texto/TCC.md)
- Slides da Apresentacao de Defesa: [`docs/tcc/slides/apresentacao_tcc.md`](docs/tcc/slides/apresentacao_tcc.md)
- Arquitetura Geral do Sistema: [`docs/arquitetura/Arquitetura.md`](docs/arquitetura/Arquitetura.md)
- Arquitetura de Backend: [`docs/arquitetura/Arquitetura_Backend.md`](docs/arquitetura/Arquitetura_Backend.md)
- Arquitetura de Frontend: [`docs/arquitetura/Arquitetura_Frontend.md`](docs/arquitetura/Arquitetura_Frontend.md)
- Stack Tecnologica e Bibliotecas: [`docs/arquitetura/TECNOLOGIAS_E_BIBLIOTECAS.md`](docs/arquitetura/TECNOLOGIAS_E_BIBLIOTECAS.md)
- Experimento 15 (Calibracao RRF): [`docs/experimentos/15_calibracao_rrf_tcc.md`](docs/experimentos/15_calibracao_rrf_tcc.md)
- Status das Sprints: [`Sprints/STATUS.md`](Sprints/STATUS.md)
