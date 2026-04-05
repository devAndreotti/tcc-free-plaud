# Contratos Front Back

## Objetivo deste arquivo

Este documento define o contrato entre backend e frontend.

Ele serve para:

- evitar que a UI dependa de detalhes internos do backend
- permitir mock no frontend antes da integracao real
- reduzir retrabalho quando a ponte real for implementada

## Regra principal

O frontend nao deve assumir que a resposta do backend e uma `string` simples.

Desde cedo, a UI deve trabalhar com objetos estruturados.

## Contrato inicial prioritario

### AskResponse

```ts
type Citation = {
  note_id: string
  chunk_id: string
  snippet: string
  source_path?: string
}

type AskResponse = {
  answer: string
  citations: Citation[]
  no_answer: boolean
  latency_ms: number
  query: string
}
```

### Comportamento esperado

- `answer` contem a resposta textual
- `citations` contem a base usada
- `no_answer` indica falta de evidencia suficiente
- `latency_ms` ajuda em debug e benchmark visual
- `query` permite rastrear a pergunta exibida ou registrada

## Contratos secundarios

### NoteSummary

```ts
type NoteSummary = {
  note_id: string
  title: string
  source_type: 'txt' | 'md' | 'pdf' | 'audio' | 'image'
  source_path: string
  created_at: string
  tags: string[]
}
```

### QueueItem

```ts
type QueueItemStatus = 'pending' | 'processing' | 'done' | 'error'

type QueueItem = {
  item_id: string
  source_path: string
  source_type: string
  status: QueueItemStatus
  step?: string
  error_message?: string
  started_at?: string
  finished_at?: string
}
```

### ExperimentRunSummary

```ts
type ExperimentRunSummary = {
  experiment_id: string
  dataset_name: string
  embedding_model: string
  chunk_size: number
  overlap: number
  top_k: number
  latency_ms: number
  mrr: number
  recall_at_3: number
  recall_at_5: number
  recall_at_10: number
}
```

## Ponte inicial esperada

Enquanto a integracao real nao existir, a UI pode mockar estes metodos:

```ts
interface BackendBridge {
  ask(query: string): Promise<AskResponse>
  listNotes(): Promise<NoteSummary[]>
  listQueue(): Promise<QueueItem[]>
  listExperiments(): Promise<ExperimentRunSummary[]>
}
```

## Regra para a implementacao do frontend

O Joao deve preferir:

1. mockar esses contratos no frontend
2. montar componentes usando esses objetos
3. trocar a origem mock pela origem real depois

Assim, a interface nao precisa ser reescrita quando o backend estiver pronto.

## Regra para a implementacao do backend

O backend deve preferir:

1. estabilizar os schemas
2. devolver payload estruturado
3. esconder detalhes de provider e storage

Assim, a interface consome apenas o contrato, nao a implementacao.

## O que evitar

- `sendMessage(): Promise<string>` como contrato final
- frontend acessar campos internos do banco
- frontend depender de formato cru do provedor
- contratos mudando sem atualizar este arquivo
