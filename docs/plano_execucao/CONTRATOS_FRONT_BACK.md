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
  note_version: number
  chunk_id: string
  snippet: string
  source_path?: string
  char_start: number
  char_end: number
}

type Claim = {
  text: string
  citations: Citation[]
  support_level: 'direct' | 'partial'
}

type UsedSource = {
  doc_id: string
  note_version: number
  source_path?: string
  chunk_ids: string[]
}

type AskResponse = {
  query: string
  status: 'answer' | 'no_answer'
  no_answer: boolean
  answer: string | null
  claims: Claim[]
  citations: Citation[]
  limitations: string[]
  reason_for_no_answer: string | null
  used_sources: UsedSource[]
  latency_ms: number
}
```

### Comportamento esperado

- `query` preserva a pergunta original
- `status` explicita se houve resposta ou abstencao
- `no_answer` facilita consumo direto pela UI
- `answer` contem a resposta textual ou `null`
- `claims` divide a resposta em afirmacoes citaveis
- `citations` agrega as citacoes usadas na resposta
- `reason_for_no_answer` explica a abstencao quando ela acontecer
- `used_sources` resume quais fontes sustentaram a resposta
- `latency_ms` ajuda em debug e benchmark visual
- `source_path` e offsets ajudam a ligar UI, debug e rastreabilidade

### Motivos atuais de abstencao

Hoje o backend pode devolver, entre outros, motivos como:

- `query_without_content`
- `no_retrieval_hits`
- `insufficient_term_coverage`
- `insufficient_vector_evidence`
- `insufficient_grounded_claims`
- `missing_named_anchor`
- `insufficient_vector_specificity`
- `citation_validation_failed`

O frontend nao deve depender de um texto amigavel fixo para esses motivos.

Ele deve tratá-los como codigos de estado, deixando a apresentacao da mensagem com a UI.

## Contratos secundarios

### NoteSummary

```ts
type NoteSummary = {
  note_id: string
  title: string
  source_type: string
  source_path: string
  created_at: string
  tags: string[]
  chunk_count: number
}

type NoteChunkSummary = {
  chunk_id: string
  chunk_index: number
  char_start: number
  char_end: number
  token_count: number
  snippet: string
}

type NoteDetail = NoteSummary & {
  structured_markdown: string
  chunks: NoteChunkSummary[]
}

type NoteDeleteResult = {
  ok: boolean
  note_id?: string
  deleted_vectors?: number
  status?: string
  message?: string
}

type NoteReindexResult = {
  ok: boolean
  note_id: string
  status: 'success' | 'failed' | 'cancelled' | 'unchanged'
  chunks_indexed: number
  message: string | null
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
  getNoteDetail(noteId: string): Promise<NoteDetail>
  deleteNote(noteId: string, confirmation: string): Promise<NoteDeleteResult>
  reindexNote(noteId: string): Promise<NoteReindexResult>
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
