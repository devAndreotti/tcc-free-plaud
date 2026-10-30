from collections.abc import Callable
from pathlib import Path
from time import perf_counter

from escolio.corpus.cancellation import CancellationToken
from escolio.corpus.models import (
    CorpusCommitMode,
    CorpusIndexBatchResult,
    CorpusIndexProgress,
    CorpusIndexResult,
    ResolvedCorpusCommitMode,
)
from escolio.ingest.loaders import PDF_PARSE_FAILED
from escolio.storage.vector import LocalVectorStore

ProgressCallback = Callable[[CorpusIndexProgress], None]


def emit_progress(
    progress: ProgressCallback | None,
    *,
    phase: str,
    started_at: float,
    current_path: Path | str | None = None,
    total_found: int = 0,
    processed_count: int = 0,
    indexed_count: int = 0,
    unchanged_count: int = 0,
    failed_count: int = 0,
    skipped_count: int = 0,
    warmup_ms: int = 0,
    embedding_ms: int = 0,
    writing_ms: int = 0,
    committed_count: int = 0,
    commit_mode_requested: CorpusCommitMode = 'auto',
    commit_mode_resolved: ResolvedCorpusCommitMode = 'atomic',
    batch_index: int = 0,
    batch_total: int = 0,
    message: str | None = None,
) -> None:
    if progress is None:
        return
    progress(
        CorpusIndexProgress(
            phase=phase,  # type: ignore[arg-type]
            current_path=str(current_path) if current_path else None,
            total_found=total_found,
            processed_count=processed_count,
            indexed_count=indexed_count,
            unchanged_count=unchanged_count,
            failed_count=failed_count,
            skipped_count=skipped_count,
            elapsed_ms=int((perf_counter() - started_at) * 1000),
            warmup_ms=warmup_ms,
            embedding_ms=embedding_ms,
            writing_ms=writing_ms,
            committed_count=committed_count,
            commit_mode_requested=commit_mode_requested,
            commit_mode_resolved=commit_mode_resolved,
            batch_index=batch_index,
            batch_total=batch_total,
            message=message,
        )
    )


def is_cancelled(cancel_token: CancellationToken | None) -> bool:
    return bool(cancel_token and cancel_token.is_cancelled())


def cancelled_batch_result(
    source_path: Path,
    *,
    recursive: bool,
    total_found: int,
    indexed_count: int,
    failed_count: int,
    skipped_count: int,
    results: list[CorpusIndexResult],
    unchanged_count: int = 0,
    commit_mode_requested: CorpusCommitMode = 'auto',
    commit_mode_resolved: ResolvedCorpusCommitMode = 'atomic',
) -> CorpusIndexBatchResult:
    return CorpusIndexBatchResult(
        source_path=str(source_path),
        recursive=recursive,
        status='cancelled',
        total_found=total_found,
        indexed_count=indexed_count,
        failed_count=failed_count,
        skipped_count=skipped_count,
        unchanged_count=unchanged_count,
        commit_mode_requested=commit_mode_requested,
        commit_mode_resolved=commit_mode_resolved,
        results=results,
    )


def unchanged_result(
    note,
    *,
    source_path: Path,
    chunk_ids: list[str],
    vector_store: LocalVectorStore,
    embedding_model: str,
) -> CorpusIndexResult:
    return CorpusIndexResult(
        source_path=str(source_path),
        status='unchanged',
        note_id=note.note_id,
        chunks_indexed=len(chunk_ids),
        embedding_model=embedding_model,
        vector_collection_name=vector_store.collection_name,
        vector_entries_count=vector_store.count(),
        message='Documento sem alterações.',
    )


def failure_result(
    source_path: Path,
    *,
    error_code: str,
    message: str,
    vector_store: LocalVectorStore,
    embedding_model: str | None,
) -> CorpusIndexResult:
    return CorpusIndexResult(
        source_path=str(source_path),
        status='failed',
        chunks_indexed=0,
        embedding_model=embedding_model,
        vector_collection_name=vector_store.collection_name,
        vector_entries_count=vector_store.count(),
        error_code=error_code,
        message=message,
    )


def error_code_for_exception(exc: Exception) -> str:
    if isinstance(exc, OSError):
        return 'INPUT_NOT_FOUND' if isinstance(exc, FileNotFoundError) else exc.__class__.__name__
    if isinstance(exc, ValueError):
        text = str(exc)
        if text == 'EMPTY_CONTENT':
            return 'EMPTY_CONTENT'
        if text == PDF_PARSE_FAILED:
            return PDF_PARSE_FAILED
        if 'Extensão não suportada' in text:
            return 'UNSUPPORTED_MEDIA_TYPE'
    return 'INDEXING_FAILED'


def batch_status(indexed_count: int, failed_count: int, unchanged_count: int = 0) -> str:
    if (indexed_count > 0 or unchanged_count > 0) and failed_count == 0:
        return 'success'
    if indexed_count > 0 or unchanged_count > 0:
        return 'partial'
    return 'failed'
