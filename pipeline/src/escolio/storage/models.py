from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, Field


class ProcessingLogRecord(BaseModel):
    process_id: str
    note_id: str | None = None
    chunk_id: str | None = None
    stage: Literal['ingest', 'parse', 'normalize', 'chunk', 'embed', 'index', 'delete', 'benchmark']
    status: Literal['started', 'success', 'error', 'skipped']
    pipeline_version: str
    config: dict[str, object] = Field(default_factory=dict)
    message: str | None = None
    error_text: str | None = None
    started_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    finished_at: datetime | None = None
    duration_ms: int | None = None


class BenchmarkRunRecord(BaseModel):
    benchmark_run_id: str
    run_name: str
    dataset_name: str
    corpus_snapshot: str
    retrieval_strategy: str
    chunking_strategy: str
    embedding_model: str
    top_k: int
    query_count: int
    pipeline_version: str
    status: Literal['started', 'success', 'error']
    config: dict[str, object] = Field(default_factory=dict)
    metrics: dict[str, object] = Field(default_factory=dict)
    started_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    finished_at: datetime | None = None
    duration_ms: int | None = None
    notes: str | None = None


class BenchmarkQueryRecord(BaseModel):
    benchmark_run_id: str
    query_id: str | None = None
    query_text: str
    expected_note_id: str | None = None
    expected_chunk_id: str | None = None
    expected_ref: str | None = None
    retrieved: list[dict[str, object]] = Field(default_factory=list)
    hit_at_k: Literal[0, 1]
    reciprocal_rank: float | None = None
    latency_ms: int | None = None
    notes: str | None = None
