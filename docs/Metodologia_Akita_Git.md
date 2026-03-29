---
tags:
- tcc
- akita
- git
- processo
---

# Metodologia Akita + Git

## Objetivo

Aplicar uma versão pragmática da metodologia inspirada no Akita ao projeto, com foco em:

- arquitetura antes de código
- fatias pequenas
- commits pequenos
- revisão contínua
- progresso audível e defensável

## Adaptação para este TCC

### Regras centrais

1. arquitetura e escopo antes da implementação
2. teste antes da expansão da feature
3. benchmark antes do polimento
4. branch curta por fatia
5. merge somente de estado entendível

## Fluxo de branches

### Branch principal

- `main`

Uso:

- baseline documental
- estado estável
- marcos prontos para demonstração

### Branches curtas sugeridas

- `feat/pipeline-core`
- `feat/rag-benchmark`
- `feat/audio-ingest`
- `feat/desktop-shell`

Se necessário, abrir sub-branches menores, por exemplo:

- `feat/pipeline-core-pdf`
- `feat/pipeline-core-structuring`

## Política de commits

### Regra prática

Um commit por decisão relevante, não por volume.

### Bons exemplos

- `docs: refine research questions and architecture`
- `feat: add note schema and markdown serializer`
- `test: cover retrieval citations`
- `refactor: isolate embedding provider interface`

### Maus exemplos

- um commit único com backend inteiro
- commit misturando docs, benchmark, UI e ajuste de estilo
- commit gigante com "misc fixes"

## Política de tags

Usar tags em marcos claros, não em toda entrega pequena.

### Tags sugeridas

- `v0-core-rag`
- `v0-benchmark`
- `v0-audio`
- `v0-ui`

## Ritmo recomendado

### Antes de abrir branch nova

Responder:

1. qual pergunta esta branch responde?
2. qual entregável mensurável ela produz?
3. como saberei que terminou?

### Antes de mergear

Checar:

1. docs relevantes atualizadas
2. testes relevantes passando
3. diff entendido
4. branch ainda pequena o suficiente para revisão humana

## Ordem recomendada

### Passo 1 - Fundação em `main`

Pode e deve existir um commit inicial estável em `main` contendo:

- `README.md`
- `CLAUDE.md`
- docs de arquitetura
- plano de arranque

Esse é o único uso aceitável de `main` como ponto de partida.

### Passo 2 - Features em branches curtas

Depois do baseline:

- toda implementação vai para branch
- `main` para de ser espaço de experimento

## Checklist rápido por branch

### `feat/pipeline-core`

- ingestão textual
- estruturação
- indexação
- pergunta com citação

### `feat/rag-benchmark`

- datasets
- métricas
- runners
- exportação

### `feat/audio-ingest`

- áudio
- transcrição
- integração com pipeline existente

### `feat/desktop-shell`

- UI mínima
- shell desktop
- integração local

## Regra de proteção contra dispersão

Se uma branch começa a mexer em:

- backend
- benchmark
- UI
- docs estruturais

tudo ao mesmo tempo, ela provavelmente está grande demais e deve ser quebrada.

## Resultado esperado

Se esse processo for seguido, o TCC ganha:

- histórico explicável
- arquitetura mais disciplinada
- menos retrabalho
- demonstrações mais frequentes
- material melhor para a banca
