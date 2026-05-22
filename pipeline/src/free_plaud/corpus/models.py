from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field


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
    status: Literal['success', 'failed']
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
    status: Literal['success', 'partial', 'failed']
    total_found: int
    indexed_count: int
    failed_count: int
    skipped_count: int
    results: list[CorpusIndexResult] = Field(default_factory=list)
    skipped: list[CorpusSkippedPath] = Field(default_factory=list)


class CorpusStatusResult(BaseModel):
    """Diagnostico de consistencia entre SQLite e Chroma."""

    sqlite_path: str
    vector_store_dir: str
    vector_collection_name: str
    notes_count: int
    sqlite_chunks_count: int
    vector_chunks_count: int
    stale_vector_chunks_count: int
    missing_vector_chunks_count: int
    orphan_vector_note_ids: list[str] = Field(default_factory=list)
    stale_vector_chunk_ids: list[str] = Field(default_factory=list)
    missing_vector_chunk_ids: list[str] = Field(default_factory=list)
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
    status: Literal['preview', 'success', 'partial', 'failed']
    before_status: CorpusStatusResult
    reset: CorpusResetResult | None = None
    index_result: CorpusIndexBatchResult | None = None
    after_status: CorpusStatusResult | None = None
    error_code: str | None = None
    message: str | None = None
