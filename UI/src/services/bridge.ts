/**
 * bridge.ts
 * ─────────────────────────────────────────────────────────────
 * Camada de comunicação entre o React e o backend Python.
 *
 * Em produção (dentro do PyWebView):
 *   - window.pywebview.api estará disponível
 *   - As chamadas vão direto para métodos da classe Api em main.py
 *
 * Em desenvolvimento (npm run dev no navegador):
 *   - window.pywebview NÃO existe
 *   - As funções retornam respostas simuladas (mock)
 * ─────────────────────────────────────────────────────────────
 */

// Detecta se está rodando dentro do PyWebView (janela desktop).
// Função (não const): o PyWebView injeta window.pywebview de forma assíncrona
// apos o carregamento do bundle, entao o valor precisa ser reavaliado a cada chamada.
const isDesktopApp = (): boolean =>
  typeof window !== 'undefined' && 'pywebview' in window && Boolean(window.pywebview?.api);

// ─── Declaração de tipos da API Python exposta pelo PyWebView ───────────────
/** Metadados de um arquivo Markdown retornado pelo scanVault */
export interface MarkdownNodeRaw {
  id: string;
  name: string;
  path: string;
  size: number;
  modified: string;
}

export interface WatcherStartResult {
  ok: boolean;
  active: boolean;
  directory: string | null;
}

export interface WatcherStatus {
  active: boolean;
  directory: string | null;
}

export interface WatcherIngestionEvent {
  ingestion_id: string;
  correlation_id: string;
  source_path: string;
  source_type: string | null;
  detected_media_type: string | null;
  status: "success" | "failed";
  size_bytes: number;
  content_sha256: string | null;
  error_code: string | null;
  message: string | null;
  warnings: string[];
  created_at: string;
}

export interface IndexVaultResult {
  ok: boolean;
  status: string;
  total_found: number;
  indexed_count: number;
  unchanged_count: number;
  failed_count: number;
  skipped_count: number;
}

export interface IndexJobProgress {
  phase: string;
  current_path: string | null;
  total_found: number;
  processed_count: number;
  indexed_count: number;
  unchanged_count: number;
  failed_count: number;
  skipped_count: number;
  elapsed_ms: number;
  warmup_ms: number;
  embedding_ms: number;
  writing_ms: number;
  committed_count: number;
  commit_mode_requested: string;
  commit_mode_resolved: string;
  batch_index: number;
  batch_total: number;
  message: string | null;
}

export interface IndexJobFileError {
  source_path: string;
  message: string;
  error_code: string | null;
}

export interface IndexJobSnapshot {
  job_id: string;
  status: 'running' | 'success' | 'partial' | 'failed' | 'cancelled' | string;
  source_path: string;
  started_at: string;
  finished_at: string | null;
  progress: IndexJobProgress | null;
  result: IndexVaultResult | null;
  error_code: string | null;
  message: string | null;
  last_errors: IndexJobFileError[];
  cancel_requested: boolean;
  files_per_second: number;
  chunks_per_second: number;
  eta_seconds: number | null;
}

/** Resultado de transcricao retornado ao final de um job de audio concluido */
export interface AudioTranscriptionResult {
  text: string;
  language: string;
  duration_seconds: number;
}

/** Snapshot de um job de gravacao (microfone) + transcricao local */
export interface AudioJobSnapshot {
  job_id: string;
  status: 'recording' | 'queued' | 'transcribing' | 'completed' | 'failed' | 'cancelled' | string;
  source_path: string;
  samples_captured: number;
  error_code: string | null;
  message: string | null;
  result: AudioTranscriptionResult | null;
}

/** Arquivo hash-verificado que compõe um modelo de voz no catálogo. */
export interface VoiceModelFile {
  path: string;
  size: number;
  sha256: string;
}

/** Modelo de voz do catálogo, enriquecido com metadados de UI e estado instalado. */
export interface VoiceModelInfo {
  id: string;
  engine: string;
  format: string;
  repo_id: string;
  revision: string;
  languages: string[];
  license: string;
  files: VoiceModelFile[];
  installed: boolean;
  size_bytes: number;
  label: string;
  description: string;
  speed_tier: 'rapido' | 'medio' | 'lento' | null;
  quality_tier: 'basica' | 'boa' | 'alta' | null;
  recommended: boolean;
  supports_auto_language: boolean;
  /** false para componentes internos (ex.: VAD) — nao deve aparecer como opcao de modelo de transcricao. */
  selectable: boolean;
}

/** Snapshot de um job de download de modelo de voz em background. */
export interface VoiceModelDownloadSnapshot {
  job_id: string;
  model_id: string;
  status: 'downloading' | 'verifying' | 'completed' | 'failed' | 'cancelled' | string;
  bytes_completed: number;
  bytes_total: number;
  error_code: string | null;
  message: string | null;
}

export interface BackendSettings {
  answer_provider: string;
  answer_model: string;
  answer_base_url: string | null;
  answer_api_key_configured: boolean;
  local_env_path: string;
  default_ask_strategy: string;
  notes_count: number;
  sqlite_chunks_count: number;
  vector_chunks_count: number;
  settings_catalog: SettingRow[];
  settings_presets: SettingPreset[];
  doctor?: DoctorReport;
}

export interface SaveApiKeyResult {
  ok: boolean;
  configured: boolean;
  local_env_path: string;
}

export interface SettingOption {
  value: string;
  label: string;
}

export interface SettingRow {
  index: number;
  key: string;
  label: string;
  description: string;
  group: string;
  value_type: 'string' | 'int' | 'float' | 'bool' | 'path' | 'enum' | 'secret';
  layer: 'simple' | 'advanced';
  storage: 'user_settings' | 'local_env';
  value: string | number | boolean | null;
  display_value: string;
  options: SettingOption[];
  recommended: string | number | boolean | null;
  secret: boolean;
  placeholder: string | null;
  warning: string | null;
  local_env_path: string | null;
  min: number | null;
  max: number | null;
}

export interface DoctorCheck {
  code: string;
  status: 'ok' | 'warning' | 'error';
  message: string;
  action: string | null;
  latency_ms: number | null;
  details: Record<string, unknown>;
}

export interface DoctorReport {
  status: 'ok' | 'warning' | 'error';
  checks: DoctorCheck[];
  latency_ms: number;
  ok_count: number;
  warning_count: number;
  error_count: number;
}

