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

// No app (build de produção) o PyWebView injeta a API depois do bundle e avisa com 'pywebviewready'.
// As chamadas esperam esse aviso: sem isso, as da abertura caíam no mock (vaults e números de exemplo na tela).
// Em dev e nos testes (navegador, Vitest, Playwright) não há PyWebView e o mock responde na hora.
let desktopReady: Promise<boolean> | null = null;
const whenDesktopReady = (): Promise<boolean> => {
  if (isDesktopApp() || import.meta.env.DEV) return Promise.resolve(isDesktopApp());
  desktopReady ??= new Promise((resolve) => {
    window.addEventListener('pywebviewready', () => resolve(isDesktopApp()), { once: true });
  });
  return desktopReady;
};

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

/** Resultado da indexação de um arquivo solto na área de soltar da Fila. */
export interface DroppedFileEvent {
  name: string;
  source_path: string;
  status: 'indexed' | 'unchanged' | 'failed' | 'removed';
  chunks: number;
  error_code: string | null;
  message: string | null;
}

/** Quais nomes entraram na fila e quais ainda não tinham caminho conhecido pelo backend. */
export interface DroppedFilesEnqueueResult {
  queued: string[];
  missing: string[];
}

export interface IndexVaultResult {
  ok: boolean;
  status: string;
  total_found: number;
  indexed_count: number;
  unchanged_count: number;
  removed_count: number;
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

/** Arquivo que a indexação da vault pula (Fila: "Ignorar"). */
export interface IgnoredPath {
  path: string;
  reason: string | null;
  ignored_at: string;
}

/** Resultado de "Tentar de novo" por arquivo (status: indexed | unchanged | failed). */
export interface RetryIndexResult {
  ok: boolean;
  results: { name: string; source_path: string; status: string; chunks: number; error_code: string | null; message: string | null }[];
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
  /** Explicação da opção (Extractive, Ollama, Auto, CPU, CUDA...). */
  description?: string | null;
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
  ndcg_at_10?: number;
  duration_ms: number;
  avg_query_latency_ms: number;
  p50_query_latency_ms?: number;
  p95_query_latency_ms?: number;
  /** Intervalo bootstrap de 95%: [inferior, superior]. */
  mrr_ci?: [number, number] | null;
  recall_at_5_ci?: [number, number] | null;
  /** Só na passada no corpus (benchmark/metrics.py: abstention_metrics + answered_positive_rate). */
  abstention?: Record<'accuracy' | 'precision' | 'recall' | 'f1' | 'support' | 'answered_positive_rate', number> | null;
}

/** Todas as notas da suite num corpus só, buscadas como o chat busca (runners.py: BenchmarkCorpusResult). */
export interface BenchmarkCorpusResult {
  note_count: number;
  positive_count: number;
  negative_count: number;
  retrieval_depth: number;
  summaries: Record<string, BenchmarkStrategySummary>;
}

export interface BenchmarkCompareResult {
  ok: boolean;
  comparison_id: string;
  suite_name: string;
  summaries: Record<string, BenchmarkStrategySummary>;
  corpus?: BenchmarkCorpusResult | null;
  json_report_path: string;
  csv_report_path: string;
  settings_snapshot: BenchmarkSettingsSnapshot | null;
}

export type AskStrategy = 'hybrid' | 'vector' | 'lexical';

/** Pasta indexada do corpus com notas (corpus/service.py: raiz gravada na indexação). */
export interface CorpusRoot {
  root: string;
  notes_count: number;
}

/** Resultado de tirar uma pasta do corpus (UI/main.py: removeCorpusRoot). Não apaga arquivos do disco. */
export interface CorpusRootRemoveResult {
  ok: boolean;
  status?: string;
  removed_notes?: number;
  message?: string;
}

/** Ícones de vault: ids do conjunto de Icons.tsx (sem o sufixo "Icon"). Espelha escolio/app/vaults.py. */
export type VaultIconId = 'notes' | 'ask' | 'graph' | 'layers' | 'chart' | 'sparkle' | 'stars' | 'code' | 'folder' | 'mic' | 'vault' | 'file';
export type VaultColor = 'violet' | 'blue' | 'green' | 'amber' | 'rose' | 'teal' | 'slate';

/** Vault: corpus independente (SQLite + Chroma + pastas de origem). */
export interface Vault {
  id: string;
  name: string;
  icon: VaultIconId;
  color: VaultColor;
  folders: string[];
  embedding_model: string | null;
  created_at: string;
  sqlite_path: string | null;
  vector_store_dir: string | null;
  note_count?: number;
  /** Pastas indexadas no banco da vault, com as notas de cada uma (listVaults). */
  roots?: CorpusRoot[];
}

export interface VaultList {
  active: string;
  vaults: Vault[];
}

export interface VaultPatch {
  name?: string;
  icon?: VaultIconId;
  color?: VaultColor;
  folders?: string[];
}

/** Resultado de criar, editar, excluir ou trocar vault (UI/main.py). */
export interface VaultMutationResult {
  ok: boolean;
  message?: string;
  vault?: Vault;
  active?: string;
}

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
  /** Modelo configurado no provedor generativo (ex.: qchat). */
  answer_model?: string;
  /** true quando `answer` foi escrito pela IA e passou na validação contra os trechos. */
  generated?: boolean;
}

/** Provedor, modelo e URL que estão na tela de Configurações, ainda sem salvar. */
export interface AnswerDraft {
  provider?: string;
  model?: string;
  baseUrl?: string;
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
  askCorpus?: (message: string, strategy?: AskStrategy, sourceRoot?: string) => Promise<AskResult>;

