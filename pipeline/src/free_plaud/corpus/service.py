import sqlite3
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from time import perf_counter

from free_plaud.app.config import Settings, get_settings
from free_plaud.app.paths import ensure_runtime_dirs
from free_plaud.corpus.cancellation import CancellationToken
from free_plaud.corpus.discovery import discover_corpus_files
from free_plaud.corpus.models import (
    CorpusIndexBatchResult,
    CorpusIndexBenchmarkResult,
    CorpusIndexBenchmarkRunResult,
    CorpusIndexProgress,
    CorpusIndexResult,
    CorpusRebuildResult,
    CorpusResetResult,
    CorpusStatusResult,
)
from free_plaud.ingest.loaders import load_document
from free_plaud.notes.schemas import Note
from free_plaud.notes.structurer import structure_document
from free_plaud.providers.embed import Embedder, get_embedder
from free_plaud.retrieval.indexer import index_note
from free_plaud.retrieval.models import Chunk
from free_plaud.storage.sqlite import (
    count_chunks,
    count_notes,
    delete_corpus_notes_and_chunks,
    get_note_content_hash,
    init_sqlite,
    list_chunk_ids,
    list_chunk_ids_for_note,
    note_chunks_match_config,
    replace_chunks_for_note,
    upsert_note,
)
from free_plaud.storage.vector import LocalVectorStore

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
        results=results,
    )


def _unchanged_result(
    note,
    *,
    source_path: Path,
    chunk_ids: list[str],
    vector_store: LocalVectorStore,
    embedding_model: str,
) -> CorpusIndexResult:  # noqa: ANN001
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
        sqlite_path=data_dir / 'results' / 'free_plaud.sqlite3',
        vector_store_dir=data_dir / 'results' / 'vector_store',
        vector_collection_name=base.vector_collection_name,
        embedding_model=base.embedding_model,
        default_chunk_size=base.default_chunk_size,
        default_chunk_overlap=base.default_chunk_overlap,
        retrieval_top_k=base.retrieval_top_k,
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


def _batched(items: list, batch_size: int):  # noqa: ANN001, ANN202
    for start in range(0, len(items), batch_size):
        yield items[start : start + batch_size]


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
        vector_records = resolved_vector_store.list_records()
        vector_chunk_ids = {chunk_id for chunk_id, _ in vector_records}

        stale_chunk_ids = sorted(vector_chunk_ids - sqlite_chunk_ids)
        missing_chunk_ids = sorted(sqlite_chunk_ids - vector_chunk_ids)
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
        elif stale_chunk_ids or missing_chunk_ids:
            status = 'inconsistent'
        else:
            status = 'clean'

        return CorpusStatusResult(
            sqlite_path=str(resolved_settings.sqlite_path),
            vector_store_dir=str(resolved_settings.vector_store_dir),
            vector_collection_name=resolved_vector_store.collection_name,
            notes_count=count_notes(resolved_connection),
            sqlite_chunks_count=count_chunks(resolved_connection),
            vector_chunks_count=len(vector_chunk_ids),
            stale_vector_chunks_count=len(stale_chunk_ids),
            missing_vector_chunks_count=len(missing_chunk_ids),
            orphan_vector_note_ids=orphan_note_ids,
            stale_vector_chunk_ids=stale_chunk_ids,
            missing_vector_chunk_ids=missing_chunk_ids,
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

        deleted_notes, deleted_chunks = delete_corpus_notes_and_chunks(resolved_connection)
        resolved_vector_store.reset()
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
) -> CorpusIndexBenchmarkResult:
    """Mede indexacao em corpus sintetico dentro de workspace temporario."""
    if files <= 0:
        raise ValueError('files precisa ser maior que zero.')
    if repeat <= 0:
        raise ValueError('repeat precisa ser maior que zero.')

    resolved_settings = settings or get_settings()
    resolved_embedder = embedder or get_embedder(resolved_settings.embedding_model)
    counting_embedder = _CountingEmbedder(resolved_embedder)
    resolved_chunk_size = chunk_size or resolved_settings.default_chunk_size
    resolved_overlap = resolved_settings.default_chunk_overlap if overlap is None else overlap

    with TemporaryDirectory(prefix='free-plaud-corpus-benchmark-', ignore_cleanup_errors=True) as temporary_dir:
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
    resolved_embedder = embedder or get_embedder(resolved_settings.embedding_model)

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
            embedder=resolved_embedder,
            chunk_size=chunk_size,
            overlap=overlap,
            recursive=recursive,
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