export interface SettingPreset {
  key: string;
  label: string;
  description: string;
  values: Record<string, string | number | boolean | null>;
}

export interface SettingPresetChange {
  before: string | number | boolean | null;
  after: string | number | boolean | null;
}

export interface SettingPresetResult {
  ok?: boolean;
  preset: SettingPreset;
  values: Record<string, string | number | boolean | null>;
  changes: Record<string, SettingPresetChange>;
}

export interface AnswerProviderTestResult {
  provider: string;
  model: string;
  base_url: string | null;
  status: 'ok' | 'error' | 'not_applicable';
  latency_ms: number;
  error: string | null;
}

export type ModelDiscoveryStatus =
  | 'ok'
  | 'not_applicable'
  | 'offline'
  | 'unauthorized'
  | 'error';

export interface ModelInfo {
  id: string;
  label: string;
  provider: string;
  details: Record<string, unknown>;
}

export interface ModelDiscoveryResult {
  provider: string;
  base_url: string | null;
  status: ModelDiscoveryStatus;
  models: ModelInfo[];
  latency_ms: number;
  cached: boolean;
  message: string | null;
}

export interface NoteSummary {
  note_id: string;
  title: string;
  source_type: string;
  source_path: string;
  created_at: string;
  tags: string[];
  chunk_count: number;
}

export interface NoteChunkSummary {
  chunk_id: string;
  chunk_index: number;
  char_start: number;
  char_end: number;
  token_count: number;
  snippet: string;
}

export interface NoteDetail extends NoteSummary {
  structured_markdown: string;
  chunks: NoteChunkSummary[];
}

export interface NoteDeleteResult {
  ok: boolean;
  note_id?: string;
  deleted_vectors?: number;
  status?: string;
  message?: string;
}

export interface NoteReindexResult {
  ok: boolean;
  note_id: string;
  status: string;
  chunks_indexed: number;
  message: string | null;
}

export interface BenchmarkSettingsSnapshot {
  embedding_model: string;
  embedding_device: string;
  default_ask_strategy: string;
  retrieval_top_k: number;
  default_chunk_size: number;
  default_chunk_overlap: number;
  answer_provider: string;
  created_at?: string;
}

export interface BenchmarkStrategySummary {
  strategy: string;
  case_count: number;
  query_count: number;
  mrr: number;
  recall_at_3: number;
  recall_at_5: number;
  recall_at_10: number;
  duration_ms: number;
  avg_query_latency_ms: number;
}

export interface BenchmarkCompareResult {
  ok: boolean;
  comparison_id: string;
  suite_name: string;
  summaries: Record<string, BenchmarkStrategySummary>;
  json_report_path: string;
  csv_report_path: string;
  settings_snapshot: BenchmarkSettingsSnapshot | null;
}

export type AskStrategy = 'hybrid' | 'vector' | 'lexical';

/** Trecho do corpus que sustenta uma resposta (retrieval/models.py: Citation). */
export interface AskCitation {
  note_id: string;
  note_version: number;
  chunk_id: string;
  snippet: string;
  source_path: string | null;
  char_start: number;
  char_end: number;
}

/** Afirmação da resposta com as citações que a apoiam, direta ou parcialmente. */
export interface AskClaim {
  text: string;
  citations: AskCitation[];
  support_level: 'direct' | 'partial';
}

/** Resposta estruturada do ask (AskResponse + estratégia, top-k e provedor usados). */
export interface AskResult {
  query: string;
  status: 'answer' | 'no_answer';
  no_answer: boolean;
  answer: string | null;
  claims: AskClaim[];
  citations: AskCitation[];
  limitations: string[];
  reason_for_no_answer: string | null;
  latency_ms: number;
  strategy?: string;
  top_k?: number;
  answer_provider?: string;
}

interface PythonApi {
  /**
   * Envia mensagem do usuário para o backend Python.
   * @param message   Texto digitado pelo usuário
   * @param attachment Nome do arquivo anexado (opcional)
   * @returns         Resposta gerada pelo backend
   */
  sendMessage: (message: string, attachment?: string) => Promise<string>;

  /** Pergunta ao corpus e devolve a resposta estruturada, com citações por afirmação. */
  askCorpus?: (message: string, strategy?: AskStrategy) => Promise<AskResult>;

  /**
   * Abre o seletor nativo de pasta do sistema operacional.
   * @returns Caminho absoluto da pasta selecionada, ou string vazia se cancelado
   */
  selectFolder: () => Promise<string>;

  /**
   * Varre a pasta do vault recursivamente e retorna metadados dos arquivos .md.
   * @param folderPath Caminho absoluto da pasta do vault
   * @returns Lista de objetos com id, name, path, size e modified
   */
  scanVault: (folderPath: string) => Promise<MarkdownNodeRaw[]>;

  /**
   * Persiste o caminho do vault em config.json para restaurar na próxima sessão.
   * @param path Caminho absoluto do vault (string vazia para limpar)
   * @returns true em caso de sucesso
   */
  saveVaultPath: (path: string) => Promise<boolean>;

  /**
   * Carrega o caminho do vault salvo na sessão anterior.
   * @returns Caminho salvo, ou string vazia se nunca foi configurado
   */
  loadVaultPath: () => Promise<string>;

  /** Indexa a pasta selecionada no corpus local do backend. */
  indexVault?: (folderPath: string) => Promise<IndexVaultResult>;

  /** Inicia monitoramento continuo de uma pasta para auto-ingestao de novos arquivos. */
  startWatcher?: (folderPath: string) => Promise<WatcherStartResult>;

  /** Para o monitoramento continuo ativo. */
  stopWatcher?: () => Promise<WatcherStartResult>;

  /** Consulta se ha monitoramento ativo e qual pasta esta sendo observada. */
  getWatcherStatus?: () => Promise<WatcherStatus>;

  /** Drena eventos de ingestao capturados pelo watcher desde a ultima consulta. */
  pollWatcherEvents?: () => Promise<WatcherIngestionEvent[]>;

  /** Inicia job assíncrono de indexação de pasta. */
  startIndexJob?: (folderPath: string, rebuild?: boolean) => Promise<IndexJobSnapshot>;

  /** Consulta snapshot de job de indexação. */
  getIndexJob?: (jobId: string) => Promise<IndexJobSnapshot>;

  /** Solicita cancelamento cooperativo de job de indexação. */
  cancelIndexJob?: (jobId: string) => Promise<IndexJobSnapshot>;

