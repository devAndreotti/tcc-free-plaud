# CLAUDE.md - free-plaud

## Overview

`free-plaud` é um projeto de TCC focado em um pipeline de IA para captura multimodal, estruturação automatizada em Markdown e recuperação semântica de conhecimento pessoal em português brasileiro.

O produto final desejado é um app desktop local-first, mas a prioridade do projeto é a validação experimental do pipeline e do módulo de benchmark.

## Current Phase

Fase atual: fundação documental e arquitetura.

Antes de escrever código, ler:

1. `docs/TCC.md`
2. `docs/Arquitetura.md`
3. `docs/Arquitetura_Backend.md`
4. `docs/Arquitetura_Frontend.md`
5. `docs/Metodologia_Akita_Git.md`
6. `docs/Plano_de_Arranque.md`

## Non-Negotiable Rules

1. Não começar pela casca desktop.
2. Não abrir a implementação por Rust/Tauri antes do core experimental.
3. Testes e benchmark antes de expansão de features.
4. Documentação arquitetural deve ser atualizada junto com decisões relevantes.
5. `main` deve ficar estável.
6. Um commit por decisão relevante, não por volume de alteração.
7. Branches curtas e focadas.

## Architecture Strategy

### Phase 1 - Backend and benchmark first

- Python 3.12
- uv
- Typer
- Pydantic
- SQLite
- ChromaDB
- Pytest

Objetivo: provar ingestão, estruturação, indexação e RAG com citação.

### Phase 2 - Local UI

- React
- TypeScript
- Vite
- Tailwind
- Zustand

Objetivo: operar fila, chat, configurações e benchmark de forma visual.

### Phase 3 - Desktop shell

- Tauri

Objetivo: empacotar a interface e integrar monitoramento local com menor custo operacional.

## Planned Repository Structure

```text
free-plaud/
├── .agents/
│   ├── inspirations/
│   ├── skills/
│   └── workflows/
├── data/
│   ├── corpus/
│   ├── datasets/
│   └── results/
├── docs/
├── pipeline/
├── src/
├── src-tauri/
├── CLAUDE.md
└── README.md
```

## Git and Delivery Rules

### Branching

- `main` = estado estável
- `feat/pipeline-core`
- `feat/rag-benchmark`
- `feat/audio-ingest`
- `feat/desktop-shell`

### Tags

- `v0-core-rag`
- `v0-benchmark`
- `v0-audio`
- `v0-ui`

### Commit discipline

- um commit por decisão relevante
- commits pequenos e legíveis
- sem acumular alterações grandes e desconexas

## What To Avoid

- acoplar provedor de IA diretamente em toda a base
- espalhar lógica de benchmark por múltiplos módulos
- misturar regra de negócio do pipeline com detalhes de UI
- gastar tempo cedo demais com animação, polimento visual ou instaladores
- criar features fora do escopo do TCC antes do benchmark mínimo

## Preferred Documentation Pattern

Quando surgir decisão estrutural nova:

1. atualizar `docs/Arquitetura.md` se afetar o desenho geral
2. atualizar `docs/Arquitetura_Backend.md` ou `docs/Arquitetura_Frontend.md` se afetar detalhe de camada
3. atualizar `docs/TCC.md` se alterar escopo, pergunta de pesquisa ou contribuição
4. atualizar `README.md` se for algo relevante para entendimento externo do projeto
