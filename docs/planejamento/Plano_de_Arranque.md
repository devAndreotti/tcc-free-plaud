---
tags:
- tcc
- plano
- arranque
- execucao
---

# Plano de Arranque

## Objetivo

Transformar o projeto de um conjunto de boas ideias bem escritas em um repositório com trilha de execução clara e baixo risco de dispersão.

## Regra de ouro

Começar pelo núcleo experimental.
Não começar pela casca desktop.

## Semana 0 - Higiene do repositório

### Objetivos

- consolidar os documentos-base
- criar `CLAUDE.md`
- revisar o estado do git
- preparar a estratégia de branches

### Entregáveis

- `README.md`
- docs arquiteturais
- `CLAUDE.md`
- estratégia Akita + git documentada

### Observação

Hoje o repositório ainda precisa de um baseline de git confiável.
Antes da implementação, vale revisar:

- remote `origin`
- commit inicial em `main`

## Semana 1 - Core textual

### Branch

- `feat/pipeline-core`

### Entregáveis

- scaffold do backend em Python
- ingestão de `.txt`, `.md` e `.pdf`
- schema da nota
- estruturação inicial em Markdown

### Gate

Não avançar enquanto não existir:

- teste de parsing
- teste da nota estruturada

## Semana 2 - Recuperação mínima

### Branch

- continua em `feat/pipeline-core` ou abre `feat/rag-benchmark` se a fatia crescer demais

### Entregáveis

- chunking
- embeddings
- indexação vetorial
- primeira pergunta respondida com citação

### Gate

Não avançar enquanto não existir:

- teste de recuperação
- teste de citação obrigatória

### Tag alvo

- `v0-core-rag`

## Semana 3 - Harness de benchmark

### Branch

- `feat/rag-benchmark`

### Entregáveis

- formato de dataset
- runners de experimento
- MRR
- Recall@k
- exportação de resultados

### Gate

Não avançar enquanto não existir:

- script reprodutível de benchmark
- resultados exportáveis

### Tag alvo

- `v0-benchmark`

## Semana 4 - Audio first

### Branch

- `feat/audio-ingest`

### Entregáveis

- ingestão de áudio
- transcrição
- estruturação
- entrada de áudio passando pelo mesmo core RAG

### Gate

Não avançar enquanto não existir:

- ao menos um fluxo completo de áudio com teste de regressão

### Tag alvo

- `v0-audio`

## Semana 5 - Interface mínima

### Branch

- `feat/ui-shell` ou `feat/desktop-shell` se já houver maturidade suficiente

### Entregáveis

- dashboard simples
- fila
- chat
- configurações mínimas

### Gate

Não entrar em polimento visual pesado.
O objetivo é demonstrar o pipeline, não vender design.

### Tag alvo

- `v0-ui`

## Primeiras tarefas técnicas concretas

1. Criar o scaffold Python com `uv`.
2. Definir schema da nota em `Pydantic`.
3. Implementar leitura de texto e PDF.
4. Implementar estruturação de nota.
5. Implementar indexação com `ChromaDB`.
6. Implementar pergunta + resposta com citação.
7. Criar runner de benchmark.

## Riscos a evitar

1. Tentar resolver desktop, áudio, imagem e benchmark de uma vez.
2. Construir UI antes de ter resultado experimental mínimo.
3. Acoplar toda a base a um provedor único.
4. Adicionar features de produto fora do escopo do TCC.

## Definição de sucesso do arranque

O arranque está bem-sucedido quando o repositório tiver:

1. arquitetura estável
2. git organizado
3. core textual implementado
4. benchmark executável
5. próximo passo claro para áudio e interface