  /** Inicia gravação do microfone padrão do sistema. */
  startAudioCapture?: () => Promise<AudioJobSnapshot>;

  /** Consulta status/resultado de um job de gravação+transcrição. */
  getAudioCapture?: (jobId: string) => Promise<AudioJobSnapshot>;

  /** Encerra a gravação e enfileira a transcrição local. */
  stopAudioCapture?: (jobId: string) => Promise<AudioJobSnapshot>;

  /** Cancela gravação ou transcrição em andamento. */
  cancelAudioCapture?: (jobId: string) => Promise<AudioJobSnapshot>;

  /** Lista os modelos de voz do catálogo com metadados de UI e estado instalado. */
  listVoiceModels?: () => Promise<VoiceModelInfo[]>;

  /** Inicia o download em background de um modelo de voz. */
  startVoiceModelDownload?: (modelId: string) => Promise<VoiceModelDownloadSnapshot>;

  /** Consulta progresso/status de um job de download de modelo de voz. */
  getVoiceModelDownload?: (jobId: string) => Promise<VoiceModelDownloadSnapshot>;

  /** Cancela um download de modelo de voz em andamento. */
  cancelVoiceModelDownload?: (jobId: string) => Promise<VoiceModelDownloadSnapshot>;

  /** Retorna resumo das configurações/backend para o modal. */
  getBackendSettings?: () => Promise<BackendSettings>;

  /** Retorna diagnostico estruturado do backend. */
  getDoctor?: () => Promise<DoctorReport>;

  /** Lista presets transacionais de settings. */
  listSettingsPresets?: () => Promise<SettingPreset[]>;

  /** Previsualiza preset sem gravar user_settings.json. */
  previewSettingsPreset?: (name: string) => Promise<SettingPresetResult>;

  /** Aplica preset em uma escrita transacional e limpa runtime. */
  applySettingsPreset?: (name: string) => Promise<SettingPresetResult>;

  /** Testa provider LLM com prompt sintetico, sem usar corpus. */
  testAnswerProvider?: () => Promise<AnswerProviderTestResult>;

  /** Lista modelos expostos pelo provider LLM configurado. */
  listAnswerModels?: () => Promise<ModelDiscoveryResult>;

  /** Salva ou remove FREE_PLAUD_ANSWER_API_KEY em pipeline/.env. */
  saveApiKey?: (apiKey: string) => Promise<SaveApiKeyResult>;

  /** Salva uma setting do catálogo canônico do backend. */
  saveBackendSetting?: (key: string, value: string | number | boolean | null) => Promise<{ ok: boolean }>;

  /** Salva varios settings do catalogo numa unica escrita atomica; retorna o BackendSettings atualizado. */
  saveBackendSettings?: (values: Record<string, string>) => Promise<BackendSettings>;

  /** Lista notas indexadas no corpus. */
  listNotes?: () => Promise<NoteSummary[]>;

  /** Retorna detalhe operacional de uma nota indexada. */
  getNoteDetail?: (noteId: string) => Promise<NoteDetail>;

  /** Remove uma nota do corpus, exigindo confirmação textual. */
  deleteNote?: (noteId: string, confirmation: string) => Promise<NoteDeleteResult>;

  /** Reindexa uma nota a partir do source_path salvo no banco. */
  reindexNote?: (noteId: string) => Promise<NoteReindexResult>;

  /** Abre o seletor nativo para suite.json de benchmark. */
  selectBenchmarkSuite?: () => Promise<string>;

  /** Executa benchmark compare e exporta JSON/CSV com snapshot de settings. */
  runBenchmarkCompare?: (suitePath: string) => Promise<BenchmarkCompareResult>;
}

declare global {
  interface Window {
    pywebview?: {
      api: PythonApi;
    };
  }
}

// ─── Mock de desenvolvimento (substitui o backend em dev mode) ───────────────
const MOCK_RESPONSES = [
  'Modo desenvolvimento no navegador. Para resposta real, rode o app via PyWebView.',
  'Recebi sua mensagem em mock. O backend real responde ao abrir UI/main.py.',
  'Modo mock ativo. Para ver as respostas reais, execute o programa via main.py com PyWebView.',
  'Esta é uma resposta simulada. A integração real usa corpus ask no backend Python.',
];

let mockIndex = 0;

const plainAskResult = (query: string, text: string): AskResult => ({
  query,
  status: 'answer',
  no_answer: false,
  answer: text,
  claims: [],
  citations: [],
  limitations: [],
  reason_for_no_answer: null,
  latency_ms: 0,
});

const MOCK_CITATIONS: AskCitation[] = [
  {
    note_id: 'arquitetura--3f9a1c',
    note_version: 1,
    chunk_id: 'arquitetura--3f9a1c::v1::ofs-000680-001480::9a41',
    snippet: 'O id de um chunk junta o id da nota, a versão e o deslocamento no texto.',
    source_path: 'Projetos/free-plaud/Arquitetura do índice.md',
    char_start: 680,
    char_end: 1480,
  },
  {
    note_id: 'arquitetura--3f9a1c',
    note_version: 1,
    chunk_id: 'arquitetura--3f9a1c::v1::ofs-001360-002160::77c0',
    snippet: 'Se o hash não mudou desde a última indexação, a nota entra como inalterada.',
    source_path: 'Projetos/free-plaud/Arquitetura do índice.md',
    char_start: 1360,
    char_end: 2160,
  },
  {
    note_id: 'pipeline--b21e07',
    note_version: 2,
    chunk_id: 'pipeline--b21e07::v2::ofs-000000-000800::1c3d',
    snippet: 'Notas alteradas voltam para a fila e passam de novo pelo chunking.',
    source_path: 'Projetos/free-plaud/Pipeline de ingestão.md',
    char_start: 0,
    char_end: 800,
  },
];

const mockAskCorpus = async (message: string, strategy: AskStrategy = 'hybrid'): Promise<AskResult> => {
  await new Promise((resolve) => setTimeout(resolve, 700));
  const [c1, c2, c3] = MOCK_CITATIONS;
  return {
    query: message,
    status: 'answer',
    no_answer: false,
    answer: '(mock) Resposta de exemplo montada a partir de três trechos.',
    claims: [
      { text: '(mock) Cada nota indexada guarda uma versão, e o id de cada chunk carrega essa versão.', citations: [c1], support_level: 'direct' },
      { text: 'Na indexação seguinte, o conteúdo é comparado pelo hash: se não mudou, a nota entra como inalterada.', citations: [c2], support_level: 'direct' },
      { text: 'Quando o hash muda, a nota volta para a fila e é quebrada em chunks de novo.', citations: [c3], support_level: 'partial' },
    ],
    citations: MOCK_CITATIONS,
    limitations: ['As fontes não dizem o que acontece com vetores já gravados se a reindexação for interrompida.'],
    reason_for_no_answer: null,
    latency_ms: 700,
    strategy,
    top_k: 5,
    answer_provider: 'extractive',
  };
};