  /** Pastas indexadas com notas, para o seletor de pasta do chat. */
  listCorpusRoots?: () => Promise<CorpusRoot[]>;

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

  /** Indexa no corpus os arquivos soltos na área de soltar (pelo nome; o caminho fica no Python). */
  indexDroppedFiles?: (names: string[]) => Promise<DroppedFilesEnqueueResult>;

  /** Drena os resultados da indexação de arquivos soltos. */
  pollDroppedFiles?: () => Promise<DroppedFileEvent[]>;

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

  /** Testa provider LLM com prompt sintetico, sem usar corpus; null usa o valor salvo. */
  testAnswerProvider?: (
    provider?: string | null,
    model?: string | null,
    baseUrl?: string | null
  ) => Promise<AnswerProviderTestResult>;

  /** Lista modelos expostos pelo provider LLM (o salvo ou o passado); null usa o valor salvo. */
  listAnswerModels?: (provider?: string | null, baseUrl?: string | null) => Promise<ModelDiscoveryResult>;

  /** Salva ou remove ESCOLIO_ANSWER_API_KEY em pipeline/.env. */
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

  /** Tira a pasta do corpus (notas e raiz), exigindo 'REMOVER'. Não apaga arquivos do disco. */
  removeCorpusRoot?: (root: string, confirmation: string) => Promise<CorpusRootRemoveResult>;
  listIgnoredPaths?: () => Promise<IgnoredPath[]>;
  ignoreIndexPaths?: (paths: string[]) => Promise<{ ok: boolean; ignored?: number; removed_notes?: number; message?: string }>;
  unignoreIndexPaths?: (paths: string[]) => Promise<{ ok: boolean; restored?: number; queued?: number; message?: string }>;
  retryIndexPaths?: (paths: string[]) => Promise<RetryIndexResult>;
  openIndexPath?: (path: string, reveal: boolean) => Promise<{ ok: boolean; message?: string }>;

