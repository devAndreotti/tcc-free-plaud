# free-plaud

Sistema desktop local-first para captura multimodal, estruturação automática em Markdown e recuperação semântica de conhecimento pessoal em português brasileiro.

## Status

O repositório está em fase de fundação de TCC com scaffold inicial do backend já iniciado:

- problema de pesquisa definido
- perguntas de pesquisa delimitadas
- arquitetura alvo descrita
- plano de arranque documentado
- scaffold inicial do backend em Python criado

## Problema

Profissionais e estudantes capturam informação em áudio, imagem, PDF e texto, mas perdem boa parte desse conhecimento porque transformar esse material em notas pesquisáveis exige disciplina manual alta demais.

O objetivo deste projeto é testar se um pipeline com:

- processamento multimodal
- estruturação automática em Markdown
- embeddings vetoriais
- RAG com citação obrigatória

é suficiente para reduzir essa fricção sem fine-tuning e sem infraestrutura de nuvem própria.

## Perguntas centrais

1. O pipeline produz notas úteis a partir de entradas reais em português brasileiro?
2. Quais parâmetros de chunking e recuperação mais impactam a qualidade do AutoRAG?
3. Qual modelo de embedding performa melhor nesse contexto?
4. Opcionalmente: como qualidade e latência degradam com o crescimento do acervo?

## Estratégia técnica atual

O projeto foi deliberadamente quebrado em fases para reduzir risco:

1. Backend e benchmark em Python primeiro
2. Interface web local depois
3. Casca desktop com Tauri apenas quando o núcleo experimental estiver estável

Essa ordem prioriza a parte científica do TCC antes da parte cosmética do produto.

## Operação local atual

O backend experimental já roda por CLI, TUI Textual e menu terminal:

```powershell
cd D:\Dev\Repos\Own\tcc-free-plaud\pipeline
uv run free-plaud-tui
uv run free-plaud menu
```

A interface React/PyWebView pode chamar o RAG real do corpus indexado:

```powershell
cd D:\Dev\Repos\Own\tcc-free-plaud\UI
npm.cmd run build
cd ..\pipeline
uv run --extra desktop python ..\UI\main.py
```

Segredos locais ficam em `.env` e não entram no Git. A chave de resposta generativa deve usar:

```env
FREE_PLAUD_ANSWER_API_KEY=sua-chave
```

No TUI, no menu terminal e na UI desktop há opção para salvar essa chave em `pipeline/.env`.

Modelo LLM local não é selecionado por pasta no free-plaud. O app aponta para um servidor local
compatível com OpenAI, como Ollama ou LM Studio. A pasta selecionada na UI é o corpus/vault a ser
indexado, não o diretório do modelo.

## Stack sugerida para começar

- `Python 3.12`
- `uv`
- `Typer`
- `Pydantic`
- `SQLite`
- `ChromaDB`
- `Pytest`
- `React + TypeScript + Vite + Tailwind` na fase de interface
- `Tauri` apenas na fase de desktop shell

## Documentação principal

- Visão geral do TCC: [`docs/tcc/texto/TCC.md`](docs/tcc/texto/TCC.md)
- Arquitetura do sistema: [`docs/arquitetura/Arquitetura.md`](docs/arquitetura/Arquitetura.md)
- Backend: [`docs/arquitetura/Arquitetura_Backend.md`](docs/arquitetura/Arquitetura_Backend.md)
- Frontend: [`docs/arquitetura/Arquitetura_Frontend.md`](docs/arquitetura/Arquitetura_Frontend.md)
- Plano de arranque: [`docs/planejamento/Plano_de_Arranque.md`](docs/planejamento/Plano_de_Arranque.md)
- Metodologia Akita + git: [`docs/planejamento/Metodologia_Akita_Git.md`](docs/planejamento/Metodologia_Akita_Git.md)
- Perguntas que o trabalho precisa responder: [`docs/tcc/perguntas/Perguntas_a_Serem_Respondidas.md`](docs/tcc/perguntas/Perguntas_a_Serem_Respondidas.md)
- Prep de defesa: [`docs/tcc/perguntas/Perguntas_do_TCC.md`](docs/tcc/perguntas/Perguntas_do_TCC.md)

## Convenções do repositório

- `main` deve refletir apenas estado estável
- branches curtas por fatia funcional
- um commit por decisão relevante
- testes e documentação andam junto da implementação
- arquitetura e escopo devem ser atualizados antes de expandir código

## Roadmap inicial

### Marco 0 - Fundamentos

- consolidar docs
- criar `CLAUDE.md`
- acertar estratégia de branches e tags
- definir baseline tecnológico

### Marco 1 - Core RAG textual

- ingestão de texto e PDF
- estruturação em nota Markdown
- chunking
- embeddings
- busca vetorial
- resposta com citação

### Marco 2 - Benchmark

- datasets
- MRR
- Recall@k
- latência
- comparação de embeddings

### Marco 3 - Multimodal

- áudio
- imagem
- OCR

### Marco 4 - Interface

- fila
- chat
- benchmark
- configurações

### Marco 5 - Desktop

- empacotamento com Tauri
- observação de pasta
- integração local

## Observações

- O backend experimental vive em `pipeline/`.
- O repositório já possui um baseline inicial para CLI, configuração local e testes.
- A pasta [`.agents/inspirations`](.agents/inspirations) foi reservada para a direção visual futura do app.