const mockSendMessage = async (message: string): Promise<string> => {
  // Simula delay de rede/processamento
  const delay = 1000 + Math.random() * 800;
  await new Promise((resolve) => setTimeout(resolve, delay));

  console.debug(`[Bridge Mock] Mensagem enviada: "${message}"`);
  const response = MOCK_RESPONSES[mockIndex % MOCK_RESPONSES.length];
  mockIndex += 1;
  return response;
};

type MockSettingRow = Omit<
  SettingRow,
  'storage' | 'options' | 'secret' | 'placeholder' | 'warning' | 'local_env_path' | 'min' | 'max'
> &
  Partial<Pick<SettingRow, 'storage' | 'options' | 'placeholder' | 'warning' | 'local_env_path' | 'min' | 'max'>>;

const mockSettingRow = (row: MockSettingRow): SettingRow => ({
  storage: 'user_settings',
  options: [],
  secret: false,
  placeholder: null,
  warning: null,
  local_env_path: null,
  min: null,
  max: null,
  ...row,
});

const MOCK_NOTES: NoteDetail[] = [
  {
    note_id: 'plataforma-local',
    title: 'Plataforma local',
    source_type: 'md',
    source_path: 'vault/plataforma-local.md',
    created_at: new Date().toISOString(),
    tags: ['md'],
    chunk_count: 2,
    structured_markdown:
      '# Plataforma local\n\nA nota documenta o corpus local, SQLite, Chroma e fluxo RAG com citação.',
    chunks: [
      {
        chunk_id: 'plataforma-local::v1::0000',
        chunk_index: 0,
        char_start: 0,
        char_end: 96,
        token_count: 18,
        snippet: 'A nota documenta o corpus local, SQLite, Chroma e fluxo RAG com citação.',
      },
      {
        chunk_id: 'plataforma-local::v1::0001',
        chunk_index: 1,
        char_start: 84,
        char_end: 148,
        token_count: 12,
        snippet: 'O detalhe operacional aparece aqui para validar a tela Notes.',
      },
    ],
  },
];

const MOCK_BENCHMARK_RESULT: BenchmarkCompareResult = {
  ok: true,
  comparison_id: 'cmp-mock',
  suite_name: 'suite-mock',
  summaries: {
    lexical: {
      strategy: 'lexical',
      case_count: 1,
      query_count: 3,
      mrr: 0.67,
      recall_at_3: 0.67,
      recall_at_5: 0.67,
      recall_at_10: 0.67,
      duration_ms: 32,
      avg_query_latency_ms: 4,
    },
    vector: {
      strategy: 'vector',
      case_count: 1,
      query_count: 3,
      mrr: 0.83,
      recall_at_3: 1,
      recall_at_5: 1,
      recall_at_10: 1,
      duration_ms: 64,
      avg_query_latency_ms: 8,
    },
    hybrid: {
      strategy: 'hybrid',
      case_count: 1,
      query_count: 3,
      mrr: 1,
      recall_at_3: 1,
      recall_at_5: 1,
      recall_at_10: 1,
      duration_ms: 81,
      avg_query_latency_ms: 10,
    },
  },
  json_report_path: 'data\\results\\cmp-mock.json',
  csv_report_path: 'data\\results\\cmp-mock.csv',
  settings_snapshot: {
    embedding_model: 'fake-hash',
    embedding_device: 'cpu',
    default_ask_strategy: 'hybrid',
    retrieval_top_k: 4,
    default_chunk_size: 800,
    default_chunk_overlap: 120,
    answer_provider: 'extractive',
    created_at: new Date().toISOString(),
  },
};

const mockIndexJob = (status: IndexJobSnapshot['status'] = 'running'): IndexJobSnapshot => ({
  job_id: 'idx-mock',
  status,
  source_path: 'C:\\Users\\usuario\\Documents\\Vault (mock)',
  started_at: new Date().toISOString(),
  finished_at: status === 'running' ? null : new Date().toISOString(),
  progress: {
    phase: status === 'running' ? 'embedding' : status,
    current_path: 'C:\\Users\\usuario\\Documents\\Vault (mock)\\Introdução.md',
    total_found: 5,
    processed_count: status === 'running' ? 2 : 5,
    indexed_count: status === 'running' ? 1 : 5,
    unchanged_count: 0,
    failed_count: 0,
    skipped_count: 0,
    elapsed_ms: status === 'running' ? 1200 : 2400,
    warmup_ms: 120,
    embedding_ms: 480,
    writing_ms: 200,
    committed_count: status === 'running' ? 1 : 5,
    commit_mode_requested: 'auto',
    commit_mode_resolved: 'microbatch',
    batch_index: status === 'running' ? 1 : 2,
    batch_total: 2,
    message: status === 'running' ? 'Processando Introdução.md' : 'Indexacao finalizada.',
  },
  result: status === 'running' ? null : {
    ok: true,
    status: 'success',
    total_found: 5,
    indexed_count: 5,
    unchanged_count: 0,
    failed_count: 0,
    skipped_count: 0,
  },
  error_code: null,
  message: status === 'running' ? 'Processando Introdução.md' : 'Indexacao finalizada.',
  last_errors: [],
  cancel_requested: status === 'cancelled',
  files_per_second: 2.08,
  chunks_per_second: 8.33,
  eta_seconds: status === 'running' ? 2 : 0,
});

const mockAudioJob = (status: AudioJobSnapshot['status'] = 'recording'): AudioJobSnapshot => ({
  job_id: 'audio-mock',
  status,
  source_path: 'C:\\Users\\usuario\\AppData\\audio\\recordings\\audio-mock.wav',
  samples_captured: status === 'recording' ? 16_000 : 48_000,
  error_code: null,
  message: null,
  result: status === 'completed' ? {
    text: '(mock) transcrição de exemplo gerada em ambiente de desenvolvimento.',
    language: 'pt',
    duration_seconds: 3,
  } : null,
});

