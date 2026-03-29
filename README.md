# free-plaud

Sistema desktop local-first para captura multimodal, estruturação automática em Markdown e recuperação semântica de conhecimento pessoal em português brasileiro.

## Status

O repositório está em fase de fundação de TCC:

- problema de pesquisa definido
- perguntas de pesquisa delimitadas
- arquitetura alvo descrita
- plano de arranque documentado
- implementação ainda não iniciada

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

- Visão geral do TCC: [`docs/TCC.md`](docs/TCC.md)
- Arquitetura do sistema: [`docs/Arquitetura.md`](docs/Arquitetura.md)
- Backend: [`docs/Arquitetura_Backend.md`](docs/Arquitetura_Backend.md)
- Frontend: [`docs/Arquitetura_Frontend.md`](docs/Arquitetura_Frontend.md)
- Plano de arranque: [`docs/Plano_de_Arranque.md`](docs/Plano_de_Arranque.md)
- Metodologia Akita + git: [`docs/Metodologia_Akita_Git.md`](docs/Metodologia_Akita_Git.md)
- Perguntas que o trabalho precisa responder: [`docs/Perguntas_a_Serem_Respondidas.md`](docs/Perguntas_a_Serem_Respondidas.md)
- Prep de defesa: [`docs/Perguntas_do_TCC.md`](docs/Perguntas_do_TCC.md)

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

- O repositório ainda não tem commit inicial útil.
- O `origin` atual parece indisponível e deve ser revisado antes do início efetivo da implementação.
- A pasta [`.agents/inspirations`](.agents/inspirations) foi reservada para a direção visual futura do app.