def _load_structure_chunk_corpus_file(path: Path, *, chunk_size: int, overlap: int) -> _PendingCorpusIndex | _PreparationFailure:
    try:
        document = load_document(path)
        if not document.raw_text.strip():
            raise ValueError('EMPTY_CONTENT')
        note = structure_document(document)
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
) -> _PendingCorpusIndex | CorpusIndexResult:
    prepared = _load_structure_chunk_corpus_file(path, chunk_size=chunk_size, overlap=overlap)
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
) -> CorpusIndexResult:
    """Estrutura, persiste e indexa um arquivo no corpus local."""
    resolved_settings = settings or get_settings()
    ensure_runtime_dirs(resolved_settings)
    source_path = Path(path).expanduser()

    owns_connection = connection is None
    resolved_connection = connection or init_sqlite(resolved_settings.sqlite_path)
    resolved_vector_store = vector_store or LocalVectorStore(
        resolved_settings.vector_store_dir,
        collection_name=resolved_settings.vector_collection_name,
    )
    resolved_embedder = embedder or get_embedder(resolved_settings.embedding_model)
    resolved_chunk_size = chunk_size or resolved_settings.default_chunk_size
    resolved_overlap = resolved_settings.default_chunk_overlap if overlap is None else overlap

    try:
        document = load_document(source_path)
        if not document.raw_text.strip():
            raise ValueError('EMPTY_CONTENT')

        note = structure_document(document)
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
            message='Document indexed successfully.',
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
    resolved_embedder = embedder or get_embedder(resolved_settings.embedding_model)
    resolved_chunk_size = chunk_size or resolved_settings.default_chunk_size
    resolved_overlap = resolved_settings.default_chunk_overlap if overlap is None else overlap
    started_at = perf_counter()

    try:
        if source_path.is_file():
            if _is_cancelled(cancel_token):
                _emit_progress(
                    progress,
                    phase='cancelled',
                    started_at=started_at,
                    current_path=source_path,
                    total_found=1,
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
                )
            _emit_progress(
                progress,
                phase='loading',
                started_at=started_at,
                current_path=source_path,
                total_found=1,
                message=f'Carregando {source_path.name}',
            )
            _emit_progress(
                progress,
                phase='embedding',
                started_at=started_at,
                current_path=source_path,
                total_found=1,
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
                results=[result],
            )

        _emit_progress(
            progress,
            phase='discovering',
            started_at=started_at,
            current_path=source_path,
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
                results=[],
                skipped=discovery.skipped,
            )

        prepared_items: list[CorpusIndexResult | _PendingCorpusIndex] = []
        pending_items: list[_PendingCorpusIndex] = []
        indexed_count = 0
        unchanged_count = 0
        failed_count = 0
        skipped_count = len(discovery.skipped)
        total_found = len(discovery.files)
        _emit_progress(
            progress,
            phase='discovering',
            started_at=started_at,
            current_path=source_path,
            total_found=total_found,
            skipped_count=skipped_count,
            message=f'{total_found} arquivos suportados encontrados.',
        )
        if resolved_settings.corpus_index_workers > 1 and discovery.files:
            _emit_progress(
                progress,
                phase='loading',
                started_at=started_at,
                current_path=source_path,
                total_found=total_found,
                skipped_count=skipped_count,
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
                    if isinstance(prepared, CorpusIndexResult):
                        if prepared.status == 'failed':
                            failed_count += 1
                        elif prepared.status == 'unchanged':
                            unchanged_count += 1
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
                        message=f'Preparado {file_path.name}',
                    )
                    if _is_cancelled(cancel_token):
                        for pending_future in futures:
                            pending_future.cancel()
                        resolved_results = [item for item in prepared_slots if isinstance(item, CorpusIndexResult)]
                        _emit_progress(
                            progress,
                            phase='cancelled',
                            started_at=started_at,
                            current_path=file_path,
                            total_found=total_found,
                            processed_count=len(resolved_results),
                            indexed_count=indexed_count,
                            unchanged_count=unchanged_count,
                            failed_count=failed_count,
                            skipped_count=skipped_count,
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
                            results=resolved_results,
                        )
            for prepared in prepared_slots:
                if prepared is None:
                    continue
                prepared_items.append(prepared)
                if isinstance(prepared, _PendingCorpusIndex):
                    pending_items.append(prepared)
        else:
            for file_path in discovery.files:
                if _is_cancelled(cancel_token):
                    _emit_progress(
                        progress,
                        phase='cancelled',
                        started_at=started_at,
                        current_path=file_path,
                        total_found=total_found,
                        processed_count=len(prepared_items),
                        indexed_count=indexed_count,
                        failed_count=failed_count,
                        skipped_count=skipped_count,
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
                        results=[item for item in prepared_items if isinstance(item, CorpusIndexResult)],
                    )
                processed_count = len(prepared_items)
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
                    message=f'Processando {file_path.name}',
                )
                if _is_cancelled(cancel_token):
                    _emit_progress(
                        progress,
                        phase='cancelled',
                        started_at=started_at,
                        current_path=file_path,
                        total_found=total_found,
                        processed_count=len(prepared_items),
                        indexed_count=indexed_count,
                        unchanged_count=unchanged_count,
                        failed_count=failed_count,
                        skipped_count=skipped_count,
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
                        results=[item for item in prepared_items if isinstance(item, CorpusIndexResult)],
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
                    message=f'Estruturando {file_path.name}',
                )
                prepared = _prepare_corpus_file(
                    file_path,
                    connection=resolved_connection,
                    vector_store=resolved_vector_store,
                    embedder=resolved_embedder,
                    chunk_size=resolved_chunk_size,
                    overlap=resolved_overlap,
                )
                prepared_items.append(prepared)
                if isinstance(prepared, _PendingCorpusIndex):
                    pending_items.append(prepared)
                elif prepared.status == 'failed':
                    failed_count += 1
                elif prepared.status == 'unchanged':
                    unchanged_count += 1
                if _is_cancelled(cancel_token):
                    _emit_progress(
                        progress,
                        phase='cancelled',
                        started_at=started_at,
                        current_path=file_path,
                        total_found=total_found,
                        processed_count=len(prepared_items),
                        indexed_count=indexed_count,
                        unchanged_count=unchanged_count,
                        failed_count=failed_count,
                        skipped_count=skipped_count,
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
                        results=[item for item in prepared_items if isinstance(item, CorpusIndexResult)],
                    )

        pending_failure_by_note_id: dict[str, CorpusIndexResult] = {}
        success_by_note_id: dict[str, CorpusIndexResult] = {}
        if pending_items and not _is_cancelled(cancel_token):
            chunk_pairs = [(item, chunk) for item in pending_items for chunk in item.chunks]
            embeddings_by_chunk_id: dict[str, list[float]] = {}
            for chunk_batch in _batched(chunk_pairs, resolved_settings.corpus_embedding_batch_size):
                if _is_cancelled(cancel_token):
                    _emit_progress(
                        progress,
                        phase='cancelled',
                        started_at=started_at,
                        current_path=chunk_batch[0][0].source_path if chunk_batch else source_path,
                        total_found=total_found,
                        processed_count=failed_count + unchanged_count,
                        indexed_count=indexed_count,
                        unchanged_count=unchanged_count,
                        failed_count=failed_count,
                        skipped_count=skipped_count,
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
                        results=[item for item in prepared_items if isinstance(item, CorpusIndexResult)],
                    )
                _emit_progress(
                    progress,
                    phase='embedding',
                    started_at=started_at,
                    current_path=chunk_batch[0][0].source_path if chunk_batch else source_path,
                    total_found=total_found,
                    processed_count=failed_count + unchanged_count,
                    indexed_count=indexed_count,
                    unchanged_count=unchanged_count,
                    failed_count=failed_count,
                    skipped_count=skipped_count,
                    message=f'Embedando {len(chunk_batch)} chunks.',
                )
                chunks = [chunk for _, chunk in chunk_batch]
                embeddings = resolved_embedder.embed([chunk.chunk_text for chunk in chunks])
                if len(embeddings) != len(chunks):
                    pending_failure_by_note_id = {
                        item.note.note_id: _failure_result(
                            item.source_path,
                            error_code='INDEXING_FAILED',
                            message='A quantidade de embeddings precisa bater com a quantidade de chunks.',
                            vector_store=resolved_vector_store,
                            embedding_model=resolved_embedder.model_name,
                        )
                        for item in pending_items
                    }
                    failed_count += len(pending_items)
                    pending_items = []
                    break
                for chunk, embedding in zip(chunks, embeddings, strict=True):
                    embeddings_by_chunk_id[chunk.chunk_id] = embedding

            if pending_items:
                _emit_progress(
                    progress,
                    phase='writing',
                    started_at=started_at,
                    current_path=source_path,
                    total_found=total_found,
                    processed_count=failed_count + unchanged_count,
                    indexed_count=indexed_count,
                    unchanged_count=unchanged_count,
                    failed_count=failed_count,
                    skipped_count=skipped_count,
                    message=f'Gravando {len(pending_items)} arquivos indexados.',
                )
                for item in pending_items:
                    resolved_vector_store.delete_by_note_id(item.note.note_id)
                all_chunks = [chunk for item in pending_items for chunk in item.chunks]
                for chunk_batch in _batched(all_chunks, resolved_settings.corpus_upsert_batch_size):
                    resolved_vector_store.upsert_chunks(
                        chunk_batch,
                        [embeddings_by_chunk_id[chunk.chunk_id] for chunk in chunk_batch],
                        embedding_model=resolved_embedder.model_name,
                    )
                for item in pending_items:
                    upsert_note(resolved_connection, item.note)
                    replace_chunks_for_note(resolved_connection, item.note.note_id, item.chunks)
                    indexed_count += 1
                    success_by_note_id[item.note.note_id] = CorpusIndexResult(
                        source_path=str(item.source_path),
                        status='success',
                        note_id=item.note.note_id,
                        chunks_indexed=len(item.chunks),
                        embedding_model=resolved_embedder.model_name,
                        vector_collection_name=resolved_vector_store.collection_name,
                        vector_entries_count=0,
                        message='Document indexed successfully.',
                    )

        vector_entries_count = resolved_vector_store.count()
        results: list[CorpusIndexResult] = []
        for item in prepared_items:
            if isinstance(item, CorpusIndexResult):
                results.append(item)
                continue
            result = success_by_note_id.get(item.note.note_id) or pending_failure_by_note_id.get(item.note.note_id)
            if result is None:
                continue
            result.vector_entries_count = vector_entries_count
            results.append(result)

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
            results=results,
            skipped=discovery.skipped,
        )
    finally:
        if owns_connection:
            resolved_connection.close()