const MOCK_VOICE_MODELS: VoiceModelInfo[] = [
  {
    id: 'whisper-small',
    engine: 'faster-whisper',
    format: 'ctranslate2',
    repo_id: 'Systran/faster-whisper-small',
    revision: 'mock',
    languages: ['pt', 'en', 'es', 'fr', 'de', 'it', 'ja', 'ko', 'zh', 'ru'],
    license: 'MIT',
    files: [{ path: 'model.bin', size: 483_546_902, sha256: 'mock' }],
    installed: true,
    size_bytes: 483_546_902,
    label: 'Whisper Small',
    description: 'Multilíngue, boa precisão geral.',
    speed_tier: 'medio',
    quality_tier: 'alta',
    recommended: true,
    supports_auto_language: true,
    selectable: true,
  },
  {
    id: 'moonshine-tiny-en',
    engine: 'moonshine',
    format: 'onnx',
    repo_id: 'csukuangfj/sherpa-onnx-moonshine-tiny-en-int8',
    revision: 'mock',
    languages: ['en'],
    license: 'MIT',
    files: [{ path: 'encode.int8.onnx', size: 18_249_187, sha256: 'mock' }],
    installed: false,
    size_bytes: 123_967_539,
    label: 'Moonshine Tiny',
    description: 'Só inglês, muito rápido e leve.',
    speed_tier: 'rapido',
    quality_tier: 'basica',
    recommended: false,
    supports_auto_language: false,
    selectable: true,
  },
  {
    id: 'silero-vad',
    engine: 'silero',
    format: 'onnx',
    repo_id: 'snakers4/silero-vad',
    revision: 'mock',
    languages: [],
    license: 'MIT',
    files: [{ path: 'silero_vad.onnx', size: 1_802_437, sha256: 'mock' }],
    installed: false,
    size_bytes: 1_802_437,
    label: 'Detector de fala (VAD)',
    description: 'Componente interno usado para detectar trechos com fala antes de transcrever; necessário para gravar áudio.',
    speed_tier: 'rapido',
    quality_tier: 'alta',
    recommended: false,
    supports_auto_language: false,
    selectable: false,
  },
];

const mockVoiceModelDownload = (
  status: VoiceModelDownloadSnapshot['status'] = 'downloading',
  modelId = 'moonshine-tiny-en'
): VoiceModelDownloadSnapshot => ({
  job_id: 'dl-mock',
  model_id: modelId,
  status,
  bytes_completed: status === 'downloading' ? 60_000_000 : 123_967_539,
  bytes_total: 123_967_539,
  error_code: null,
  message: status === 'completed' ? 'Modelo baixado e verificado.' : null,
});

// ─── Serviço de bridge exportado ─────────────────────────────────────────────
let mockWatcherActive = false;
let mockWatcherDirectory: string | null = null;

