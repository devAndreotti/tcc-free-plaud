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
  generated: boolean        // true quando `answer` veio da IA e passou na validação
  answer_sources: string[]  // chunk_id de cada [n] da resposta gerada, na ordem
  answer_discard_reason: string | null  // motivo do descarte da resposta gerada (ver lista abaixo); null se aceita ou sem provedor
  answer_model: string | null           // provider.model quando há provedor de resposta; null sem provedor
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
- `answer_discard_reason` diz por que a resposta gerada foi tentada e não foi aceita. Quando a validação troca a IA pela resposta extrativa, `status` segue `answer` com `generated: false`; quando vira abstenção, traz o mesmo código de `reason_for_no_answer`. É `null` quando a IA foi aceita, quando não houve provedor e quando a abstenção veio da recuperação
- `answer_model` traz o modelo configurado do provedor (ex.: `qchat:latest`) sempre que há provedor, mesmo que ele não tenha respondido; é `null` sem provedor

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

### Motivos de descarte da resposta gerada (`answer_discard_reason`)

- `generated_no_answer_sentinel`: a IA escreveu `NAO_ENCONTRADO` (no começo ou no meio da resposta, sem a palavra nos contextos); vira abstenção
- `generated_generic_no_answer`: negativa genérica da IA, com sugestão de consultar documentação; vira abstenção
- `echoed_context_metadata`: a IA repetiu metadados do trecho (`source_path:`, `note_id:`, ...); volta para a extrativa
- `echoed_title`: a IA só copiou um título ou cabeçalho do contexto, em até 10 palavras; volta para a extrativa
- `echoed_question`: a IA devolveu a própria pergunta (termina em `?`, ou só usa palavras dela); volta para a extrativa
- `unsupported_number`: número que não aparece nos contextos; volta para a extrativa
- `unsupported_anchor`: nome próprio ou sigla que não aparece nos contextos; volta para a extrativa
- `low_claim_overlap`: pouca sobreposição com os trechos citáveis; volta para a extrativa
- `empty_generated_answer`: a IA devolveu só marcadores `[n]`, sem texto; volta para a extrativa
- `provider_error`: o provedor falhou (erro, timeout, payload inválido); volta para a extrativa

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

### IndexJobSnapshot

```ts
type IndexJobProgress = {
  phase: string
  current_path: string | null
  total_found: number
  processed_count: number
  indexed_count: number
  unchanged_count: number
  failed_count: number
  skipped_count: number
  elapsed_ms: number
  warmup_ms: number
  embedding_ms: number
  writing_ms: number
  committed_count: number
  commit_mode_requested: string
  commit_mode_resolved: string
  batch_index: number
  batch_total: number
  message: string | null
}

type IndexJobFileError = {
  source_path: string
  message: string
  error_code: string | null
}

type IndexJobSnapshot = {
  job_id: string
  status: 'running' | 'success' | 'partial' | 'failed' | 'cancelled'
  source_path: string
  started_at: string
  finished_at: string | null
  progress: IndexJobProgress | null
  result: unknown | null
  error_code: string | null
  message: string | null
  last_errors: IndexJobFileError[]
  cancel_requested: boolean
  files_per_second: number
  chunks_per_second: number
  eta_seconds: number | null
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
  listAnswerModels(): Promise<ModelDiscoveryResult>
  listQueue(): Promise<QueueItem[]>
  startIndexJob(folderPath: string, rebuild?: boolean): Promise<IndexJobSnapshot>
  getIndexJob(jobId: string): Promise<IndexJobSnapshot>
  cancelIndexJob(jobId: string): Promise<IndexJobSnapshot>
  listExperiments(): Promise<ExperimentRunSummary[]>
  loadConversations(): Promise<SavedConversations | null>
  saveConversations(payload: SavedConversations): Promise<{ ok: boolean; message?: string }>
  listNoteLinks(): Promise<{ source: string; target: string }[]>  // [[links]] entre notas, por note_id
  // Pergunta em segundo plano: pollAsk devolve { ask_id, stage: 'retrieving' | 'writing' | 'done' | 'error',
  // partial (texto gerado até agora), result (AskResponse no fim), error }.
  startAsk(message: string, strategy?: AskStrategy, sourceRoot?: string): Promise<{ ask_id: string }>
  pollAsk(askId: string): Promise<AskProgress>
  warmAnswerModel(): Promise<{ ok: boolean; started: boolean }>  // carrega o modelo local antes da 1ª pergunta
}
```

## Discovery de modelos de resposta

O frontend nao consulta Ollama, LM Studio ou OpenAI-compatible diretamente. Ele chama
`listAnswerModels()` no bridge local e recebe payload seguro:

```ts
type ModelDiscoveryStatus =
  | 'ok'
  | 'not_applicable'
  | 'offline'
  | 'unauthorized'
  | 'error'

interface ModelInfo {
  id: string
  label: string
  provider: string
  details: Record<string, unknown>
}

interface ModelDiscoveryResult {
  provider: string
  base_url: string | null
  status: ModelDiscoveryStatus
  models: ModelInfo[]
  latency_ms: number
  cached: boolean
  message: string | null
}
```

Regras:

1. `extractive` retorna `not_applicable`, sem rede.
2. Ollama usa endpoint nativo `/api/tags`, mesmo quando o chat usa `/v1`.
3. LM Studio e OpenAI-compatible usam `/models`.
4. servidor offline retorna `offline`, sem traceback.
5. API key nunca aparece no payload.
6. escolher modelo na UI preenche draft de `answer_model`; salvar continua sendo acao separada.

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
