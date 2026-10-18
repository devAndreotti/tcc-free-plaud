import json
import sqlite3
import subprocess
import sys
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from statistics import mean, median
from tempfile import TemporaryDirectory
from time import perf_counter

from escolio.app.config import Settings, get_settings
from escolio.app.paths import ensure_runtime_dirs
from escolio.corpus.ask import answer_corpus_with_citations
from escolio.corpus.cancellation import CancellationToken
from escolio.corpus.discovery import discover_corpus_files
from escolio.corpus.models import (
    CorpusCommitMode,
    CorpusIndexBatchResult,
    CorpusIndexBenchmarkResult,
    CorpusIndexBenchmarkRunResult,
    CorpusIndexProgress,
    CorpusIndexResult,
    CorpusPerfBenchmarkResult,
    CorpusRebuildResult,
    CorpusResetResult,
    CorpusStatusResult,
    ResolvedCorpusCommitMode,
)
from escolio.ingest.loaders import PDF_PARSE_FAILED, load_document
from escolio.notes.schemas import Note
from escolio.notes.structurer import structure_document
from escolio.providers.embed import Embedder, get_embedder
from escolio.retrieval.indexer import index_note
from escolio.retrieval.models import Chunk
from escolio.storage.sqlite import (
    count_chunks,
    count_fts_chunks,
    count_notes,
    delete_corpus_notes_and_chunks,
    delete_note_and_chunks,
    get_note_content_hash,
    init_sqlite,
    list_chunk_ids,
    list_chunk_ids_for_note,
    list_note_ids_by_source_path,
    note_chunks_match_config,
    replace_chunks_for_note,
    upsert_note,
)
from escolio.storage.vector import LocalVectorStore

ProgressCallback = Callable[[CorpusIndexProgress], None]