  /** Vaults cadastradas, com a ativa e a contagem de notas de cada uma. */
  listVaults?: () => Promise<VaultList>;
  createVault?: (name: string, icon: VaultIconId, color: VaultColor, folders: string[]) => Promise<VaultMutationResult>;
  updateVault?: (vaultId: string, patch: VaultPatch) => Promise<VaultMutationResult>;
  /** Exclui a vault; `confirm` precisa ser o nome dela. Nunca apaga pastas de origem. */
  deleteVault?: (vaultId: string, confirm: string) => Promise<VaultMutationResult>;
  selectVault?: (vaultId: string) => Promise<VaultMutationResult>;

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

const MOCK_CORPUS_ROOTS: CorpusRoot[] = [
  { root: 'D:\\Notas\\Obsidian', notes_count: 42 },
  { root: 'D:\\Notas\\Culinaria', notes_count: 7 },
];

const MOCK_CITATIONS: AskCitation[] = [
  {
    note_id: 'arquitetura--3f9a1c',
    note_version: 1,
    chunk_id: 'arquitetura--3f9a1c::v1::ofs-000680-001480::9a41',
    snippet: 'O id de um chunk junta o id da nota, a versão e o deslocamento no texto.',
    source_path: 'D:\\Notas\\Obsidian\\Projetos\\escolio\\Arquitetura do índice.md',
    char_start: 680,
    char_end: 1480,
  },
  {
    note_id: 'arquitetura--3f9a1c',
    note_version: 1,
    chunk_id: 'arquitetura--3f9a1c::v1::ofs-001360-002160::77c0',
    snippet: 'Se o hash não mudou desde a última indexação, a nota entra como inalterada.',
    source_path: 'D:\\Notas\\Obsidian\\Projetos\\escolio\\Arquitetura do índice.md',
    char_start: 1360,
    char_end: 2160,
  },
  {
    note_id: 'pipeline--b21e07',
    note_version: 2,
    chunk_id: 'pipeline--b21e07::v2::ofs-000000-000800::1c3d',
    snippet: 'Notas alteradas voltam para a fila e passam de novo pelo chunking.',
    source_path: 'D:\\Notas\\Obsidian\\Projetos\\escolio\\Pipeline de ingestão.md',
    char_start: 0,
    char_end: 800,
  },
];

// Provedor e modelo de resposta do modo navegador; Salvar em Configurações › IA muda os dois.
const mockAnswer = { provider: 'extractive', model: 'qwen2.5:3b' };

const MOCK_LOCAL_MODELS: ModelInfo[] = [
  { id: 'qchat:latest', label: 'qchat:latest', provider: 'ollama', details: { parameter_size: '3.1B', quantization_level: 'Q4_K_M', size: 1929912432 } },
  { id: 'qwen2.5:3b', label: 'qwen2.5:3b', provider: 'ollama', details: { parameter_size: '3.1B', quantization_level: 'Q4_K_M', size: 1929912432 } },
  { id: 'qwen2.5-coder:3b', label: 'qwen2.5-coder:3b', provider: 'ollama', details: { parameter_size: '3.1B', quantization_level: 'Q4_K_M', size: 1929912461 } },
  { id: 'deepseek-r1:1.5b', label: 'deepseek-r1:1.5b', provider: 'ollama', details: { parameter_size: '1.8B', quantization_level: 'Q4_K_M', size: 1117322768 } },
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
    answer_provider: mockAnswer.provider,
    ...(mockAnswer.provider === 'extractive'
      ? {}
      : {
          answer:
            '(mock) Cada nota guarda uma versão, e o id de cada chunk carrega essa versão. Ao indexar de novo, o hash decide: ' +
            'se o conteúdo não mudou, a nota fica como está; se mudou, ela volta para a fila e é quebrada em chunks outra vez.',
          answer_model: mockAnswer.model,
          generated: true,
          latency_ms: 2400,
        }),
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

// Mesmas explicações do catálogo do backend (settings_specs.py), para o modo navegador.
const MOCK_DEVICE_OPTIONS = [
  { value: 'auto', label: 'Auto', description: 'Usa a placa de vídeo NVIDIA (CUDA) se houver; senão, o processador. A escolha segura.' },
  { value: 'cpu', label: 'CPU', description: 'Roda no processador. Funciona em qualquer PC; mais lento com modelos grandes.' },
  { value: 'cuda', label: 'CUDA', description: 'Roda na placa de vídeo NVIDIA: bem mais rápido, mas exige GPU NVIDIA com CUDA; sem ela, dá erro.' },
];

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

// Notas do grafo no modo navegador; as duas primeiras são as citadas por MOCK_CITATIONS.
const mockVaultNote = (note_id: string, title: string, rel: string): NoteDetail => ({
  note_id,
  title,
  source_type: 'md',
  source_path: `D:\\Notas\\Obsidian\\${rel}`,
  created_at: '2026-10-18T12:00:00-03:00',
  tags: ['md'],
  chunk_count: 1,
  structured_markdown: `# ${title}\n\n(mock) Nota de exemplo do modo navegador.`,
  chunks: [
    { chunk_id: `${note_id}::v1::0000`, chunk_index: 0, char_start: 0, char_end: 42, token_count: 8, snippet: '(mock) Nota de exemplo do modo navegador.' },
  ],
});

const MOCK_VAULT_NOTES: NoteDetail[] = [
  mockVaultNote('arquitetura--3f9a1c', 'Arquitetura do índice', 'Projetos\\escolio\\Arquitetura do índice.md'),
  mockVaultNote('pipeline--b21e07', 'Pipeline de ingestão', 'Projetos\\escolio\\Pipeline de ingestão.md'),
  mockVaultNote('roadmap--5c1d', 'Roadmap', 'Projetos\\escolio\\Roadmap.md'),
  mockVaultNote('benchmark--8e2a', 'Benchmark de busca', 'Projetos\\escolio\\Benchmark de busca.md'),
  mockVaultNote('vlan--11aa', 'VLAN', 'Estudos\\Redes\\VLAN.md'),
  mockVaultNote('mac--22bb', 'Endereço MAC', 'Estudos\\Redes\\Endereço MAC.md'),
  mockVaultNote('ospf--33cc', 'OSPF', 'Estudos\\Redes\\OSPF.md'),
  mockVaultNote('docker--44dd', 'Docker vs Máquinas Virtuais', 'Estudos\\Infra\\Docker vs Maquinas Virtuais.md'),
  mockVaultNote('linux--55ee', 'Distribuições Linux', 'Estudos\\Infra\\Distribuicoes Linux.md'),
  mockVaultNote('zustand--66ff', 'Zustand', 'Estudos\\Front\\Zustand.md'),
  mockVaultNote('diario-29--77aa', 'Segunda-feira, 29 de Junho', 'Diário\\2026-06-29.md'),
  mockVaultNote('diario-30--88bb', 'Terça-feira, 30 de Junho', 'Diário\\2026-06-30.md'),
];

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
  ...MOCK_VAULT_NOTES,
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
  corpus: {
    note_count: 10,
    positive_count: 39,
    negative_count: 10,
    retrieval_depth: 10,
    summaries: {
      lexical: {
        strategy: 'lexical', case_count: 10, query_count: 39, mrr: 0.914, recall_at_3: 0.974, recall_at_5: 0.974,
        recall_at_10: 1, ndcg_at_10: 0.934, duration_ms: 1912, avg_query_latency_ms: 7, p50_query_latency_ms: 6,
        p95_query_latency_ms: 11, mrr_ci: [0.84, 0.97], recall_at_5_ci: [0.92, 1],
        abstention: { accuracy: 0.86, precision: 1, recall: 0.3, f1: 0.46, support: 49, answered_positive_rate: 1 },
      },
      vector: {
        strategy: 'vector', case_count: 10, query_count: 39, mrr: 0.936, recall_at_3: 1, recall_at_5: 1,
        recall_at_10: 1, ndcg_at_10: 0.952, duration_ms: 6328, avg_query_latency_ms: 58, p50_query_latency_ms: 55,
        p95_query_latency_ms: 86, mrr_ci: [0.88, 0.99], recall_at_5_ci: [1, 1],
        abstention: { accuracy: 0.73, precision: 0.36, recall: 0.4, f1: 0.38, support: 49, answered_positive_rate: 0.82 },
      },
      hybrid: {
        strategy: 'hybrid', case_count: 10, query_count: 39, mrr: 0.942, recall_at_3: 0.974, recall_at_5: 1,
        recall_at_10: 1, ndcg_at_10: 0.956, duration_ms: 6033, avg_query_latency_ms: 50, p50_query_latency_ms: 48,
        p95_query_latency_ms: 65, mrr_ci: [0.88, 0.99], recall_at_5_ci: [1, 1],
        abstention: { accuracy: 0.76, precision: 0.42, recall: 0.5, f1: 0.45, support: 49, answered_positive_rate: 0.82 },
      },
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

let mockJobPolls = 0;

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
    message: status === 'running' ? 'Processando Introdução.md' : 'Indexação finalizada.',
  },
  result: status === 'running' ? null : {
    ok: true,
    status: 'success',
    total_found: 5,
    indexed_count: 5,
    unchanged_count: 0,
    removed_count: 0,
    failed_count: 0,
    skipped_count: 0,
  },
  error_code: null,
  message: status === 'running' ? 'Processando Introdução.md' : 'Indexação finalizada.',
  // Exemplos de falhas (modo navegador): templates vazios e um PDF escaneado.
  last_errors:
    status === 'running'
      ? []
      : [
          { source_path: 'C:\\Users\\usuario\\Documents\\Vault (mock)\\Templates\\Mensal.md', message: 'EMPTY_CONTENT', error_code: 'EMPTY_CONTENT' },
          { source_path: 'C:\\Users\\usuario\\Documents\\Vault (mock)\\Templates\\Reunião.md', message: 'EMPTY_CONTENT', error_code: 'EMPTY_CONTENT' },
          { source_path: 'C:\\Users\\usuario\\Documents\\Vault (mock)\\Anexos\\contrato-escaneado.pdf', message: 'PDF_PARSE_FAILED', error_code: 'PDF_PARSE_FAILED' },
        ],
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
    id: 'sensevoice-small',
    engine: 'sensevoice',
    format: 'onnx',
    repo_id: 'csukuangfj/sherpa-onnx-sense-voice-zh-en-ja-ko-yue-2024-07-17',
    revision: 'mock',
    languages: ['zh', 'en', 'ja', 'ko', 'yue'],
    license: 'Apache-2.0',
    files: [{ path: 'model.int8.onnx', size: 239_549_735, sha256: 'mock' }],
    installed: false,
    size_bytes: 239_549_735,
    label: 'SenseVoice Small',
    description: 'Multilíngue (zh/en/ja/ko/yue), boa precisão.',
    speed_tier: 'medio',
    quality_tier: 'boa',
    recommended: false,
    supports_auto_language: false,
    selectable: true,
  },
  {
    id: 'sensevoice-gguf-q8',
    engine: 'catalog-only',
    format: 'gguf',
    repo_id: 'handy-computer/SenseVoiceSmall-gguf',
    revision: 'mock',
    languages: ['zh', 'en', 'ja', 'ko', 'yue'],
    license: 'Apache-2.0',
    files: [{ path: 'model.gguf', size: 252_684_608, sha256: 'mock' }],
    installed: false,
    size_bytes: 252_684_608,
    label: 'SenseVoice GGUF Q8',
    description: 'Variante quantizada; menor, com precisão um pouco menor.',
    speed_tier: 'rapido',
    quality_tier: 'boa',
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

// Arquivos ignorados na indexação (mock).
const MOCK_IGNORED_PATHS: IgnoredPath[] = [];

// ─── Vaults (mock) ──────────────────────────────────────────────────────────
const MOCK_VAULTS: Vault[] = [
  { id: 'obsidian', name: 'Obsidian', icon: 'notes', color: 'violet', folders: ['C:/Notas/Obsidian'], embedding_model: 'chroma-default', created_at: '2026-10-18T12:00:00-03:00', sqlite_path: null, vector_store_dir: null, note_count: 42, roots: [{ root: 'D:\\Notas\\Obsidian', notes_count: 42 }] },
  { id: 'culinaria', name: 'Culinária', icon: 'layers', color: 'amber', folders: ['C:/Notas/Receitas'], embedding_model: 'chroma-default', created_at: '2026-10-18T12:05:00-03:00', sqlite_path: null, vector_store_dir: null, note_count: 7, roots: [{ root: 'D:\\Notas\\Culinaria', notes_count: 7 }] },
];
let mockActiveVaultId = 'obsidian';

const mockVaultId = (name: string): string =>
  name.trim().toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '').replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '') || 'vault';

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
    if ((await whenDesktopReady()) && window.pywebview?.api) {
      // Produção: delega ao backend Python via PyWebView
      return window.pywebview.api.sendMessage(message, attachmentName);
    }
    // Desenvolvimento: usa mock local
    return mockSendMessage(message);
  },

  askCorpus: async (message: string, strategy?: AskStrategy, sourceRoot?: string | null): Promise<AskResult> => {
    if ((await whenDesktopReady()) && window.pywebview?.api.askCorpus) {
      // Sem pasta escolhida, o backend recebe só (message, strategy): corpus inteiro.
      return sourceRoot
        ? window.pywebview.api.askCorpus(message, strategy, sourceRoot)
        : window.pywebview.api.askCorpus(message, strategy);
    }
    // Backend antigo (ou mocks de E2E) só expõem sendMessage: vira resposta sem citações.
    if ((await whenDesktopReady()) && window.pywebview?.api.sendMessage) {
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
    if ((await whenDesktopReady()) && window.pywebview?.api) {
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
    if ((await whenDesktopReady()) && window.pywebview?.api) {
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
    if ((await whenDesktopReady()) && window.pywebview?.api) {
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
    if ((await whenDesktopReady()) && window.pywebview?.api) {
      return window.pywebview.api.loadVaultPath();
    }
    // Mock: sem persistência em dev
    return '';
  },

  indexVault: async (folderPath: string): Promise<IndexVaultResult> => {
    if ((await whenDesktopReady()) && window.pywebview?.api.indexVault) {
      return window.pywebview.api.indexVault(folderPath);
    }
    await new Promise((resolve) => setTimeout(resolve, 700));
    return {
      ok: true,
      status: 'mock',
      total_found: 5,
      indexed_count: 5,
      unchanged_count: 0,
      removed_count: 0,
      failed_count: 0,
      skipped_count: 0,
    };
  },

  startIndexJob: async (folderPath: string, rebuild = false): Promise<IndexJobSnapshot> => {
    if ((await whenDesktopReady()) && window.pywebview?.api.startIndexJob) {
      return window.pywebview.api.startIndexJob(folderPath, rebuild);
    }
    console.debug(`[Bridge Mock] startIndexJob: ${folderPath} rebuild=${String(rebuild)}`);
    await new Promise((resolve) => setTimeout(resolve, 250));
    mockJobPolls = 0;
    return mockIndexJob('running');
  },

  getIndexJob: async (jobId: string): Promise<IndexJobSnapshot> => {
    if ((await whenDesktopReady()) && window.pywebview?.api.getIndexJob) {
      return window.pywebview.api.getIndexJob(jobId);
    }
    console.debug(`[Bridge Mock] getIndexJob: ${jobId}`);
    // O job de exemplo termina na quarta consulta (com as falhas de exemplo).
    mockJobPolls += 1;
    return mockIndexJob(mockJobPolls >= 4 ? 'completed' : 'running');
  },

  cancelIndexJob: async (jobId: string): Promise<IndexJobSnapshot> => {
    if ((await whenDesktopReady()) && window.pywebview?.api.cancelIndexJob) {
      return window.pywebview.api.cancelIndexJob(jobId);
    }
    console.debug(`[Bridge Mock] cancelIndexJob: ${jobId}`);
    return mockIndexJob('cancelled');
  },

  startAudioCapture: async (): Promise<AudioJobSnapshot> => {
    if ((await whenDesktopReady()) && window.pywebview?.api.startAudioCapture) {
      return window.pywebview.api.startAudioCapture();
    }
    console.debug('[Bridge Mock] startAudioCapture');
    await new Promise((resolve) => setTimeout(resolve, 150));
    return mockAudioJob('recording');
  },

  getAudioCapture: async (jobId: string): Promise<AudioJobSnapshot> => {
    if ((await whenDesktopReady()) && window.pywebview?.api.getAudioCapture) {
      return window.pywebview.api.getAudioCapture(jobId);
    }
    console.debug(`[Bridge Mock] getAudioCapture: ${jobId}`);
    return mockAudioJob('completed');
  },

  stopAudioCapture: async (jobId: string): Promise<AudioJobSnapshot> => {
    if ((await whenDesktopReady()) && window.pywebview?.api.stopAudioCapture) {
      return window.pywebview.api.stopAudioCapture(jobId);
    }
    console.debug(`[Bridge Mock] stopAudioCapture: ${jobId}`);
    await new Promise((resolve) => setTimeout(resolve, 400));
    return mockAudioJob('completed');
  },

  cancelAudioCapture: async (jobId: string): Promise<AudioJobSnapshot> => {
    if ((await whenDesktopReady()) && window.pywebview?.api.cancelAudioCapture) {
      return window.pywebview.api.cancelAudioCapture(jobId);
    }
    console.debug(`[Bridge Mock] cancelAudioCapture: ${jobId}`);
    return mockAudioJob('cancelled');
  },

  listVoiceModels: async (): Promise<VoiceModelInfo[]> => {
    if ((await whenDesktopReady()) && window.pywebview?.api.listVoiceModels) {
      return window.pywebview.api.listVoiceModels();
    }
    console.debug('[Bridge Mock] listVoiceModels');
    return MOCK_VOICE_MODELS;
  },

  startVoiceModelDownload: async (modelId: string): Promise<VoiceModelDownloadSnapshot> => {
    if ((await whenDesktopReady()) && window.pywebview?.api.startVoiceModelDownload) {
      return window.pywebview.api.startVoiceModelDownload(modelId);
    }
    console.debug(`[Bridge Mock] startVoiceModelDownload: ${modelId}`);
    await new Promise((resolve) => setTimeout(resolve, 150));
    return mockVoiceModelDownload('downloading', modelId);
  },

  getVoiceModelDownload: async (jobId: string): Promise<VoiceModelDownloadSnapshot> => {
    if ((await whenDesktopReady()) && window.pywebview?.api.getVoiceModelDownload) {
      return window.pywebview.api.getVoiceModelDownload(jobId);
    }
    console.debug(`[Bridge Mock] getVoiceModelDownload: ${jobId}`);
    return mockVoiceModelDownload('completed');
  },

  cancelVoiceModelDownload: async (jobId: string): Promise<VoiceModelDownloadSnapshot> => {
    if ((await whenDesktopReady()) && window.pywebview?.api.cancelVoiceModelDownload) {
      return window.pywebview.api.cancelVoiceModelDownload(jobId);
    }
    console.debug(`[Bridge Mock] cancelVoiceModelDownload: ${jobId}`);
    return mockVoiceModelDownload('cancelled');
  },

  startWatcher: async (folderPath: string): Promise<WatcherStartResult> => {
    if ((await whenDesktopReady()) && window.pywebview?.api.startWatcher) {
      return window.pywebview.api.startWatcher(folderPath);
    }
    console.debug(`[Bridge Mock] startWatcher: ${folderPath}`);
    mockWatcherActive = true;
    mockWatcherDirectory = folderPath;
    return { ok: true, active: true, directory: folderPath };
  },

  stopWatcher: async (): Promise<WatcherStartResult> => {
    if ((await whenDesktopReady()) && window.pywebview?.api.stopWatcher) {
      return window.pywebview.api.stopWatcher();
    }
    console.debug("[Bridge Mock] stopWatcher");
    mockWatcherActive = false;
    mockWatcherDirectory = null;
    return { ok: true, active: false, directory: null };
  },

  getWatcherStatus: async (): Promise<WatcherStatus> => {
    if ((await whenDesktopReady()) && window.pywebview?.api.getWatcherStatus) {
      return window.pywebview.api.getWatcherStatus();
    }
    return { active: mockWatcherActive, directory: mockWatcherDirectory };
  },

  indexDroppedFiles: async (names: string[]): Promise<DroppedFilesEnqueueResult> => {
    if ((await whenDesktopReady()) && window.pywebview?.api.indexDroppedFiles) {
      return window.pywebview.api.indexDroppedFiles(names);
    }
    // Fora do app desktop o navegador não expõe o caminho do arquivo.
    return { queued: [], missing: names };
  },

  pollDroppedFiles: async (): Promise<DroppedFileEvent[]> => {
    if ((await whenDesktopReady()) && window.pywebview?.api.pollDroppedFiles) {
      return window.pywebview.api.pollDroppedFiles();
    }
    return [];
  },

  getBackendSettings: async (): Promise<BackendSettings> => {
    if ((await whenDesktopReady()) && window.pywebview?.api.getBackendSettings) {
      return window.pywebview.api.getBackendSettings();
    }
    return {
      answer_provider: mockAnswer.provider,
      answer_model: mockAnswer.model,
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
          label: 'CPU rápido',
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
          options: MOCK_DEVICE_OPTIONS,
          recommended: 'auto',
        }),
        mockSettingRow({
          index: 2,
          key: 'answer_provider',
          label: 'Provedor de resposta',
          description: 'Quem transforma evidências recuperadas em resposta final.',
          group: 'LLM',
          value_type: 'enum',
          layer: 'simple',
          value: mockAnswer.provider,
          display_value: mockAnswer.provider,
          options: [
            {
              value: 'extractive',
              label: 'Extractive',
              description: 'Sem IA generativa: monta a resposta com trechos das suas notas, cada um com a fonte. Rápido, offline e sem custo.',
            },
            {
              value: 'ollama',
              label: 'Ollama',
              description: 'IA local pelo Ollama (localhost:11434): escreve a resposta a partir dos trechos sem enviar nada para fora. Precisa do Ollama aberto e de um modelo baixado.',
            },
            {
              value: 'lmstudio',
              label: 'LM Studio',
              description: 'IA local pelo servidor do LM Studio (localhost:1234). Mesmo papel do Ollama: privado, mas exige o servidor ligado com um modelo carregado.',
            },
            {
              value: 'openai-compatible',
              label: 'OpenAI-compatible',
              description: 'Qualquer API no padrão OpenAI (OpenAI, OpenRouter, Groq…). Usa a API key e envia os trechos recuperados para o serviço.',
            },
          ],
          recommended: 'extractive',
        }),
        mockSettingRow({
          index: 3,
          key: 'answer_model',
          label: 'Modelo de resposta',
          description: 'Modelo que escreve a resposta. Os de ~3B (como qwen2.5:3b) cabem numa GPU de 4 GB e respondem em segundos; 7B ou mais ficam lentos.',
          group: 'LLM',
          value_type: 'string',
          layer: 'simple',
          value: mockAnswer.model,
          display_value: mockAnswer.model,
          recommended: 'qwen2.5:3b',
        }),
        mockSettingRow({
          index: 3,
          key: 'answer_base_url',
          label: 'URL do provider',
          description: 'Endereço do servidor da IA; vazio usa o padrão do provedor escolhido.',
          group: 'LLM',
          value_type: 'string',
          layer: 'advanced',
          value: null,
          display_value: '',
          recommended: null,
          placeholder: 'http://localhost:11434/v1',
        }),
        mockSettingRow({
          index: 4,
          key: 'retrieval_top_k',
          label: 'Chunks por pergunta',
          description: 'Quantos chunks o Ask recupera para montar evidências e resposta.',
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
          options: MOCK_DEVICE_OPTIONS,
          recommended: 'auto',
        }),
        mockSettingRow({
          index: 8,
          key: 'audio_input_device',
          label: 'Microfone',
          description: 'Dispositivo usado para gravar a pergunta por voz. "Padrão do sistema" segue o microfone padrão do Windows.',
          group: 'Áudio',
          value_type: 'string',
          layer: 'simple',
          value: null,
          display_value: 'vazio',
          options: [
            { value: '', label: 'Padrão do sistema' },
            { value: 'Headset (QCY H3 Pro)', label: 'Headset (QCY H3 Pro)' },
          ],
          recommended: null,
        }),
      ],
    };
  },

  getDoctor: async (): Promise<DoctorReport> => {
    if ((await whenDesktopReady()) && window.pywebview?.api.getDoctor) {
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
    if ((await whenDesktopReady()) && window.pywebview?.api.listSettingsPresets) {
      return window.pywebview.api.listSettingsPresets();
    }
    return [
      {
        key: 'cpu_rapido',
        label: 'CPU rápido',
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
    if ((await whenDesktopReady()) && window.pywebview?.api.previewSettingsPreset) {
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
    if ((await whenDesktopReady()) && window.pywebview?.api.applySettingsPreset) {
      return window.pywebview.api.applySettingsPreset(name);
    }
    const preview = await bridge.previewSettingsPreset(name);
    console.debug(`[Bridge Mock] applySettingsPreset: ${name}`);
    return { ...preview, ok: true };
  },

  testAnswerProvider: async (draft: AnswerDraft = {}): Promise<AnswerProviderTestResult> => {
    if ((await whenDesktopReady()) && window.pywebview?.api.testAnswerProvider) {
      return window.pywebview.api.testAnswerProvider(draft.provider ?? null, draft.model ?? null, draft.baseUrl ?? null);
    }
    await new Promise((resolve) => setTimeout(resolve, 300));
    const provider = draft.provider ?? mockAnswer.provider;
    return {
      provider,
      model: draft.model || mockAnswer.model,
      base_url: draft.baseUrl || null,
      status: provider === 'extractive' ? 'not_applicable' : 'ok',
      latency_ms: provider === 'extractive' ? 0 : 840,
      error: null,
    };
  },

  listAnswerModels: async (draft: AnswerDraft = {}): Promise<ModelDiscoveryResult> => {
    const desktop = await whenDesktopReady();
    const pywebviewApi = globalThis.window?.pywebview?.api;
    if (desktop && pywebviewApi?.listAnswerModels) {
      return pywebviewApi.listAnswerModels(draft.provider ?? null, draft.baseUrl ?? null);
    }
    await new Promise((resolve) => setTimeout(resolve, 250));
    const provider = draft.provider ?? mockAnswer.provider;
    // Modo navegador: Ollama com os modelos de exemplo; LM Studio desligado, para ver o aviso.
    if (provider === 'ollama') {
      return { provider, base_url: 'http://localhost:11434', status: 'ok', models: MOCK_LOCAL_MODELS, latency_ms: 12, cached: false, message: null };
    }
    return {
      provider,
      base_url: provider === 'lmstudio' ? 'http://localhost:1234/v1' : null,
      status: provider === 'lmstudio' ? 'offline' : 'not_applicable',
      models: [],
      latency_ms: 4,
      cached: false,
      message: provider === 'lmstudio' ? 'Servidor indisponivel ou timeout.' : null,
    };
  },

  saveApiKey: async (apiKey: string): Promise<SaveApiKeyResult> => {
    if ((await whenDesktopReady()) && window.pywebview?.api.saveApiKey) {
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
    if ((await whenDesktopReady()) && window.pywebview?.api.saveBackendSetting) {
      return window.pywebview.api.saveBackendSetting(key, value);
    }
    console.debug(`[Bridge Mock] saveBackendSetting: ${key}=${String(value)}`);
    return { ok: true };
  },

  saveBackendSettings: async (values: Record<string, string>): Promise<BackendSettings> => {
    if ((await whenDesktopReady()) && window.pywebview?.api.saveBackendSettings) {
      return window.pywebview.api.saveBackendSettings(values);
    }
    console.debug('[Bridge Mock] saveBackendSettings:', values);
    if (values.answer_provider) mockAnswer.provider = values.answer_provider;
    if (values.answer_model) mockAnswer.model = values.answer_model;
    return bridge.getBackendSettings();
  },

  listCorpusRoots: async (): Promise<CorpusRoot[]> => {
    if ((await whenDesktopReady())) {
      // Backend sem o método devolve lista vazia, sem pastas inventadas.
      return window.pywebview?.api.listCorpusRoots ? window.pywebview.api.listCorpusRoots() : [];
    }
    return MOCK_CORPUS_ROOTS.map((root) => ({ ...root }));
  },

  listNotes: async (): Promise<NoteSummary[]> => {
    if ((await whenDesktopReady()) && window.pywebview?.api.listNotes) {
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
    if ((await whenDesktopReady()) && window.pywebview?.api.getNoteDetail) {
      return window.pywebview.api.getNoteDetail(noteId);
    }
    await new Promise((resolve) => setTimeout(resolve, 180));
    const note = MOCK_NOTES.find((item) => item.note_id === noteId);
    if (!note) throw new Error(`Nota nao encontrada: ${noteId}`);
    return note;
  },

  deleteNote: async (noteId: string, confirmation: string): Promise<NoteDeleteResult> => {
    if ((await whenDesktopReady()) && window.pywebview?.api.deleteNote) {
      return window.pywebview.api.deleteNote(noteId, confirmation);
    }
    if (confirmation !== 'APAGAR') {
      return { ok: false, status: 'confirmation_required', message: 'Digite APAGAR para confirmar.' };
    }
    console.debug(`[Bridge Mock] deleteNote: ${noteId}`);
    return { ok: true, note_id: noteId, deleted_vectors: 2 };
  },

  removeCorpusRoot: async (root: string, confirmation: string): Promise<CorpusRootRemoveResult> => {
    if ((await whenDesktopReady()) && window.pywebview?.api.removeCorpusRoot) {
      return window.pywebview.api.removeCorpusRoot(root, confirmation);
    }
    if (confirmation !== 'REMOVER') {
      return { ok: false, status: 'confirmation_required', message: 'Digite REMOVER para confirmar.' };
    }
    console.debug(`[Bridge Mock] removeCorpusRoot: ${root}`);
    const index = MOCK_CORPUS_ROOTS.findIndex((item) => item.root === root);
    const removed = index >= 0 ? MOCK_CORPUS_ROOTS.splice(index, 1)[0].notes_count : 0;
    return { ok: true, removed_notes: removed };
  },

  // ─── Falhas da Fila: ignorar, voltar a indexar, tentar de novo, abrir ──────
  listIgnoredPaths: async (): Promise<IgnoredPath[]> => {
    if ((await whenDesktopReady()) && window.pywebview?.api.listIgnoredPaths) {
      return window.pywebview.api.listIgnoredPaths();
    }
    return MOCK_IGNORED_PATHS.map((item) => ({ ...item }));
  },

  ignoreIndexPaths: async (paths: string[]) => {
    if ((await whenDesktopReady()) && window.pywebview?.api.ignoreIndexPaths) {
      return window.pywebview.api.ignoreIndexPaths(paths);
    }
    for (const path of paths) {
      if (!MOCK_IGNORED_PATHS.some((item) => item.path === path)) {
        MOCK_IGNORED_PATHS.push({ path, reason: 'usuario', ignored_at: new Date().toISOString() });
      }
    }
    return { ok: true, ignored: paths.length, removed_notes: 0 };
  },

  unignoreIndexPaths: async (paths: string[]) => {
    if ((await whenDesktopReady()) && window.pywebview?.api.unignoreIndexPaths) {
      return window.pywebview.api.unignoreIndexPaths(paths);
    }
    const before = MOCK_IGNORED_PATHS.length;
    const keep = MOCK_IGNORED_PATHS.filter((item) => !paths.includes(item.path));
    MOCK_IGNORED_PATHS.splice(0, MOCK_IGNORED_PATHS.length, ...keep);
    return { ok: true, restored: before - keep.length, queued: 0 };
  },

  retryIndexPaths: async (paths: string[]): Promise<RetryIndexResult> => {
    if ((await whenDesktopReady()) && window.pywebview?.api.retryIndexPaths) {
      return window.pywebview.api.retryIndexPaths(paths);
    }
    const results = paths.map((path) => ({
      name: path.split(/[\\/]/).pop() ?? path,
      source_path: path,
      status: 'failed',
      chunks: 0,
      error_code: 'EMPTY_CONTENT',
      message: 'EMPTY_CONTENT',
    }));
    return { ok: true, results };
  },

  openIndexPath: async (path: string, reveal = false) => {
    if ((await whenDesktopReady()) && window.pywebview?.api.openIndexPath) {
      return window.pywebview.api.openIndexPath(path, reveal);
    }
    console.debug(`[Bridge Mock] openIndexPath: ${path} reveal=${reveal}`);
    return { ok: true };
  },

  listVaults: async (): Promise<VaultList> => {
    if ((await whenDesktopReady()) && window.pywebview?.api.listVaults) {
      return window.pywebview.api.listVaults();
    }
    return { active: mockActiveVaultId, vaults: MOCK_VAULTS.map((vault) => ({ ...vault })) };
  },

  createVault: async (name: string, icon: VaultIconId, color: VaultColor, folders: string[]): Promise<VaultMutationResult> => {
    if ((await whenDesktopReady()) && window.pywebview?.api.createVault) {
      return window.pywebview.api.createVault(name, icon, color, folders);
    }
    if (!name.trim()) {
      return { ok: false, message: 'O nome da vault não pode ser vazio.' };
    }
    const id = mockVaultId(name);
    const vault: Vault = {
      id: MOCK_VAULTS.some((item) => item.id === id) ? `${id}-2` : id,
      name: name.trim(),
      icon,
      color,
      folders,
      embedding_model: 'chroma-default',
      created_at: new Date().toISOString(),
      sqlite_path: null,
      vector_store_dir: null,
      note_count: 0,
    };
    MOCK_VAULTS.push(vault);
    return { ok: true, vault };
  },

  updateVault: async (vaultId: string, patch: VaultPatch): Promise<VaultMutationResult> => {
    if ((await whenDesktopReady()) && window.pywebview?.api.updateVault) {
      return window.pywebview.api.updateVault(vaultId, patch);
    }
    const vault = MOCK_VAULTS.find((item) => item.id === vaultId);
    if (!vault) {
      return { ok: false, message: `vault não encontrada: ${vaultId}` };
    }
    Object.assign(vault, patch);
    return { ok: true, vault: { ...vault } };
  },

  deleteVault: async (vaultId: string, confirm: string): Promise<VaultMutationResult> => {
    if ((await whenDesktopReady()) && window.pywebview?.api.deleteVault) {
      return window.pywebview.api.deleteVault(vaultId, confirm);
    }
    const index = MOCK_VAULTS.findIndex((item) => item.id === vaultId);
    if (index < 0) {
      return { ok: false, message: `vault não encontrada: ${vaultId}` };
    }
    if (MOCK_VAULTS.length === 1) {
      return { ok: false, message: 'Não é possível excluir a única vault.' };
    }
    if (confirm !== MOCK_VAULTS[index].name) {
      return { ok: false, message: 'Digite o nome da vault para confirmar a exclusão.' };
    }
    MOCK_VAULTS.splice(index, 1);
    if (mockActiveVaultId === vaultId) {
      mockActiveVaultId = MOCK_VAULTS[0].id;
    }
    return { ok: true, active: mockActiveVaultId };
  },

  selectVault: async (vaultId: string): Promise<VaultMutationResult> => {
    if ((await whenDesktopReady()) && window.pywebview?.api.selectVault) {
      return window.pywebview.api.selectVault(vaultId);
    }
    const vault = MOCK_VAULTS.find((item) => item.id === vaultId);
    if (!vault) {
      return { ok: false, message: `vault não encontrada: ${vaultId}` };
    }
    mockActiveVaultId = vault.id;
    return { ok: true, vault: { ...vault } };
  },

  reindexNote: async (noteId: string): Promise<NoteReindexResult> => {
    if ((await whenDesktopReady()) && window.pywebview?.api.reindexNote) {
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
    if ((await whenDesktopReady()) && window.pywebview?.api.selectBenchmarkSuite) {
      return window.pywebview.api.selectBenchmarkSuite();
    }
    await new Promise((resolve) => setTimeout(resolve, 250));
    return 'data\\datasets\\suite-mock.json';
  },

  runBenchmarkCompare: async (suitePath: string): Promise<BenchmarkCompareResult> => {
    if ((await whenDesktopReady()) && window.pywebview?.api.runBenchmarkCompare) {
      return window.pywebview.api.runBenchmarkCompare(suitePath);
    }
    console.debug(`[Bridge Mock] runBenchmarkCompare: ${suitePath}`);
    await new Promise((resolve) => setTimeout(resolve, 600));
    return MOCK_BENCHMARK_RESULT;
  },

  /** Indica se o app está rodando dentro do PyWebView (desktop) */
  isDesktop: isDesktopApp,
};