export const bridge = {
  /**
   * Envia uma mensagem ao backend Python.
   * Em dev: retorna resposta mock.
   * Em produção: chama window.pywebview.api.sendMessage().
   */
  sendMessage: async (
    message: string,
    attachmentName?: string
  ): Promise<string> => {
    if (isDesktopApp() && window.pywebview?.api) {
      // Produção: delega ao backend Python via PyWebView
      return window.pywebview.api.sendMessage(message, attachmentName);
    }
    // Desenvolvimento: usa mock local
    return mockSendMessage(message);
  },

  askCorpus: async (message: string, strategy?: AskStrategy): Promise<AskResult> => {
    if (isDesktopApp() && window.pywebview?.api.askCorpus) {
      return window.pywebview.api.askCorpus(message, strategy);
    }
    // Backend antigo (ou mocks de E2E) só expõem sendMessage: vira resposta sem citações.
    if (isDesktopApp() && window.pywebview?.api.sendMessage) {
      return plainAskResult(message, await window.pywebview.api.sendMessage(message));
    }
    return mockAskCorpus(message, strategy);
  },

  /**
   * Abre o seletor nativo de pasta (via Python).
   * Em dev: retorna um caminho de exemplo.
   * Em produção: chama window.pywebview.api.selectFolder().
   */
  selectFolder: async (): Promise<string> => {
    if (isDesktopApp() && window.pywebview?.api) {
      return window.pywebview.api.selectFolder();
    }
    // Mock de desenvolvimento: simula delay e retorna caminho fictício
    await new Promise((resolve) => setTimeout(resolve, 600));
    return 'C:\\Users\\usuario\\Documents\\Vault (mock)';
  },

  /**
   * Varre o vault em busca de arquivos .md (via Python).
   * Em dev: retorna lista de arquivos fictícios.
   */
  scanVault: async (folderPath: string): Promise<MarkdownNodeRaw[]> => {
    if (isDesktopApp() && window.pywebview?.api) {
      return window.pywebview.api.scanVault(folderPath);
    }
    // Mock de desenvolvimento
    await new Promise((resolve) => setTimeout(resolve, 900));
    const now = new Date().toISOString();
    return [
      { id: 'mock-1', name: 'Introdução',       path: 'Introdução.md',              size: 1240,  modified: now },
      { id: 'mock-2', name: 'Referencial Teórico', path: 'teoria/Referencial Teórico.md', size: 4800,  modified: now },
      { id: 'mock-3', name: 'Metodologia',      path: 'Metodologia.md',             size: 2300,  modified: now },
      { id: 'mock-4', name: 'Resultados',       path: 'resultados/Resultados.md',   size: 3100,  modified: now },
      { id: 'mock-5', name: 'Conclusão',        path: 'Conclusão.md',               size: 980,   modified: now },
    ];
  },

  /**
   * Salva o caminho do vault no config.json (via Python).
   * Em dev: no-op.
   */
  saveVaultPath: async (path: string): Promise<boolean> => {
    if (isDesktopApp() && window.pywebview?.api) {
      return window.pywebview.api.saveVaultPath(path);
    }
    // Mock: simula sucesso silencioso
    console.debug(`[Bridge Mock] saveVaultPath: "${path}"`);
    return true;
  },

  /**
   * Carrega o caminho do vault salvo anteriormente (via Python).
   * Em dev: retorna string vazia.
   */
  loadVaultPath: async (): Promise<string> => {
    if (isDesktopApp() && window.pywebview?.api) {
      return window.pywebview.api.loadVaultPath();
    }
    // Mock: sem persistência em dev
    return '';
  },

  indexVault: async (folderPath: string): Promise<IndexVaultResult> => {
    if (isDesktopApp() && window.pywebview?.api.indexVault) {
      return window.pywebview.api.indexVault(folderPath);
    }
    await new Promise((resolve) => setTimeout(resolve, 700));
    return {
      ok: true,
      status: 'mock',
      total_found: 5,
      indexed_count: 5,
      unchanged_count: 0,
      failed_count: 0,
      skipped_count: 0,
    };
  },

  startIndexJob: async (folderPath: string, rebuild = false): Promise<IndexJobSnapshot> => {
    if (isDesktopApp() && window.pywebview?.api.startIndexJob) {
      return window.pywebview.api.startIndexJob(folderPath, rebuild);
    }
    console.debug(`[Bridge Mock] startIndexJob: ${folderPath} rebuild=${String(rebuild)}`);
    await new Promise((resolve) => setTimeout(resolve, 250));
    return mockIndexJob('running');
  },

  getIndexJob: async (jobId: string): Promise<IndexJobSnapshot> => {
    if (isDesktopApp() && window.pywebview?.api.getIndexJob) {
      return window.pywebview.api.getIndexJob(jobId);
    }
    console.debug(`[Bridge Mock] getIndexJob: ${jobId}`);
    return mockIndexJob('running');
  },

  cancelIndexJob: async (jobId: string): Promise<IndexJobSnapshot> => {
    if (isDesktopApp() && window.pywebview?.api.cancelIndexJob) {
      return window.pywebview.api.cancelIndexJob(jobId);
    }
    console.debug(`[Bridge Mock] cancelIndexJob: ${jobId}`);
    return mockIndexJob('cancelled');
  },

  startAudioCapture: async (): Promise<AudioJobSnapshot> => {
    if (isDesktopApp() && window.pywebview?.api.startAudioCapture) {
      return window.pywebview.api.startAudioCapture();
    }
    console.debug('[Bridge Mock] startAudioCapture');
    await new Promise((resolve) => setTimeout(resolve, 150));
    return mockAudioJob('recording');
  },

  getAudioCapture: async (jobId: string): Promise<AudioJobSnapshot> => {
    if (isDesktopApp() && window.pywebview?.api.getAudioCapture) {
      return window.pywebview.api.getAudioCapture(jobId);
    }
    console.debug(`[Bridge Mock] getAudioCapture: ${jobId}`);
    return mockAudioJob('completed');
  },

  stopAudioCapture: async (jobId: string): Promise<AudioJobSnapshot> => {
    if (isDesktopApp() && window.pywebview?.api.stopAudioCapture) {
      return window.pywebview.api.stopAudioCapture(jobId);
    }
    console.debug(`[Bridge Mock] stopAudioCapture: ${jobId}`);
    await new Promise((resolve) => setTimeout(resolve, 400));
    return mockAudioJob('completed');
  },

  cancelAudioCapture: async (jobId: string): Promise<AudioJobSnapshot> => {
    if (isDesktopApp() && window.pywebview?.api.cancelAudioCapture) {
      return window.pywebview.api.cancelAudioCapture(jobId);
    }
    console.debug(`[Bridge Mock] cancelAudioCapture: ${jobId}`);
    return mockAudioJob('cancelled');
  },

  listVoiceModels: async (): Promise<VoiceModelInfo[]> => {
    if (isDesktopApp() && window.pywebview?.api.listVoiceModels) {
      return window.pywebview.api.listVoiceModels();
    }
    console.debug('[Bridge Mock] listVoiceModels');
    return MOCK_VOICE_MODELS;
  },

  startVoiceModelDownload: async (modelId: string): Promise<VoiceModelDownloadSnapshot> => {
    if (isDesktopApp() && window.pywebview?.api.startVoiceModelDownload) {
      return window.pywebview.api.startVoiceModelDownload(modelId);
    }
    console.debug(`[Bridge Mock] startVoiceModelDownload: ${modelId}`);
    await new Promise((resolve) => setTimeout(resolve, 150));
    return mockVoiceModelDownload('downloading', modelId);
  },

  getVoiceModelDownload: async (jobId: string): Promise<VoiceModelDownloadSnapshot> => {
    if (isDesktopApp() && window.pywebview?.api.getVoiceModelDownload) {
      return window.pywebview.api.getVoiceModelDownload(jobId);
    }
    console.debug(`[Bridge Mock] getVoiceModelDownload: ${jobId}`);
    return mockVoiceModelDownload('completed');
  },

  cancelVoiceModelDownload: async (jobId: string): Promise<VoiceModelDownloadSnapshot> => {
    if (isDesktopApp() && window.pywebview?.api.cancelVoiceModelDownload) {
      return window.pywebview.api.cancelVoiceModelDownload(jobId);
    }
    console.debug(`[Bridge Mock] cancelVoiceModelDownload: ${jobId}`);
    return mockVoiceModelDownload('cancelled');
  },

  startWatcher: async (folderPath: string): Promise<WatcherStartResult> => {
    if (isDesktopApp() && window.pywebview?.api.startWatcher) {
      return window.pywebview.api.startWatcher(folderPath);
    }
    console.debug(`[Bridge Mock] startWatcher: ${folderPath}`);
    mockWatcherActive = true;
    mockWatcherDirectory = folderPath;
    return { ok: true, active: true, directory: folderPath };
  },

  stopWatcher: async (): Promise<WatcherStartResult> => {
    if (isDesktopApp() && window.pywebview?.api.stopWatcher) {
      return window.pywebview.api.stopWatcher();
    }
    console.debug("[Bridge Mock] stopWatcher");
    mockWatcherActive = false;
    mockWatcherDirectory = null;
    return { ok: true, active: false, directory: null };
  },

  getWatcherStatus: async (): Promise<WatcherStatus> => {
    if (isDesktopApp() && window.pywebview?.api.getWatcherStatus) {
      return window.pywebview.api.getWatcherStatus();
    }
    return { active: mockWatcherActive, directory: mockWatcherDirectory };
  },

  pollWatcherEvents: async (): Promise<WatcherIngestionEvent[]> => {
    if (isDesktopApp() && window.pywebview?.api.pollWatcherEvents) {
      return window.pywebview.api.pollWatcherEvents();
    }
    return [];
  },

  getBackendSettings: async (): Promise<BackendSettings> => {
    if (isDesktopApp() && window.pywebview?.api.getBackendSettings) {
      return window.pywebview.api.getBackendSettings();
    }
    return {
      answer_provider: 'extractive',
      answer_model: 'llama3.1:8b',
      answer_base_url: null,
      answer_api_key_configured: false,
      local_env_path: 'pipeline\\.env',
      default_ask_strategy: 'hybrid',
      notes_count: 0,
      sqlite_chunks_count: 0,
      vector_chunks_count: 0,
      settings_presets: [
        {
          key: 'cpu_rapido',
          label: 'CPU rapido',
          description: 'Notebook sem GPU dedicada; usa embeddings Chroma e busca hybrid.',
          values: {
            embedding_model: 'chroma-default',
            embedding_device: 'cpu',
            retrieval_top_k: 4,
          },
        },
      ],
      doctor: {
        status: 'warning',
        checks: [
          {
            code: 'mock',
            status: 'warning',
            message: 'Doctor mock; abra via PyWebView para diagnostico real.',
            action: null,
            latency_ms: 0,
            details: {},
          },
        ],
        latency_ms: 0,
        ok_count: 0,
        warning_count: 1,
        error_count: 0,
      },
      settings_catalog: [
        mockSettingRow({
          index: 1,
          key: 'embedding_device',
          label: 'Device de embedding',
          description: 'Onde roda o modelo de embedding quando ele suporta device.',
          group: 'Embeddings',
          value_type: 'enum',
          layer: 'simple',
          value: 'cpu',
          display_value: 'cpu',
          options: [
            { value: 'auto', label: 'Auto' },
            { value: 'cpu', label: 'CPU' },
            { value: 'cuda', label: 'CUDA' },
          ],
          recommended: 'auto',
        }),
        mockSettingRow({
          index: 2,
          key: 'answer_provider',
          label: 'Provedor de resposta',
          description: 'Quem transforma evidencias recuperadas em resposta final.',
          group: 'LLM',
          value_type: 'enum',
          layer: 'simple',
          value: 'extractive',
          display_value: 'extractive',
          options: [
            { value: 'extractive', label: 'Extractive' },
            { value: 'ollama', label: 'Ollama' },
            { value: 'lmstudio', label: 'LM Studio' },
            { value: 'openai-compatible', label: 'OpenAI-compatible' },
          ],
          recommended: 'extractive',
        }),
        mockSettingRow({
          index: 3,
          key: 'answer_model',
          label: 'Modelo de resposta',
          description: 'Modelo LLM usado pelo provider generativo.',
          group: 'LLM',
          value_type: 'string',
          layer: 'simple',
          value: 'llama3.1:8b',
          display_value: 'llama3.1:8b',
          recommended: 'llama3.1:8b',
        }),
        mockSettingRow({
          index: 4,
          key: 'retrieval_top_k',
          label: 'Chunks por pergunta',
          description: 'Quantos chunks o Ask recupera para montar evidencias e resposta.',
          group: 'Retrieval',
          value_type: 'int',
          layer: 'advanced',
          value: 4,
          display_value: '4',
          recommended: 4,
        }),
        mockSettingRow({
          index: 5,
          key: 'audio_model',
          label: 'Modelo de transcrição (voz)',
          description: 'Modelo local usado para transcrever o áudio gravado no chat.',
          group: 'Áudio',
          value_type: 'enum',
          layer: 'simple',
          value: 'whisper-small',
          display_value: 'whisper-small',
          options: [
            { value: 'whisper-small', label: 'Whisper Small (multilíngue)' },
            { value: 'moonshine-tiny-en', label: 'Moonshine Tiny (inglês)' },
            { value: 'sensevoice-small', label: 'SenseVoice Small' },
            { value: 'sensevoice-gguf-q8', label: 'SenseVoice GGUF Q8' },
          ],
          recommended: 'whisper-small',
        }),
        mockSettingRow({
          index: 6,
          key: 'audio_language',
          label: 'Idioma da transcrição',
          description: 'Idioma usado pelo modelo de voz. "Automático" só funciona com modelos faster-whisper.',
          group: 'Áudio',
          value_type: 'enum',
          layer: 'simple',
          value: 'pt',
          display_value: 'pt',
          options: [
            { value: 'auto', label: 'Automático (detectar idioma)' },
            { value: 'de', label: 'Alemão' },
            { value: 'en', label: 'Inglês' },
            { value: 'es', label: 'Espanhol' },
            { value: 'fr', label: 'Francês' },
            { value: 'it', label: 'Italiano' },
            { value: 'ja', label: 'Japonês' },
            { value: 'ko', label: 'Coreano' },
            { value: 'pt', label: 'Português' },
            { value: 'ru', label: 'Russo' },
            { value: 'yue', label: 'Cantonês' },
            { value: 'zh', label: 'Chinês' },
          ],
          recommended: 'pt',
        }),
        mockSettingRow({
          index: 7,
          key: 'audio_device',
          label: 'Device de transcrição',
          description: 'Onde roda o modelo de voz quando ele suporta device.',
          group: 'Áudio',
          value_type: 'enum',
          layer: 'simple',
          value: 'auto',
          display_value: 'auto',
          options: [
            { value: 'auto', label: 'Auto' },
            { value: 'cpu', label: 'CPU' },
            { value: 'cuda', label: 'CUDA' },
          ],
          recommended: 'auto',
        }),
      ],
    };
  },

  getDoctor: async (): Promise<DoctorReport> => {
    if (isDesktopApp() && window.pywebview?.api.getDoctor) {
      return window.pywebview.api.getDoctor();
    }
    return {
      status: 'warning',
      checks: [
        {
          code: 'mock',
          status: 'warning',
          message: 'Doctor mock; abra via PyWebView para diagnostico real.',
          action: null,
          latency_ms: 0,
          details: {},
        },
      ],
      latency_ms: 0,
      ok_count: 0,
      warning_count: 1,
      error_count: 0,
    };
  },

  listSettingsPresets: async (): Promise<SettingPreset[]> => {
    if (isDesktopApp() && window.pywebview?.api.listSettingsPresets) {
      return window.pywebview.api.listSettingsPresets();
    }
    return [
      {
        key: 'cpu_rapido',
        label: 'CPU rapido',
        description: 'Notebook sem GPU dedicada; usa embeddings Chroma e busca hybrid.',
        values: {
          embedding_model: 'chroma-default',
          embedding_device: 'cpu',
          retrieval_top_k: 4,
        },
      },
    ];
  },

  previewSettingsPreset: async (name: string): Promise<SettingPresetResult> => {
    if (isDesktopApp() && window.pywebview?.api.previewSettingsPreset) {
      return window.pywebview.api.previewSettingsPreset(name);
    }
    const preset = (await bridge.listSettingsPresets()).find((item) => item.key === name);
    if (!preset) throw new Error(`Preset desconhecido: ${name}`);
    return {
      preset,
      values: preset.values,
      changes: Object.fromEntries(
        Object.entries(preset.values).map(([key, after]) => [key, { before: null, after }])
      ),
    };
  },

  applySettingsPreset: async (name: string): Promise<SettingPresetResult> => {
    if (isDesktopApp() && window.pywebview?.api.applySettingsPreset) {
      return window.pywebview.api.applySettingsPreset(name);
    }
    const preview = await bridge.previewSettingsPreset(name);
    console.debug(`[Bridge Mock] applySettingsPreset: ${name}`);
    return { ...preview, ok: true };
  },

  testAnswerProvider: async (): Promise<AnswerProviderTestResult> => {
    if (isDesktopApp() && window.pywebview?.api.testAnswerProvider) {
      return window.pywebview.api.testAnswerProvider();
    }
    await new Promise((resolve) => setTimeout(resolve, 300));
    return {
      provider: 'extractive',
      model: 'llama3.1:8b',
      base_url: null,
      status: 'not_applicable',
      latency_ms: 0,
      error: null,
    };
  },

  listAnswerModels: async (): Promise<ModelDiscoveryResult> => {
    const pywebviewApi = globalThis.window?.pywebview?.api;
    if (isDesktopApp() && pywebviewApi?.listAnswerModels) {
      return pywebviewApi.listAnswerModels();
    }
    await new Promise((resolve) => setTimeout(resolve, 250));
    return {
      provider: 'ollama',
      base_url: 'http://localhost:11434',
      status: 'ok',
      models: [
        { id: 'llama3.1:8b', label: 'llama3.1:8b', provider: 'ollama', details: { size: 4661224676 } },
        { id: 'mistral:7b', label: 'mistral:7b', provider: 'ollama', details: {} },
      ],
      latency_ms: 12,
      cached: false,
      message: null,
    };
  },

  saveApiKey: async (apiKey: string): Promise<SaveApiKeyResult> => {
    if (isDesktopApp() && window.pywebview?.api.saveApiKey) {
      return window.pywebview.api.saveApiKey(apiKey);
    }
    console.debug('[Bridge Mock] saveApiKey:', apiKey ? '<redacted>' : '<empty>');
    return {
      ok: true,
      configured: apiKey.trim().length > 0,
      local_env_path: 'pipeline\\.env',
    };
  },

  saveBackendSetting: async (
    key: string,
    value: string | number | boolean | null
  ): Promise<{ ok: boolean }> => {
    if (isDesktopApp() && window.pywebview?.api.saveBackendSetting) {
      return window.pywebview.api.saveBackendSetting(key, value);
    }
    console.debug(`[Bridge Mock] saveBackendSetting: ${key}=${String(value)}`);
    return { ok: true };
  },

  saveBackendSettings: async (values: Record<string, string>): Promise<BackendSettings> => {
    if (isDesktopApp() && window.pywebview?.api.saveBackendSettings) {
      return window.pywebview.api.saveBackendSettings(values);
    }
    console.debug('[Bridge Mock] saveBackendSettings:', values);
    return bridge.getBackendSettings();
  },

  listNotes: async (): Promise<NoteSummary[]> => {
    if (isDesktopApp() && window.pywebview?.api.listNotes) {
      return window.pywebview.api.listNotes();
    }
    await new Promise((resolve) => setTimeout(resolve, 250));
    return MOCK_NOTES.map((note) => ({
      note_id: note.note_id,
      title: note.title,
      source_type: note.source_type,
      source_path: note.source_path,
      created_at: note.created_at,
      tags: note.tags,
      chunk_count: note.chunk_count,
    }));
  },

  getNoteDetail: async (noteId: string): Promise<NoteDetail> => {
    if (isDesktopApp() && window.pywebview?.api.getNoteDetail) {
      return window.pywebview.api.getNoteDetail(noteId);
    }
    await new Promise((resolve) => setTimeout(resolve, 180));
    const note = MOCK_NOTES.find((item) => item.note_id === noteId);
    if (!note) throw new Error(`Nota nao encontrada: ${noteId}`);
    return note;
  },

  deleteNote: async (noteId: string, confirmation: string): Promise<NoteDeleteResult> => {
    if (isDesktopApp() && window.pywebview?.api.deleteNote) {
      return window.pywebview.api.deleteNote(noteId, confirmation);
    }
    if (confirmation !== 'APAGAR') {
      return { ok: false, status: 'confirmation_required', message: 'Digite APAGAR para confirmar.' };
    }
    console.debug(`[Bridge Mock] deleteNote: ${noteId}`);
    return { ok: true, note_id: noteId, deleted_vectors: 2 };
  },

  reindexNote: async (noteId: string): Promise<NoteReindexResult> => {
    if (isDesktopApp() && window.pywebview?.api.reindexNote) {
      return window.pywebview.api.reindexNote(noteId);
    }
    await new Promise((resolve) => setTimeout(resolve, 350));
    return {
      ok: true,
      note_id: noteId,
      status: 'success',
      chunks_indexed: 2,
      message: 'Mock reindexed.',
    };
  },

  selectBenchmarkSuite: async (): Promise<string> => {
    if (isDesktopApp() && window.pywebview?.api.selectBenchmarkSuite) {
      return window.pywebview.api.selectBenchmarkSuite();
    }
    await new Promise((resolve) => setTimeout(resolve, 250));
    return 'data\\datasets\\suite-mock.json';
  },

  runBenchmarkCompare: async (suitePath: string): Promise<BenchmarkCompareResult> => {
    if (isDesktopApp() && window.pywebview?.api.runBenchmarkCompare) {
      return window.pywebview.api.runBenchmarkCompare(suitePath);
    }
    console.debug(`[Bridge Mock] runBenchmarkCompare: ${suitePath}`);
    await new Promise((resolve) => setTimeout(resolve, 600));
    return MOCK_BENCHMARK_RESULT;
  },

  /** Indica se o app está rodando dentro do PyWebView (desktop) */
  isDesktop: isDesktopApp,
};
