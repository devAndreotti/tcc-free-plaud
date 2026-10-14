from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

CorpusCommitMode = Literal['auto', 'atomic', 'microbatch']
ResolvedCorpusCommitMode = Literal['atomic', 'microbatch']


class CorpusSkippedPath(BaseModel):
    """Path ignorado durante descoberta de corpus."""

    path: str
    reason: str


class CorpusDiscoveryResult(BaseModel):
    """Resultado de descoberta deterministica de arquivos de corpus."""

    root_path: str
    recursive: bool
    files: list[Path] = Field(default_factory=list)
    skipped: list[CorpusSkippedPath] = Field(default_factory=list)


class CorpusIndexResult(BaseModel):
    """Resultado estavel de indexacao de um arquivo no corpus local."""

    source_path: str
    status: Literal['success', 'failed', 'cancelled', 'unchanged']
    note_id: str | None = None
    chunks_indexed: int = 0
    embedding_model: str | None = None
    vector_collection_name: str | None = None
    vector_entries_count: int = 0
    error_code: str | None = None
    message: str | None = None


class CorpusIndexBatchResult(BaseModel):
    """Resumo de indexacao de um diretorio ou lote de arquivos."""

    source_path: str
    recursive: bool
    status: Literal['success', 'partial', 'failed', 'cancelled']
    total_found: int
    indexed_count: int
    failed_count: int
    skipped_count: int
    unchanged_count: int = 0
    commit_mode_requested: CorpusCommitMode = 'auto'
    commit_mode_resolved: ResolvedCorpusCommitMode = 'atomic'
    results: list[CorpusIndexResult] = Field(default_factory=list)
    skipped: list[CorpusSkippedPath] = Field(default_factory=list)


class CorpusIndexProgress(BaseModel):
    """Evento de progresso da indexacao de corpus."""

    phase: Literal[
        'warmup',
        'discovering',
        'loading',
        'structuring',
        'embedding',
        'writing',
        'committed',
        'finished',
        'failed',
        'cancelled',
    ]
    current_path: str | None = None
    total_found: int = 0
    processed_count: int = 0
    indexed_count: int = 0
    unchanged_count: int = 0
    failed_count: int = 0
    skipped_count: int = 0
    elapsed_ms: int = 0
    warmup_ms: int = 0
    embedding_ms: int = 0
    writing_ms: int = 0
    committed_count: int = 0
    commit_mode_requested: CorpusCommitMode = 'auto'
    commit_mode_resolved: ResolvedCorpusCommitMode = 'atomic'
    batch_index: int = 0
    batch_total: int = 0
    message: str | None = None


class CorpusStatusResult(BaseModel):
    """Diagnostico de consistencia entre SQLite e Chroma."""

    sqlite_path: str
    vector_store_dir: str
    vector_collection_name: str
    notes_count: int
    sqlite_chunks_count: int
    fts_chunks_count: int = 0
    fts_status: Literal['ready', 'missing', 'stale', 'unavailable'] = 'unavailable'
    vector_chunks_count: int
    stale_vector_chunks_count: int
    missing_vector_chunks_count: int
    embedding_model_mismatch_count: int = 0
    orphan_vector_note_ids: list[str] = Field(default_factory=list)
    stale_vector_chunk_ids: list[str] = Field(default_factory=list)
    missing_vector_chunk_ids: list[str] = Field(default_factory=list)
    embedding_model_mismatch_chunk_ids: list[str] = Field(default_factory=list)
    status: Literal['empty', 'clean', 'sqlite_only', 'inconsistent']


class CorpusResetResult(BaseModel):
    """Resultado de limpeza segura do corpus local."""

    dry_run: bool
    would_delete_notes: int
    would_delete_chunks: int
    would_delete_vectors: int
    deleted_notes: int = 0
    deleted_chunks: int = 0
    deleted_vectors: int = 0
    status: Literal['preview', 'reset']


class CorpusRebuildResult(BaseModel):
    """Resultado de rebuild seguro a partir de arquivo ou pasta."""

    source_path: str
    recursive: bool
    dry_run: bool
    status: Literal['preview', 'success', 'partial', 'failed', 'cancelled']
    before_status: CorpusStatusResult
    reset: CorpusResetResult | None = None
    index_result: CorpusIndexBatchResult | None = None
    after_status: CorpusStatusResult | None = None
    error_code: str | None = None
    message: str | None = None


class CorpusIndexBenchmarkRunResult(BaseModel):
    """Metrica operacional de uma rodada de indexacao sintetica."""

    repeat_index: int
    status: Literal['success', 'partial', 'failed', 'cancelled']
    elapsed_ms: int
    files_per_second: float
    chunks_per_second: float
    total_found: int
    indexed_count: int
    unchanged_count: int
    failed_count: int
    skipped_count: int
    chunks_indexed: int
    embedding_calls: int
    commit_mode_resolved: ResolvedCorpusCommitMode = 'atomic'


class CorpusIndexBenchmarkResult(BaseModel):
    """Resultado agregado do benchmark operacional de indexacao."""

    status: Literal['success', 'partial', 'failed', 'cancelled']
    files_requested: int
    supported_files: int
    ignored_files: int
    repeat: int
    embedding_model: str
    commit_mode_requested: CorpusCommitMode = 'auto'
    commit_mode_resolved: ResolvedCorpusCommitMode = 'atomic'
    chunk_size: int
    overlap: int
    total_elapsed_ms: int
    files_per_second: float
    chunks_per_second: float
    indexed_count: int
    unchanged_count: int
    failed_count: int
    skipped_count: int
    chunks_indexed: int
    embedding_calls: int
    runs: list[CorpusIndexBenchmarkRunResult] = Field(default_factory=list)


class CorpusPerfBenchmarkResult(BaseModel):
    """Benchmark operacional persistivel de indexacao e ask."""

    status: Literal['success', 'partial', 'failed', 'cancelled']
    output_path: str
    timestamp: str
    git_commit: str | None = None
    cold_start_ms: int = 0
    python_import_ms: int = 0
    embedder_init_ms: int = 0
    first_embed_ms: int = 0
    warm_embed_ms: int = 0
    first_progress_ms: int = 0
    first_committed_ms: int = 0
    first_askable_ms: int = 0
    total_index_ms: int = 0
    files_per_second: float = 0.0
    chunks_per_second: float = 0.0
    embedding_calls: int = 0
    ask_avg_ms: float = 0.0
    ask_p50_ms: float = 0.0
    ask_p95_ms: float = 0.0
    commit_mode_requested: CorpusCommitMode = 'auto'
    commit_mode_resolved: ResolvedCorpusCommitMode = 'atomic'
    device: str = 'cpu'
    embedding_model: str
    torch_version: str | None = None
    cuda_available: bool | None = None
    gpu_name: str | None = None
    peak_vram_mb: int | None = None
    dataset_shape: dict[str, int] = Field(default_factory=dict)
    settings: dict[str, object] = Field(default_factory=dict)
    environment: dict[str, object] = Field(default_factory=dict)
