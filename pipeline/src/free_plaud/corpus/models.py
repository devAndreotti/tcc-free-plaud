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