def _emit_progress(
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


def _is_cancelled(cancel_token: CancellationToken | None) -> bool:
    return bool(cancel_token and cancel_token.is_cancelled())


def _cancelled_batch_result(
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


def _unchanged_result(
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
        message='Document unchanged.',
    )


def _failure_result(
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


def _error_code_for_exception(exc: Exception) -> str:
    if isinstance(exc, FileNotFoundError):
        return 'INPUT_NOT_FOUND'
    if isinstance(exc, ValueError):
        text = str(exc)
        if text == 'EMPTY_CONTENT':
            return 'EMPTY_CONTENT'
        if text == PDF_PARSE_FAILED:
            return PDF_PARSE_FAILED
        if 'Extensão não suportada' in text:
            return 'UNSUPPORTED_MEDIA_TYPE'
    return 'INDEXING_FAILED'


class _CountingEmbedder:
    def __init__(self, embedder: Embedder) -> None:
        self._embedder = embedder
        self.model_name = embedder.model_name
        self.calls = 0

    def embed(self, texts: list[str]) -> list[list[float]]:
        self.calls += 1
        return self._embedder.embed(texts)


@dataclass(frozen=True)
class _PendingCorpusIndex:
    source_path: Path
    note: Note
    chunks: list[Chunk]


@dataclass(frozen=True)
class _PreparationFailure:
    source_path: Path
    error_code: str
    message: str


def _benchmark_settings(base: Settings, workspace_dir: Path) -> Settings:
    data_dir = workspace_dir / 'data'
    return Settings(
        environment=base.environment,
        workspace_dir=workspace_dir,
        data_dir=data_dir,
        notes_dir=data_dir / 'corpus' / 'notes',
        datasets_dir=data_dir / 'datasets',
        results_dir=data_dir / 'results',
        sqlite_path=data_dir / 'results' / 'escolio.sqlite3',
        vector_store_dir=data_dir / 'results' / 'vector_store',
        vector_collection_name=base.vector_collection_name,
        embedding_model=base.embedding_model,
        embedding_device=base.embedding_device,
        default_chunk_size=base.default_chunk_size,
        default_chunk_overlap=base.default_chunk_overlap,
        retrieval_top_k=base.retrieval_top_k,
        corpus_commit_mode=base.corpus_commit_mode,
        corpus_micro_batch_chunks=base.corpus_micro_batch_chunks,
        corpus_micro_batch_files=base.corpus_micro_batch_files,
        corpus_atomic_max_files=base.corpus_atomic_max_files,
        corpus_atomic_max_chunks=base.corpus_atomic_max_chunks,
        corpus_embedding_batch_size=base.corpus_embedding_batch_size,
        corpus_upsert_batch_size=base.corpus_upsert_batch_size,
        corpus_index_workers=base.corpus_index_workers,
    )


def _write_index_benchmark_fixture(root: Path, files: int) -> int:
    root.mkdir(parents=True, exist_ok=True)
    for index in range(files):
        suffix = '.txt' if index % 5 == 0 else '.md'
        path = root / f'documento-{index:03d}{suffix}'
        repeated = 12 if index % 4 == 0 else 3
        body = (
            f'# Documento {index:03d}\n\n'
            f'Arquivo sintetico {index:03d} para benchmark de indexacao local-first. '
            'RabbitMQ, runbook SRE e pipeline Bronze Silver Gold aparecem como termos controlados. '
        )
        path.write_text(body * repeated, encoding='utf-8')

    (root / 'ignorado.png').write_text('fora do corpus', encoding='utf-8')
    (root / 'ignorado.docx').write_text('fora do corpus', encoding='utf-8')
    (root / 'ignorado.canvas').write_text('fora do corpus', encoding='utf-8')
    return 3


def _rate(amount: int, elapsed_ms: int) -> float:
    if amount <= 0 or elapsed_ms <= 0:
        return 0.0
    return round(amount / (elapsed_ms / 1000), 3)


def _batched(items: list, batch_size: int):
    for start in range(0, len(items), batch_size):
        yield items[start : start + batch_size]


def _count_pending_chunks(items: list[_PendingCorpusIndex]) -> int:
    return sum(len(item.chunks) for item in items)


def _duplicate_note_ids(items: list[_PendingCorpusIndex]) -> set[str]:
    seen: set[str] = set()
    duplicates: set[str] = set()
    for item in items:
        if item.note.note_id in seen:
            duplicates.add(item.note.note_id)
        seen.add(item.note.note_id)
    return duplicates


def _delete_superseded_source_notes(
    connection: sqlite3.Connection,
    vector_store: LocalVectorStore,
    note: Note,
) -> None:
    for existing_note_id in list_note_ids_by_source_path(connection, note.source_path):
        if existing_note_id == note.note_id:
            continue
        vector_store.delete_by_note_id(existing_note_id)
        delete_note_and_chunks(connection, existing_note_id)


def _resolve_initial_commit_mode(
    requested: CorpusCommitMode,
    *,
    total_files: int,
    settings: Settings,
    source_is_file: bool = False,
) -> ResolvedCorpusCommitMode:
    if requested == 'atomic' or source_is_file:
        return 'atomic'
    if requested == 'microbatch':
        return 'microbatch'
    return 'microbatch' if total_files > settings.corpus_atomic_max_files else 'atomic'


def _should_switch_auto_to_microbatch(
    requested: CorpusCommitMode,
    resolved: ResolvedCorpusCommitMode,
    *,
    pending_items: list[_PendingCorpusIndex],
    settings: Settings,
) -> bool:
    return (
        requested == 'auto'
        and resolved == 'atomic'
        and _count_pending_chunks(pending_items) > settings.corpus_atomic_max_chunks
    )


def _should_flush_microbatch(pending_items: list[_PendingCorpusIndex], *, settings: Settings) -> bool:
    if not pending_items:
        return False
    return (
        len(pending_items) >= settings.corpus_micro_batch_files
        or _count_pending_chunks(pending_items) >= settings.corpus_micro_batch_chunks
    )


def _resolve_embedder_for_index(
    embedder: Embedder | None,
    *,
    settings: Settings,
    progress: ProgressCallback | None,
    started_at: float,
    source_path: Path,
    total_found: int,
    commit_mode_requested: CorpusCommitMode,
    commit_mode_resolved: ResolvedCorpusCommitMode,
) -> tuple[Embedder, int]:
    if embedder is not None:
        return embedder, 0
    _emit_progress(
        progress,
        phase='warmup',
        started_at=started_at,
        current_path=source_path,
        total_found=total_found,
        commit_mode_requested=commit_mode_requested,
        commit_mode_resolved=commit_mode_resolved,
        message=f'Aquecendo embeddings: {settings.embedding_model} device={settings.embedding_device}.',
    )
    warmup_started_at = perf_counter()
    resolved_embedder = get_embedder(settings.embedding_model, device=settings.embedding_device)
    warmup_ms = int((perf_counter() - warmup_started_at) * 1000)
    _emit_progress(
        progress,
        phase='warmup',
        started_at=started_at,
        current_path=source_path,
        total_found=total_found,
        warmup_ms=warmup_ms,
        commit_mode_requested=commit_mode_requested,
        commit_mode_resolved=commit_mode_resolved,
        message=f'Embeddings prontos em {warmup_ms} ms.',
    )
    return resolved_embedder, warmup_ms


@dataclass
class _CommitOutcome:
    results: list[CorpusIndexResult]
    indexed_count: int
    failed_count: int
    embedding_ms: int
    writing_ms: int


def _commit_pending_items(
    pending_items: list[_PendingCorpusIndex],
    *,
    settings: Settings,
    vector_store: LocalVectorStore,
    connection: sqlite3.Connection,
    embedder: Embedder,
    progress: ProgressCallback | None,
    started_at: float,
    source_path: Path,
    total_found: int,
    skipped_count: int,
    unchanged_count: int,
    indexed_count: int,
    failed_count: int,
    commit_mode_requested: CorpusCommitMode,
    commit_mode_resolved: ResolvedCorpusCommitMode,
    batch_index: int,
    batch_total: int,
    cancel_token: CancellationToken | None,
) -> _CommitOutcome:
    """Embeda e grava um grupo de notas ja estruturadas.

    O helper deixa SQLite/Chroma writes no thread principal. Isso evita
    compartilhar conexao SQLite entre workers e limita estado parcial ao lote.
    """
    if not pending_items:
        return _CommitOutcome([], 0, 0, 0, 0)

    duplicates = _duplicate_note_ids(pending_items)
    if duplicates:
        duplicate_list = ', '.join(sorted(duplicates))
        failures = [
            _failure_result(
                item.source_path,
                error_code='DUPLICATE_NOTE_ID',
                message=f'Note_id duplicado no lote: {duplicate_list}. Nada foi gravado.',
                vector_store=vector_store,
                embedding_model=embedder.model_name,
            )
            for item in pending_items
        ]
        return _CommitOutcome(failures, 0, len(failures), 0, 0)

    chunk_pairs = [(item, chunk) for item in pending_items for chunk in item.chunks]
    embeddings_by_chunk_id: dict[str, list[float]] = {}
    embedding_ms = 0
    writing_ms = 0

    for chunk_batch in _batched(chunk_pairs, settings.corpus_embedding_batch_size):
        if _is_cancelled(cancel_token):
            break
        _emit_progress(
            progress,
            phase='embedding',
            started_at=started_at,
            current_path=chunk_batch[0][0].source_path if chunk_batch else source_path,
            total_found=total_found,
            processed_count=indexed_count + unchanged_count + failed_count,
            indexed_count=indexed_count,
            unchanged_count=unchanged_count,
            failed_count=failed_count,
            skipped_count=skipped_count,
            committed_count=indexed_count,
            commit_mode_requested=commit_mode_requested,
            commit_mode_resolved=commit_mode_resolved,
            batch_index=batch_index,
            batch_total=batch_total,
            message=f'Gerando embeddings: lote {batch_index}/{batch_total or 1}, {len(chunk_batch)} chunks.',
        )
        chunks = [chunk for _, chunk in chunk_batch]
        embedding_started_at = perf_counter()
        embeddings = embedder.embed([chunk.chunk_text for chunk in chunks])
        embedding_ms += int((perf_counter() - embedding_started_at) * 1000)
        if len(embeddings) != len(chunks):
            failures = [
                _failure_result(
                    item.source_path,
                    error_code='INDEXING_FAILED',
                    message='A quantidade de embeddings precisa bater com a quantidade de chunks.',
                    vector_store=vector_store,
                    embedding_model=embedder.model_name,
                )
                for item in pending_items
            ]
            return _CommitOutcome(failures, 0, len(failures), embedding_ms, writing_ms)
        for chunk, embedding in zip(chunks, embeddings, strict=True):
            embeddings_by_chunk_id[chunk.chunk_id] = embedding

    if _is_cancelled(cancel_token):
        return _CommitOutcome([], 0, 0, embedding_ms, writing_ms)

    _emit_progress(
        progress,
        phase='writing',
        started_at=started_at,
        current_path=source_path,
        total_found=total_found,
        processed_count=indexed_count + unchanged_count + failed_count,
        indexed_count=indexed_count,
        unchanged_count=unchanged_count,
        failed_count=failed_count,
        skipped_count=skipped_count,
        embedding_ms=embedding_ms,
        committed_count=indexed_count,
        commit_mode_requested=commit_mode_requested,
        commit_mode_resolved=commit_mode_resolved,
        batch_index=batch_index,
        batch_total=batch_total,
        message=f'Gravando lote {batch_index}/{batch_total or 1}: {len(pending_items)} arquivos.',
    )
    writing_started_at = perf_counter()
    for item in pending_items:
        _delete_superseded_source_notes(connection, vector_store, item.note)
        vector_store.delete_by_note_id(item.note.note_id)
    all_chunks = [chunk for item in pending_items for chunk in item.chunks]
    for chunk_batch in _batched(all_chunks, settings.corpus_upsert_batch_size):
        vector_store.upsert_chunks(
            chunk_batch,
            [embeddings_by_chunk_id[chunk.chunk_id] for chunk in chunk_batch],
            embedding_model=embedder.model_name,
        )
    committed_results: list[CorpusIndexResult] = []
    for item in pending_items:
        upsert_note(connection, item.note)
        replace_chunks_for_note(connection, item.note.note_id, item.chunks)
        committed_results.append(
            CorpusIndexResult(
                source_path=str(item.source_path),
                status='success',
                note_id=item.note.note_id,
                chunks_indexed=len(item.chunks),
                embedding_model=embedder.model_name,
                vector_collection_name=vector_store.collection_name,
                vector_entries_count=0,
                message='Nota indexada.',
            )
        )
    writing_ms = int((perf_counter() - writing_started_at) * 1000)
    return _CommitOutcome(committed_results, len(committed_results), 0, embedding_ms, writing_ms)


def get_corpus_status(
    *,
    settings: Settings | None = None,
    connection: sqlite3.Connection | None = None,
    vector_store: LocalVectorStore | None = None,
) -> CorpusStatusResult:
    """Compara chunks persistidos no SQLite com vetores da collection ativa."""
    resolved_settings = settings or get_settings()
    ensure_runtime_dirs(resolved_settings)

    owns_connection = connection is None
    resolved_connection = connection or init_sqlite(resolved_settings.sqlite_path)
    resolved_vector_store = vector_store or LocalVectorStore(
        resolved_settings.vector_store_dir,
        collection_name=resolved_settings.vector_collection_name,
    )

    try:
        sqlite_chunk_ids = list_chunk_ids(resolved_connection)
        sqlite_chunks_count = count_chunks(resolved_connection)
        try:
            fts_chunks_count = count_fts_chunks(resolved_connection)
            if sqlite_chunks_count == fts_chunks_count:
                fts_status = 'ready'
            elif fts_chunks_count == 0:
                fts_status = 'missing'
            else:
                fts_status = 'stale'
        except sqlite3.OperationalError:
            fts_chunks_count = 0
            fts_status = 'unavailable'
        vector_records = resolved_vector_store.list_records()
        vector_chunk_ids = {chunk_id for chunk_id, _ in vector_records}

        stale_chunk_ids = sorted(vector_chunk_ids - sqlite_chunk_ids)
        missing_chunk_ids = sorted(sqlite_chunk_ids - vector_chunk_ids)
        embedding_model_mismatch_chunk_ids = sorted(
            chunk_id
            for chunk_id, metadata in vector_records
            if metadata.get('embedding_model') not in {None, resolved_settings.embedding_model}
        )
        stale_chunk_id_set = set(stale_chunk_ids)
        orphan_note_ids = sorted(
            {
                str(metadata['note_id'])
                for chunk_id, metadata in vector_records
                if chunk_id in stale_chunk_id_set and metadata.get('note_id')
            }
        )

        if not sqlite_chunk_ids and not vector_chunk_ids:
            status = 'empty'
        elif sqlite_chunk_ids and not vector_chunk_ids:
            status = 'sqlite_only'
        elif stale_chunk_ids or missing_chunk_ids or embedding_model_mismatch_chunk_ids:
            status = 'inconsistent'
        else:
            status = 'clean'

        return CorpusStatusResult(
            sqlite_path=str(resolved_settings.sqlite_path),
            vector_store_dir=str(resolved_settings.vector_store_dir),
            vector_collection_name=resolved_vector_store.collection_name,
            notes_count=count_notes(resolved_connection),
            sqlite_chunks_count=sqlite_chunks_count,
            fts_chunks_count=fts_chunks_count,
            fts_status=fts_status,  # type: ignore[arg-type]
            vector_chunks_count=len(vector_chunk_ids),
            stale_vector_chunks_count=len(stale_chunk_ids),
            missing_vector_chunks_count=len(missing_chunk_ids),
            embedding_model_mismatch_count=len(embedding_model_mismatch_chunk_ids),
            orphan_vector_note_ids=orphan_note_ids,
            stale_vector_chunk_ids=stale_chunk_ids,
            missing_vector_chunk_ids=missing_chunk_ids,
            embedding_model_mismatch_chunk_ids=embedding_model_mismatch_chunk_ids,
            status=status,  # type: ignore[arg-type]
        )
    finally:
        if owns_connection:
            resolved_connection.close()


def reset_corpus(
    *,
    settings: Settings | None = None,
    connection: sqlite3.Connection | None = None,
    vector_store: LocalVectorStore | None = None,
    dry_run: bool = True,
) -> CorpusResetResult:
    """Limpa notas/chunks e collection vetorial ativa, preservando benchmarks."""
    resolved_settings = settings or get_settings()
    ensure_runtime_dirs(resolved_settings)

    owns_connection = connection is None
    resolved_connection = connection or init_sqlite(resolved_settings.sqlite_path)
    resolved_vector_store = vector_store or LocalVectorStore(
        resolved_settings.vector_store_dir,
        collection_name=resolved_settings.vector_collection_name,
    )

    try:
        notes_total = count_notes(resolved_connection)
        chunks_total = count_chunks(resolved_connection)
        vectors_total = resolved_vector_store.count()
        if dry_run:
            return CorpusResetResult(
                dry_run=True,
                would_delete_notes=notes_total,
                would_delete_chunks=chunks_total,
                would_delete_vectors=vectors_total,
                status='preview',
            )

        resolved_vector_store.reset()
        deleted_notes, deleted_chunks = delete_corpus_notes_and_chunks(resolved_connection)
        return CorpusResetResult(
            dry_run=False,
            would_delete_notes=notes_total,
            would_delete_chunks=chunks_total,
            would_delete_vectors=vectors_total,
            deleted_notes=deleted_notes,
            deleted_chunks=deleted_chunks,
            deleted_vectors=vectors_total,
            status='reset',
        )
    finally:
        if owns_connection:
            resolved_connection.close()


def benchmark_corpus_indexing(
    *,
    files: int = 100,
    repeat: int = 2,
    settings: Settings | None = None,
    embedder: Embedder | None = None,
    chunk_size: int | None = None,
    overlap: int | None = None,
    commit_mode: CorpusCommitMode | None = None,
) -> CorpusIndexBenchmarkResult:
    """Mede indexacao em corpus sintetico dentro de workspace temporario."""
    if files <= 0:
        raise ValueError('files precisa ser maior que zero.')
    if repeat <= 0:
        raise ValueError('repeat precisa ser maior que zero.')

    resolved_settings = settings or get_settings()
    resolved_embedder = embedder or get_embedder(
        resolved_settings.embedding_model,
        device=resolved_settings.embedding_device,
    )
    counting_embedder = _CountingEmbedder(resolved_embedder)
    resolved_chunk_size = chunk_size or resolved_settings.default_chunk_size
    resolved_overlap = resolved_settings.default_chunk_overlap if overlap is None else overlap
    commit_mode_requested = commit_mode or resolved_settings.corpus_commit_mode

    with TemporaryDirectory(prefix='escolio-corpus-benchmark-', ignore_cleanup_errors=True) as temporary_dir:
        workspace_dir = Path(temporary_dir)
        benchmark_settings = _benchmark_settings(resolved_settings, workspace_dir)
        source_dir = workspace_dir / 'fixture'
        ignored_files = _write_index_benchmark_fixture(source_dir, files)
        total_started_at = perf_counter()
        runs: list[CorpusIndexBenchmarkRunResult] = []

        for repeat_index in range(1, repeat + 1):
            calls_before = counting_embedder.calls
            started_at = perf_counter()
            batch_result = index_corpus_path(
                source_dir,
                settings=benchmark_settings,
                embedder=counting_embedder,
                chunk_size=resolved_chunk_size,
                overlap=resolved_overlap,
                recursive=True,
                commit_mode=commit_mode_requested,
            )
            elapsed_ms = int((perf_counter() - started_at) * 1000)
            chunks_indexed = sum(item.chunks_indexed for item in batch_result.results if item.status == 'success')
            chunks_seen = sum(item.chunks_indexed for item in batch_result.results)
            processed_files = batch_result.indexed_count + batch_result.unchanged_count + batch_result.failed_count
            runs.append(
                CorpusIndexBenchmarkRunResult(
                    repeat_index=repeat_index,
                    status=batch_result.status,
                    elapsed_ms=elapsed_ms,
                    files_per_second=_rate(processed_files, elapsed_ms),
                    chunks_per_second=_rate(chunks_seen, elapsed_ms),
                    total_found=batch_result.total_found,
                    indexed_count=batch_result.indexed_count,
                    unchanged_count=batch_result.unchanged_count,
                    failed_count=batch_result.failed_count,
                    skipped_count=batch_result.skipped_count,
                    chunks_indexed=chunks_indexed,
                    embedding_calls=counting_embedder.calls - calls_before,
                    commit_mode_resolved=batch_result.commit_mode_resolved,
                )
            )

        total_elapsed_ms = int((perf_counter() - total_started_at) * 1000)

    indexed_count = sum(run.indexed_count for run in runs)
    unchanged_count = sum(run.unchanged_count for run in runs)
    failed_count = sum(run.failed_count for run in runs)
    skipped_count = runs[-1].skipped_count if runs else ignored_files
    chunks_indexed = sum(run.chunks_indexed for run in runs)
    processed_files = indexed_count + unchanged_count + failed_count

    if failed_count and (indexed_count or unchanged_count):
        status = 'partial'
    elif failed_count:
        status = 'failed'
    else:
        status = 'success'

    return CorpusIndexBenchmarkResult(
        status=status,  # type: ignore[arg-type]
        files_requested=files,
        supported_files=files,
        ignored_files=ignored_files,
        repeat=repeat,
        embedding_model=counting_embedder.model_name,
        commit_mode_requested=commit_mode_requested,
        commit_mode_resolved=runs[-1].commit_mode_resolved if runs else 'atomic',
        chunk_size=resolved_chunk_size,
        overlap=resolved_overlap,
        total_elapsed_ms=total_elapsed_ms,
        files_per_second=_rate(processed_files, total_elapsed_ms),
        chunks_per_second=_rate(chunks_indexed, total_elapsed_ms),
        indexed_count=indexed_count,
        unchanged_count=unchanged_count,
        failed_count=failed_count,
        skipped_count=skipped_count,
        chunks_indexed=chunks_indexed,
        embedding_calls=counting_embedder.calls,
        runs=runs,
    )


def _git_commit_for_path(path: Path) -> str | None:
    try:
        completed = subprocess.run(
            ['git', 'rev-parse', 'HEAD'],
            cwd=path,
            check=True,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except Exception:
        return None
    commit = completed.stdout.strip()
    return commit or None


def _torch_environment() -> dict[str, object]:
    payload: dict[str, object] = {
        'python': sys.version.split()[0],
        'executable': sys.executable,
    }
    try:
        import torch
    except Exception as exc:
        payload.update(
            {
                'torch_version': None,
                'cuda_available': False,
                'gpu_name': None,
                'torch_error': f'{type(exc).__name__}: {exc}',
            }
        )
        return payload

    cuda_available = bool(torch.cuda.is_available())
    payload.update(
        {
            'torch_version': getattr(torch, '__version__', None),
            'torch_cuda_version': getattr(torch.version, 'cuda', None),
            'cuda_available': cuda_available,
            'gpu_name': torch.cuda.get_device_name(0) if cuda_available else None,
        }
    )
    if cuda_available:
        try:
            payload['peak_vram_mb'] = int(torch.cuda.max_memory_allocated(0) / (1024 * 1024))
        except Exception:
            payload['peak_vram_mb'] = None
    return payload


def _percentile(values: list[int], percentile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = round((len(ordered) - 1) * percentile)
    return float(ordered[index])


def perf_benchmark_corpus(
    *,
    files: int = 100,
    repeat: int = 1,
    ask_repeat: int = 10,
    include_cold_start: bool = False,
    settings: Settings | None = None,
    embedder: Embedder | None = None,
    chunk_size: int | None = None,
    overlap: int | None = None,
    commit_mode: CorpusCommitMode | None = None,
) -> CorpusPerfBenchmarkResult:
    """Roda benchmark pequeno, pergunta no corpus e salva JSON comparavel."""
    if files <= 0:
        raise ValueError('files precisa ser maior que zero.')
    if repeat <= 0:
        raise ValueError('repeat precisa ser maior que zero.')
    if ask_repeat < 0:
        raise ValueError('ask-repeat nao pode ser negativo.')

    resolved_settings = settings or get_settings()
    resolved_chunk_size = chunk_size or resolved_settings.default_chunk_size
    resolved_overlap = resolved_settings.default_chunk_overlap if overlap is None else overlap
    commit_mode_requested = commit_mode or resolved_settings.corpus_commit_mode
    cold_start_ms = 0
    embedder_init_ms = 0
    first_embed_ms = 0
    warm_embed_ms = 0
    base_embedder = embedder

    if base_embedder is None:
        init_started_at = perf_counter()
        base_embedder = get_embedder(resolved_settings.embedding_model, device=resolved_settings.embedding_device)
        embedder_init_ms = int((perf_counter() - init_started_at) * 1000)
        if include_cold_start:
            first_started_at = perf_counter()
            base_embedder.embed(['escolio cold start benchmark'])
            first_embed_ms = int((perf_counter() - first_started_at) * 1000)
            warm_started_at = perf_counter()
            base_embedder.embed(['escolio warm benchmark'])
            warm_embed_ms = int((perf_counter() - warm_started_at) * 1000)
    cold_start_ms = embedder_init_ms + first_embed_ms
    counting_embedder = _CountingEmbedder(base_embedder)

    with TemporaryDirectory(prefix='escolio-corpus-perf-', ignore_cleanup_errors=True) as temporary_dir:
        workspace_dir = Path(temporary_dir)
        benchmark_settings = _benchmark_settings(resolved_settings, workspace_dir)
        source_dir = workspace_dir / 'fixture'
        ignored_files = _write_index_benchmark_fixture(source_dir, files)
        progress_events: list[CorpusIndexProgress] = []
        batch_results: list[CorpusIndexBatchResult] = []
        total_index_ms = 0
        for _ in range(repeat):
            run_events: list[CorpusIndexProgress] = []
            index_started_at = perf_counter()
            batch_result = index_corpus_path(
                source_dir,
                settings=benchmark_settings,
                embedder=counting_embedder,
                chunk_size=resolved_chunk_size,
                overlap=resolved_overlap,
                recursive=True,
                commit_mode=commit_mode_requested,
                progress=run_events.append,
            )
            total_index_ms += int((perf_counter() - index_started_at) * 1000)
            batch_results.append(batch_result)
            if not progress_events:
                progress_events = run_events
        connection = init_sqlite(benchmark_settings.sqlite_path)
        vector_store = LocalVectorStore(
            benchmark_settings.vector_store_dir,
            collection_name=benchmark_settings.vector_collection_name,
        )
        ask_latencies: list[int] = []
        try:
            for _ in range(ask_repeat):
                ask_started_at = perf_counter()
                answer_corpus_with_citations(
                    'RabbitMQ runbook SRE pipeline',
                    connection=connection,
                    vector_store=vector_store,
                    embedder=counting_embedder,
                    strategy='hybrid',
                    top_k=benchmark_settings.retrieval_top_k,
                )
                ask_latencies.append(int((perf_counter() - ask_started_at) * 1000))
        finally:
            connection.close()

    first_progress_ms = progress_events[0].elapsed_ms if progress_events else 0
    first_committed_ms = next(
        (event.elapsed_ms for event in progress_events if event.phase == 'committed' or event.indexed_count > 0),
        0,
    )
    chunks_indexed = sum(
        item.chunks_indexed
        for batch_result in batch_results
        for item in batch_result.results
        if item.status == 'success'
    )
    processed_files = sum(
        batch_result.indexed_count + batch_result.unchanged_count + batch_result.failed_count
        for batch_result in batch_results
    )
    failed_count = sum(batch_result.failed_count for batch_result in batch_results)
    indexed_count = sum(batch_result.indexed_count for batch_result in batch_results)
    unchanged_count = sum(batch_result.unchanged_count for batch_result in batch_results)
    if failed_count and (indexed_count or unchanged_count):
        status = 'partial'
    elif failed_count:
        status = 'failed'
    elif batch_results and any(batch_result.status == 'cancelled' for batch_result in batch_results):
        status = 'cancelled'
    else:
        status = 'success'
    environment = _torch_environment()
    timestamp = datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')
    output_dir = resolved_settings.results_dir / 'corpus_perf'
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f'perf-{timestamp}.json'
    result = CorpusPerfBenchmarkResult(
        status=status,  # type: ignore[arg-type]
        output_path=str(output_path),
        timestamp=timestamp,
        git_commit=_git_commit_for_path(resolved_settings.workspace_dir),
        cold_start_ms=cold_start_ms,
        python_import_ms=0,
        embedder_init_ms=embedder_init_ms,
        first_embed_ms=first_embed_ms,
        warm_embed_ms=warm_embed_ms,
        first_progress_ms=first_progress_ms,
        first_committed_ms=first_committed_ms,
        first_askable_ms=first_committed_ms,
        total_index_ms=total_index_ms,
        files_per_second=_rate(processed_files, total_index_ms),
        chunks_per_second=_rate(chunks_indexed, total_index_ms),
        embedding_calls=counting_embedder.calls,
        ask_avg_ms=round(mean(ask_latencies), 3) if ask_latencies else 0.0,
        ask_p50_ms=float(median(ask_latencies)) if ask_latencies else 0.0,
        ask_p95_ms=_percentile(ask_latencies, 0.95),
        commit_mode_requested=commit_mode_requested,
        commit_mode_resolved=batch_results[0].commit_mode_resolved if batch_results else 'atomic',
        device=resolved_settings.embedding_device,
        embedding_model=counting_embedder.model_name,
        torch_version=environment.get('torch_version') if isinstance(environment.get('torch_version'), str) else None,
        cuda_available=bool(environment.get('cuda_available')),
        gpu_name=environment.get('gpu_name') if isinstance(environment.get('gpu_name'), str) else None,
        peak_vram_mb=environment.get('peak_vram_mb') if isinstance(environment.get('peak_vram_mb'), int) else None,
        dataset_shape={
            'files_requested': files,
            'supported_files': files,
            'ignored_files': ignored_files,
            'chunks_indexed': chunks_indexed,
            'ask_repeat': ask_repeat,
            'repeat': repeat,
        },
        settings={
            'chunk_size': resolved_chunk_size,
            'overlap': resolved_overlap,
            'corpus_embedding_batch_size': resolved_settings.corpus_embedding_batch_size,
            'corpus_upsert_batch_size': resolved_settings.corpus_upsert_batch_size,
            'corpus_micro_batch_chunks': resolved_settings.corpus_micro_batch_chunks,
            'corpus_micro_batch_files': resolved_settings.corpus_micro_batch_files,
            'corpus_index_workers': resolved_settings.corpus_index_workers,
        },
        environment=environment,
    )
    output_path.write_text(json.dumps(result.model_dump(mode='json'), ensure_ascii=True, indent=2), encoding='utf-8')
    return result


def rebuild_corpus(
    path: Path | str,
    *,
    settings: Settings | None = None,
    connection: sqlite3.Connection | None = None,
    vector_store: LocalVectorStore | None = None,
    embedder: Embedder | None = None,
    chunk_size: int | None = None,
    overlap: int | None = None,
    recursive: bool = False,
    dry_run: bool = True,
    commit_mode: CorpusCommitMode | None = None,
    progress: ProgressCallback | None = None,
    cancel_token: CancellationToken | None = None,
) -> CorpusRebuildResult:
    """Reconstroi corpus ativo a partir de arquivo ou diretorio controlado."""
    resolved_settings = settings or get_settings()
    ensure_runtime_dirs(resolved_settings)
    source_path = Path(path).expanduser()

    owns_connection = connection is None
    resolved_connection = connection or init_sqlite(resolved_settings.sqlite_path)
    resolved_vector_store = vector_store or LocalVectorStore(
        resolved_settings.vector_store_dir,
        collection_name=resolved_settings.vector_collection_name,
    )

    try:
        before_status = get_corpus_status(
            settings=resolved_settings,
            connection=resolved_connection,
            vector_store=resolved_vector_store,
        )
        if not source_path.exists():
            return CorpusRebuildResult(
                source_path=str(source_path),
                recursive=recursive,
                dry_run=dry_run,
                status='failed',
                before_status=before_status,
                error_code='INPUT_NOT_FOUND',
                message='Path not found.',
            )

        reset_result = reset_corpus(
            settings=resolved_settings,
            connection=resolved_connection,
            vector_store=resolved_vector_store,
            dry_run=dry_run,
        )
        if dry_run:
            return CorpusRebuildResult(
                source_path=str(source_path),
                recursive=recursive,
                dry_run=True,
                status='preview',
                before_status=before_status,
                reset=reset_result,
                after_status=before_status,
            )

        index_result = index_corpus_path(
            source_path,
            settings=resolved_settings,
            connection=resolved_connection,
            vector_store=resolved_vector_store,
            embedder=embedder,
            chunk_size=chunk_size,
            overlap=overlap,
            recursive=recursive,
            commit_mode=commit_mode,
            progress=progress,
            cancel_token=cancel_token,
        )
        after_status = get_corpus_status(
            settings=resolved_settings,
            connection=resolved_connection,
            vector_store=resolved_vector_store,
        )
        return CorpusRebuildResult(
            source_path=str(source_path),
            recursive=recursive,
            dry_run=False,
            status=index_result.status,
            before_status=before_status,
            reset=reset_result,
            index_result=index_result,
            after_status=after_status,
        )
    finally:
        if owns_connection:
            resolved_connection.close()


def _load_structure_chunk_corpus_file(
    path: Path,
    *,
    chunk_size: int,
    overlap: int,
    source_root: Path | None = None,
) -> _PendingCorpusIndex | _PreparationFailure:
    try:
        document = load_document(path)
        if not document.raw_text.strip():
            raise ValueError('EMPTY_CONTENT')
        note = structure_document(document, source_root=source_root, hash_unrooted=True)
        return _PendingCorpusIndex(
            source_path=document.source_path,
            note=note,
            chunks=index_note(note, chunk_size=chunk_size, overlap=overlap),
        )
    except (FileNotFoundError, ValueError) as exc:
        return _PreparationFailure(
            source_path=path,
            error_code=_error_code_for_exception(exc),
            message=str(exc),
        )


def _resolve_prepared_corpus_file(
    prepared: _PendingCorpusIndex | _PreparationFailure,
    *,
    connection: sqlite3.Connection,
    vector_store: LocalVectorStore,
    embedder: Embedder,
    chunk_size: int,
    overlap: int,
) -> _PendingCorpusIndex | CorpusIndexResult:
    if isinstance(prepared, _PreparationFailure):
        return _failure_result(
            prepared.source_path,
            error_code=prepared.error_code,
            message=prepared.message,
            vector_store=vector_store,
            embedding_model=embedder.model_name,
        )

    existing_hash = get_note_content_hash(connection, prepared.note.note_id)
    existing_chunk_ids = list_chunk_ids_for_note(connection, prepared.note.note_id)
    chunks_match_config = note_chunks_match_config(
        connection,
        prepared.note.note_id,
        chunk_size=chunk_size,
        overlap=overlap,
    )
    if existing_hash == prepared.note.content_hash and chunks_match_config and vector_store.has_chunk_ids(existing_chunk_ids):
        return _unchanged_result(
            prepared.note,
            source_path=prepared.source_path,
            chunk_ids=existing_chunk_ids,
            vector_store=vector_store,
            embedding_model=embedder.model_name,
        )
    return prepared


def _prepare_corpus_file(
    path: Path,
    *,
    connection: sqlite3.Connection,
    vector_store: LocalVectorStore,
    embedder: Embedder,
    chunk_size: int,
    overlap: int,
    source_root: Path | None = None,
) -> _PendingCorpusIndex | CorpusIndexResult:
    prepared = _load_structure_chunk_corpus_file(
        path,
        chunk_size=chunk_size,
        overlap=overlap,
        source_root=source_root,
    )
    return _resolve_prepared_corpus_file(
        prepared,
        connection=connection,
        vector_store=vector_store,
        embedder=embedder,
        chunk_size=chunk_size,
        overlap=overlap,
    )


def index_corpus_file(
    path: Path | str,
    *,
    settings: Settings | None = None,
    connection: sqlite3.Connection | None = None,
    vector_store: LocalVectorStore | None = None,
    embedder: Embedder | None = None,
    chunk_size: int | None = None,
    overlap: int | None = None,
    source_root: Path | None = None,
) -> CorpusIndexResult:
    """Estrutura, persiste e indexa um arquivo no corpus local.

    `source_root` é a pasta-raiz do vault; ela entra no note_id, então reindexar uma nota
    precisa da mesma raiz da indexação original para manter o id.
    """
    resolved_settings = settings or get_settings()
    ensure_runtime_dirs(resolved_settings)
    source_path = Path(path).expanduser()

    owns_connection = connection is None
    resolved_connection = connection or init_sqlite(resolved_settings.sqlite_path)
    resolved_vector_store = vector_store or LocalVectorStore(
        resolved_settings.vector_store_dir,
        collection_name=resolved_settings.vector_collection_name,
    )
    resolved_embedder = embedder or get_embedder(
        resolved_settings.embedding_model,
        device=resolved_settings.embedding_device,
    )
    resolved_chunk_size = chunk_size or resolved_settings.default_chunk_size
    resolved_overlap = resolved_settings.default_chunk_overlap if overlap is None else overlap

    try:
        document = load_document(source_path)
        if not document.raw_text.strip():
            raise ValueError('EMPTY_CONTENT')

        note = structure_document(document, source_root=source_root, hash_unrooted=True)
        existing_hash = get_note_content_hash(resolved_connection, note.note_id)
        existing_chunk_ids = list_chunk_ids_for_note(resolved_connection, note.note_id)
        chunks_match_config = note_chunks_match_config(
            resolved_connection,
            note.note_id,
            chunk_size=resolved_chunk_size,
            overlap=resolved_overlap,
        )
        if (
            existing_hash == note.content_hash
            and chunks_match_config
            and resolved_vector_store.has_chunk_ids(existing_chunk_ids)
        ):
            return _unchanged_result(
                note,
                source_path=document.source_path,
                chunk_ids=existing_chunk_ids,
                vector_store=resolved_vector_store,
                embedding_model=resolved_embedder.model_name,
            )

        chunks = index_note(note, chunk_size=resolved_chunk_size, overlap=resolved_overlap)
        embeddings = resolved_embedder.embed([chunk.chunk_text for chunk in chunks])
        if len(embeddings) != len(chunks):
            raise ValueError('A quantidade de embeddings precisa bater com a quantidade de chunks.')

        _delete_superseded_source_notes(resolved_connection, resolved_vector_store, note)
        resolved_vector_store.delete_by_note_id(note.note_id)
        resolved_vector_store.upsert_chunks(chunks, embeddings, embedding_model=resolved_embedder.model_name)
        upsert_note(resolved_connection, note)
        replace_chunks_for_note(resolved_connection, note.note_id, chunks)

        return CorpusIndexResult(
            source_path=str(document.source_path),
            status='success',
            note_id=note.note_id,
            chunks_indexed=len(chunks),
            embedding_model=resolved_embedder.model_name,
            vector_collection_name=resolved_vector_store.collection_name,
            vector_entries_count=resolved_vector_store.count(),
            message='Nota indexada.',
        )
    except (FileNotFoundError, ValueError) as exc:
        return _failure_result(
            source_path,
            error_code=_error_code_for_exception(exc),
            message=str(exc),
            vector_store=resolved_vector_store,
            embedding_model=resolved_embedder.model_name,
        )
    finally:
        if owns_connection:
            resolved_connection.close()


def _batch_status(indexed_count: int, failed_count: int, unchanged_count: int = 0) -> str:
    if (indexed_count > 0 or unchanged_count > 0) and failed_count == 0:
        return 'success'
    if indexed_count > 0 or unchanged_count > 0:
        return 'partial'
    return 'failed'


def index_corpus_path(
    path: Path | str,
    *,
    settings: Settings | None = None,
    connection: sqlite3.Connection | None = None,
    vector_store: LocalVectorStore | None = None,
    embedder: Embedder | None = None,
    chunk_size: int | None = None,
    overlap: int | None = None,
    recursive: bool = False,
    commit_mode: CorpusCommitMode | None = None,
    progress: ProgressCallback | None = None,
    cancel_token: CancellationToken | None = None,
) -> CorpusIndexBatchResult:
    """Indexa um arquivo ou diretorio no corpus local."""
    resolved_settings = settings or get_settings()
    ensure_runtime_dirs(resolved_settings)
    source_path = Path(path).expanduser()
    owns_connection = connection is None
    resolved_connection = connection or init_sqlite(resolved_settings.sqlite_path)
    resolved_vector_store = vector_store or LocalVectorStore(
        resolved_settings.vector_store_dir,
        collection_name=resolved_settings.vector_collection_name,
    )
    resolved_chunk_size = chunk_size or resolved_settings.default_chunk_size
    resolved_overlap = resolved_settings.default_chunk_overlap if overlap is None else overlap
    commit_mode_requested = commit_mode or resolved_settings.corpus_commit_mode
    commit_mode_resolved: ResolvedCorpusCommitMode = 'atomic'
    started_at = perf_counter()
    warmup_ms = 0

    try:
        if source_path.is_file():
            commit_mode_resolved = _resolve_initial_commit_mode(
                commit_mode_requested,
                total_files=1,
                settings=resolved_settings,
                source_is_file=True,
            )
            if _is_cancelled(cancel_token):
                _emit_progress(
                    progress,
                    phase='cancelled',
                    started_at=started_at,
                    current_path=source_path,
                    total_found=1,
                    commit_mode_requested=commit_mode_requested,
                    commit_mode_resolved=commit_mode_resolved,
                    message='Indexacao cancelada.',
                )
                return _cancelled_batch_result(
                    source_path,
                    recursive=recursive,
                    total_found=1,
                    indexed_count=0,
                    failed_count=0,
                    skipped_count=0,
                    results=[],
                    commit_mode_requested=commit_mode_requested,
                    commit_mode_resolved=commit_mode_resolved,
                )
            resolved_embedder, warmup_ms = _resolve_embedder_for_index(
                embedder,
                settings=resolved_settings,
                progress=progress,
                started_at=started_at,
                source_path=source_path,
                total_found=1,
                commit_mode_requested=commit_mode_requested,
                commit_mode_resolved=commit_mode_resolved,
            )
            _emit_progress(
                progress,
                phase='loading',
                started_at=started_at,
                current_path=source_path,
                total_found=1,
                warmup_ms=warmup_ms,
                commit_mode_requested=commit_mode_requested,
                commit_mode_resolved=commit_mode_resolved,
                message=f'Carregando {source_path.name}',
            )
            _emit_progress(
                progress,
                phase='embedding',
                started_at=started_at,
                current_path=source_path,
                total_found=1,
                warmup_ms=warmup_ms,
                commit_mode_requested=commit_mode_requested,
                commit_mode_resolved=commit_mode_resolved,
                message=f'Estruturando e embedando {source_path.name}',
            )
            result = index_corpus_file(
                source_path,
                settings=resolved_settings,
                connection=resolved_connection,
                vector_store=resolved_vector_store,
                embedder=resolved_embedder,
                chunk_size=chunk_size,
                overlap=overlap,
            )
            indexed_count = 1 if result.status == 'success' else 0
            failed_count = 1 if result.status == 'failed' else 0
            unchanged_count = 1 if result.status == 'unchanged' else 0
            _emit_progress(
                progress,
                phase='writing',
                started_at=started_at,
                current_path=source_path,
                total_found=1,
                processed_count=1,
                indexed_count=indexed_count,
                unchanged_count=unchanged_count,
                failed_count=failed_count,
                warmup_ms=warmup_ms,
                committed_count=indexed_count,
                commit_mode_requested=commit_mode_requested,
                commit_mode_resolved=commit_mode_resolved,
                batch_index=1,
                batch_total=1,
                message=f'Finalizado {source_path.name}',
            )
            _emit_progress(
                progress,
                phase='finished',
                started_at=started_at,
                total_found=1,
                processed_count=1,
                indexed_count=indexed_count,
                unchanged_count=unchanged_count,
                failed_count=failed_count,
                warmup_ms=warmup_ms,
                committed_count=indexed_count,
                commit_mode_requested=commit_mode_requested,
                commit_mode_resolved=commit_mode_resolved,
                batch_index=1,
                batch_total=1,
                message='Indexacao concluida.',
            )
            return CorpusIndexBatchResult(
                source_path=str(source_path),
                recursive=recursive,
                status=_batch_status(indexed_count, failed_count, unchanged_count),  # type: ignore[arg-type]
                total_found=1,
                indexed_count=indexed_count,
                failed_count=failed_count,
                skipped_count=0,
                unchanged_count=unchanged_count,
                commit_mode_requested=commit_mode_requested,
                commit_mode_resolved=commit_mode_resolved,
                results=[result],
            )

        _emit_progress(
            progress,
            phase='discovering',
            started_at=started_at,
            current_path=source_path,
            commit_mode_requested=commit_mode_requested,
            commit_mode_resolved=commit_mode_resolved,
            message='Descobrindo arquivos.',
        )
        discovery = discover_corpus_files(source_path, recursive=recursive)
        if not source_path.exists() or not source_path.is_dir():
            _emit_progress(
                progress,
                phase='failed',
                started_at=started_at,
                current_path=source_path,
                skipped_count=len(discovery.skipped),
                commit_mode_requested=commit_mode_requested,
                commit_mode_resolved=commit_mode_resolved,
                message='Pasta nao encontrada.',
            )
            return CorpusIndexBatchResult(
                source_path=str(source_path),
                recursive=recursive,
                status='failed',
                total_found=0,
                indexed_count=0,
                failed_count=0,
                skipped_count=len(discovery.skipped),
                commit_mode_requested=commit_mode_requested,
                commit_mode_resolved=commit_mode_resolved,
                results=[],
                skipped=discovery.skipped,
            )

        pending_items: list[_PendingCorpusIndex] = []
        results: list[CorpusIndexResult] = []
        indexed_count = 0
        unchanged_count = 0
        failed_count = 0
        skipped_count = len(discovery.skipped)
        total_found = len(discovery.files)
        commit_mode_resolved = _resolve_initial_commit_mode(
            commit_mode_requested,
            total_files=total_found,
            settings=resolved_settings,
        )
        batch_total = 1
        if commit_mode_resolved == 'microbatch':
            batch_total = max(1, (max(total_found, 1) + resolved_settings.corpus_micro_batch_files - 1) // resolved_settings.corpus_micro_batch_files)
        batch_index = 0
        embedding_ms_total = 0
        writing_ms_total = 0

        _emit_progress(
            progress,
            phase='discovering',
            started_at=started_at,
            current_path=source_path,
            total_found=total_found,
            skipped_count=skipped_count,
            commit_mode_requested=commit_mode_requested,
            commit_mode_resolved=commit_mode_resolved,
            batch_total=batch_total,
            message=f'{total_found} arquivos suportados encontrados.',
        )
        if not discovery.files:
            _emit_progress(
                progress,
                phase='finished',
                started_at=started_at,
                total_found=0,
                skipped_count=skipped_count,
                commit_mode_requested=commit_mode_requested,
                commit_mode_resolved=commit_mode_resolved,
                batch_total=batch_total,
                message='Indexacao concluida sem arquivos suportados.',
            )
            return CorpusIndexBatchResult(
                source_path=str(source_path),
                recursive=recursive,
                status='success',
                total_found=0,
                indexed_count=0,
                failed_count=0,
                skipped_count=skipped_count,
                unchanged_count=0,
                commit_mode_requested=commit_mode_requested,
                commit_mode_resolved=commit_mode_resolved,
                results=[],
                skipped=discovery.skipped,
            )

        resolved_embedder, warmup_ms = _resolve_embedder_for_index(
            embedder,
            settings=resolved_settings,
            progress=progress,
            started_at=started_at,
            source_path=source_path,
            total_found=total_found,
            commit_mode_requested=commit_mode_requested,
            commit_mode_resolved=commit_mode_resolved,
        )

        def flush_pending(*, force: bool, current_path: Path | None = None) -> None:
            nonlocal batch_index, embedding_ms_total, indexed_count, failed_count, pending_items, writing_ms_total
            if not pending_items or (not force and commit_mode_resolved != 'microbatch'):
                return
            batch_index += 1
            effective_batch_total = max(batch_total, batch_index)
            outcome = _commit_pending_items(
                pending_items,
                settings=resolved_settings,
                vector_store=resolved_vector_store,
                connection=resolved_connection,
                embedder=resolved_embedder,
                progress=progress,
                started_at=started_at,
                source_path=current_path or source_path,
                total_found=total_found,
                skipped_count=skipped_count,
                unchanged_count=unchanged_count,
                indexed_count=indexed_count,
                failed_count=failed_count,
                commit_mode_requested=commit_mode_requested,
                commit_mode_resolved=commit_mode_resolved,
                batch_index=batch_index,
                batch_total=effective_batch_total,
                cancel_token=cancel_token,
            )
            pending_items = []
            embedding_ms_total += outcome.embedding_ms
            writing_ms_total += outcome.writing_ms
            for item in outcome.results:
                item.vector_entries_count = resolved_vector_store.count()
            results.extend(outcome.results)
            indexed_count += outcome.indexed_count
            failed_count += outcome.failed_count
            if outcome.results:
                _emit_progress(
                    progress,
                    phase='committed',
                    started_at=started_at,
                    current_path=current_path or source_path,
                    total_found=total_found,
                    processed_count=len(results) + len(pending_items),
                    indexed_count=indexed_count,
                    unchanged_count=unchanged_count,
                    failed_count=failed_count,
                    skipped_count=skipped_count,
                    warmup_ms=warmup_ms,
                    embedding_ms=embedding_ms_total,
                    writing_ms=writing_ms_total,
                    committed_count=indexed_count,
                    commit_mode_requested=commit_mode_requested,
                    commit_mode_resolved=commit_mode_resolved,
                    batch_index=batch_index,
                    batch_total=effective_batch_total,
                    message=f'Lote {batch_index}/{effective_batch_total} commitado: {outcome.indexed_count} arquivos.',
                )

        def accept_prepared(prepared: _PendingCorpusIndex | CorpusIndexResult, file_path: Path) -> None:
            nonlocal commit_mode_resolved, batch_total, unchanged_count, failed_count
            if isinstance(prepared, _PendingCorpusIndex):
                pending_items.append(prepared)
                if _should_switch_auto_to_microbatch(
                    commit_mode_requested,
                    commit_mode_resolved,
                    pending_items=pending_items,
                    settings=resolved_settings,
                ):
                    commit_mode_resolved = 'microbatch'
                    batch_total = max(
                        1,
                        (max(total_found, 1) + resolved_settings.corpus_micro_batch_files - 1)
                        // resolved_settings.corpus_micro_batch_files,
                    )
                if commit_mode_resolved == 'microbatch' and _should_flush_microbatch(pending_items, settings=resolved_settings):
                    flush_pending(force=True, current_path=file_path)
                return
            results.append(prepared)
            if prepared.status == 'failed':
                failed_count += 1
            elif prepared.status == 'unchanged':
                unchanged_count += 1

        use_parallel_prepare = (
            resolved_settings.corpus_index_workers > 1
            and discovery.files
            and commit_mode_resolved == 'atomic'
            and commit_mode_requested != 'microbatch'
        )
        if use_parallel_prepare:
            _emit_progress(
                progress,
                phase='loading',
                started_at=started_at,
                current_path=source_path,
                total_found=total_found,
                skipped_count=skipped_count,
                warmup_ms=warmup_ms,
                commit_mode_requested=commit_mode_requested,
                commit_mode_resolved=commit_mode_resolved,
                batch_total=batch_total,
                message=f'Preparando arquivos com {resolved_settings.corpus_index_workers} workers.',
            )
            prepared_slots: list[_PendingCorpusIndex | CorpusIndexResult | None] = [None] * len(discovery.files)
            with ThreadPoolExecutor(max_workers=resolved_settings.corpus_index_workers) as executor:
                futures = {
                    executor.submit(
                        _load_structure_chunk_corpus_file,
                        file_path,
                        chunk_size=resolved_chunk_size,
                        overlap=resolved_overlap,
                        source_root=source_path,
                    ): (index, file_path)
                    for index, file_path in enumerate(discovery.files)
                }
                for future in as_completed(futures):
                    index, file_path = futures[future]
                    prepared = _resolve_prepared_corpus_file(
                        future.result(),
                        connection=resolved_connection,
                        vector_store=resolved_vector_store,
                        embedder=resolved_embedder,
                        chunk_size=resolved_chunk_size,
                        overlap=resolved_overlap,
                    )
                    prepared_slots[index] = prepared
                    _emit_progress(
                        progress,
                        phase='structuring',
                        started_at=started_at,
                        current_path=file_path,
                        total_found=total_found,
                        processed_count=sum(item is not None for item in prepared_slots),
                        indexed_count=indexed_count,
                        unchanged_count=unchanged_count,
                        failed_count=failed_count,
                        skipped_count=skipped_count,
                        warmup_ms=warmup_ms,
                        commit_mode_requested=commit_mode_requested,
                        commit_mode_resolved=commit_mode_resolved,
                        batch_total=batch_total,
                        message=f'Preparado {file_path.name}',
                    )
                    if _is_cancelled(cancel_token):
                        for pending_future in futures:
                            pending_future.cancel()
                        _emit_progress(
                            progress,
                            phase='cancelled',
                            started_at=started_at,
                            current_path=file_path,
                            total_found=total_found,
                            processed_count=len(results),
                            indexed_count=indexed_count,
                            unchanged_count=unchanged_count,
                            failed_count=failed_count,
                            skipped_count=skipped_count,
                            warmup_ms=warmup_ms,
                            commit_mode_requested=commit_mode_requested,
                            commit_mode_resolved=commit_mode_resolved,
                            batch_total=batch_total,
                            message='Indexacao cancelada.',
                        )
                        return _cancelled_batch_result(
                            source_path,
                            recursive=recursive,
                            total_found=total_found,
                            indexed_count=indexed_count,
                            unchanged_count=unchanged_count,
                            failed_count=failed_count,
                            skipped_count=skipped_count,
                            results=results,
                            commit_mode_requested=commit_mode_requested,
                            commit_mode_resolved=commit_mode_resolved,
                        )
            for prepared in prepared_slots:
                if prepared is None:
                    continue
                accept_prepared(prepared, prepared.source_path if isinstance(prepared, _PendingCorpusIndex) else Path(prepared.source_path))
        else:
            for file_path in discovery.files:
                if _is_cancelled(cancel_token):
                    _emit_progress(
                        progress,
                        phase='cancelled',
                        started_at=started_at,
                        current_path=file_path,
                        total_found=total_found,
                        processed_count=len(results),
                        indexed_count=indexed_count,
                        failed_count=failed_count,
                        skipped_count=skipped_count,
                        warmup_ms=warmup_ms,
                        commit_mode_requested=commit_mode_requested,
                        commit_mode_resolved=commit_mode_resolved,
                        batch_index=batch_index,
                        batch_total=batch_total,
                        message='Indexacao cancelada.',
                    )
                    return _cancelled_batch_result(
                        source_path,
                        recursive=recursive,
                        total_found=total_found,
                        indexed_count=indexed_count,
                        unchanged_count=unchanged_count,
                        failed_count=failed_count,
                        skipped_count=skipped_count,
                        results=results,
                        commit_mode_requested=commit_mode_requested,
                        commit_mode_resolved=commit_mode_resolved,
                    )
                processed_count = len(results) + len(pending_items)
                _emit_progress(
                    progress,
                    phase='loading',
                    started_at=started_at,
                    current_path=file_path,
                    total_found=total_found,
                    processed_count=processed_count,
                    indexed_count=indexed_count,
                    unchanged_count=unchanged_count,
                    failed_count=failed_count,
                    skipped_count=skipped_count,
                    warmup_ms=warmup_ms,
                    committed_count=indexed_count,
                    commit_mode_requested=commit_mode_requested,
                    commit_mode_resolved=commit_mode_resolved,
                    batch_index=batch_index,
                    batch_total=batch_total,
                    message=f'Processando {file_path.name}',
                )
                if _is_cancelled(cancel_token):
                    _emit_progress(
                        progress,
                        phase='cancelled',
                        started_at=started_at,
                        current_path=file_path,
                        total_found=total_found,
                        processed_count=len(results),
                        indexed_count=indexed_count,
                        unchanged_count=unchanged_count,
                        failed_count=failed_count,
                        skipped_count=skipped_count,
                        warmup_ms=warmup_ms,
                        committed_count=indexed_count,
                        commit_mode_requested=commit_mode_requested,
                        commit_mode_resolved=commit_mode_resolved,
                        batch_index=batch_index,
                        batch_total=batch_total,
                        message='Indexacao cancelada.',
                    )
                    return _cancelled_batch_result(
                        source_path,
                        recursive=recursive,
                        total_found=total_found,
                        indexed_count=indexed_count,
                        unchanged_count=unchanged_count,
                        failed_count=failed_count,
                        skipped_count=skipped_count,
                        results=results,
                        commit_mode_requested=commit_mode_requested,
                        commit_mode_resolved=commit_mode_resolved,
                    )
                _emit_progress(
                    progress,
                    phase='structuring',
                    started_at=started_at,
                    current_path=file_path,
                    total_found=total_found,
                    processed_count=processed_count,
                    indexed_count=indexed_count,
                    unchanged_count=unchanged_count,
                    failed_count=failed_count,
                    skipped_count=skipped_count,
                    warmup_ms=warmup_ms,
                    committed_count=indexed_count,
                    commit_mode_requested=commit_mode_requested,
                    commit_mode_resolved=commit_mode_resolved,
                    batch_index=batch_index,
                    batch_total=batch_total,
                    message=f'Estruturando {file_path.name}',
                )
                prepared = _prepare_corpus_file(
                    file_path,
                    connection=resolved_connection,
                    vector_store=resolved_vector_store,
                    embedder=resolved_embedder,
                    chunk_size=resolved_chunk_size,
                    overlap=resolved_overlap,
                    source_root=source_path,
                )
                accept_prepared(prepared, file_path)
                if _is_cancelled(cancel_token):
                    _emit_progress(
                        progress,
                        phase='cancelled',
                        started_at=started_at,
                        current_path=file_path,
                        total_found=total_found,
                        processed_count=len(results),
                        indexed_count=indexed_count,
                        unchanged_count=unchanged_count,
                        failed_count=failed_count,
                        skipped_count=skipped_count,
                        warmup_ms=warmup_ms,
                        committed_count=indexed_count,
                        commit_mode_requested=commit_mode_requested,
                        commit_mode_resolved=commit_mode_resolved,
                        batch_index=batch_index,
                        batch_total=batch_total,
                        message='Indexacao cancelada.',
                    )
                    return _cancelled_batch_result(
                        source_path,
                        recursive=recursive,
                        total_found=total_found,
                        indexed_count=indexed_count,
                        unchanged_count=unchanged_count,
                        failed_count=failed_count,
                        skipped_count=skipped_count,
                        results=results,
                        commit_mode_requested=commit_mode_requested,
                        commit_mode_resolved=commit_mode_resolved,
                    )

        if pending_items and _is_cancelled(cancel_token):
            _emit_progress(
                progress,
                phase='cancelled',
                started_at=started_at,
                current_path=source_path,
                total_found=total_found,
                processed_count=len(results),
                indexed_count=indexed_count,
                unchanged_count=unchanged_count,
                failed_count=failed_count,
                skipped_count=skipped_count,
                warmup_ms=warmup_ms,
                embedding_ms=embedding_ms_total,
                writing_ms=writing_ms_total,
                committed_count=indexed_count,
                commit_mode_requested=commit_mode_requested,
                commit_mode_resolved=commit_mode_resolved,
                batch_index=batch_index,
                batch_total=batch_total,
                message='Indexacao cancelada antes da gravacao.',
            )
            return _cancelled_batch_result(
                source_path,
                recursive=recursive,
                total_found=total_found,
                indexed_count=indexed_count,
                unchanged_count=unchanged_count,
                failed_count=failed_count,
                skipped_count=skipped_count,
                results=results,
                commit_mode_requested=commit_mode_requested,
                commit_mode_resolved=commit_mode_resolved,
            )

        if pending_items:
            flush_pending(force=True, current_path=source_path)

        vector_entries_count = resolved_vector_store.count()
        for item in results:
            item.vector_entries_count = vector_entries_count

        _emit_progress(
            progress,
            phase='finished',
            started_at=started_at,
            total_found=total_found,
            processed_count=len(results),
            indexed_count=indexed_count,
            unchanged_count=unchanged_count,
            failed_count=failed_count,
            skipped_count=skipped_count,
            warmup_ms=warmup_ms,
            embedding_ms=embedding_ms_total,
            writing_ms=writing_ms_total,
            committed_count=indexed_count,
            commit_mode_requested=commit_mode_requested,
            commit_mode_resolved=commit_mode_resolved,
            batch_index=batch_index,
            batch_total=max(batch_total, batch_index),
            message='Indexacao concluida.',
        )
        return CorpusIndexBatchResult(
            source_path=str(source_path),
            recursive=recursive,
            status=_batch_status(indexed_count, failed_count, unchanged_count),  # type: ignore[arg-type]
            total_found=len(discovery.files),
            indexed_count=indexed_count,
            failed_count=failed_count,
            skipped_count=len(discovery.skipped),
            unchanged_count=unchanged_count,
            commit_mode_requested=commit_mode_requested,
            commit_mode_resolved=commit_mode_resolved,
            results=results,
            skipped=discovery.skipped,
        )
    finally:
        if owns_connection:
            resolved_connection.close()
