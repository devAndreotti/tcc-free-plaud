import sqlite3
from collections.abc import Callable
from pathlib import Path
from time import perf_counter

from free_plaud.app.config import Settings, get_settings
from free_plaud.app.paths import ensure_runtime_dirs
from free_plaud.corpus.discovery import discover_corpus_files
from free_plaud.corpus.models import (
    CorpusIndexBatchResult,
    CorpusIndexProgress,
    CorpusIndexResult,
    CorpusRebuildResult,
    CorpusResetResult,
    CorpusStatusResult,
)
from free_plaud.ingest.loaders import load_document
from free_plaud.notes.structurer import structure_document
from free_plaud.providers.embed import Embedder, get_embedder
from free_plaud.retrieval.indexer import index_note
from free_plaud.storage.sqlite import (
    count_chunks,
    count_notes,
    delete_corpus_notes_and_chunks,
    init_sqlite,
    list_chunk_ids,
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


def _batch_status(indexed_count: int, failed_count: int) -> str:
    if indexed_count > 0 and failed_count == 0:
        return 'success'
    if indexed_count > 0:
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
    started_at = perf_counter()

    try:
        if source_path.is_file():
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
            _emit_progress(
                progress,
                phase='writing',
                started_at=started_at,
                current_path=source_path,
                total_found=1,
                processed_count=1,
                indexed_count=indexed_count,
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
                failed_count=failed_count,
                message='Indexacao concluida.',
            )
            return CorpusIndexBatchResult(
                source_path=str(source_path),
                recursive=recursive,
                status=_batch_status(indexed_count, failed_count),  # type: ignore[arg-type]
                total_found=1,
                indexed_count=indexed_count,
                failed_count=failed_count,
                skipped_count=0,
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

        results: list[CorpusIndexResult] = []
        indexed_count = 0
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
        for file_path in discovery.files:
            processed_count = len(results)
            _emit_progress(
                progress,
                phase='loading',
                started_at=started_at,
                current_path=file_path,
                total_found=total_found,
                processed_count=processed_count,
                indexed_count=indexed_count,
                failed_count=failed_count,
                skipped_count=skipped_count,
                message=f'Processando {file_path.name}',
            )
            _emit_progress(
                progress,
                phase='embedding',
                started_at=started_at,
                current_path=file_path,
                total_found=total_found,
                processed_count=processed_count,
                indexed_count=indexed_count,
                failed_count=failed_count,
                skipped_count=skipped_count,
                message=f'Estruturando e embedando {file_path.name}',
            )
            result = index_corpus_file(
                file_path,
                settings=resolved_settings,
                connection=resolved_connection,
                vector_store=resolved_vector_store,
                embedder=resolved_embedder,
                chunk_size=chunk_size,
                overlap=overlap,
            )
            results.append(result)
            if result.status == 'success':
                indexed_count += 1
            elif result.status == 'failed':
                failed_count += 1
            _emit_progress(
                progress,
                phase='writing',
                started_at=started_at,
                current_path=file_path,
                total_found=total_found,
                processed_count=len(results),
                indexed_count=indexed_count,
                failed_count=failed_count,
                skipped_count=skipped_count,
                message=f'Finalizado {file_path.name}',
            )

        _emit_progress(
            progress,
            phase='finished',
            started_at=started_at,
            total_found=total_found,
            processed_count=len(results),
            indexed_count=indexed_count,
            failed_count=failed_count,
            skipped_count=skipped_count,
            message='Indexacao concluida.',
        )
        return CorpusIndexBatchResult(
            source_path=str(source_path),
            recursive=recursive,
            status=_batch_status(indexed_count, failed_count),  # type: ignore[arg-type]
            total_found=len(discovery.files),
            indexed_count=indexed_count,
            failed_count=failed_count,
            skipped_count=len(discovery.skipped),
            results=results,
            skipped=discovery.skipped,
        )
    finally:
        if owns_connection:
            resolved_connection.close()
