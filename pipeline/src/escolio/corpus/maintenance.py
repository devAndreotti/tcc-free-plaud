import sqlite3
from pathlib import Path

from escolio.app.config import Settings, get_settings
from escolio.app.paths import ensure_runtime_dirs
from escolio.corpus.jobs import corpus_write_lock
from escolio.corpus.models import CorpusResetResult
from escolio.notes.service import delete_notes_by_source_path
from escolio.storage.sqlite import (
    count_chunks,
    count_notes,
    delete_corpus_notes_and_chunks,
    forget_corpus_root,
    init_sqlite,
)
from escolio.storage.vector import LocalVectorStore


def remove_corpus_root(
    root: Path | str,
    *,
    settings: Settings | None = None,
    connection: sqlite3.Connection | None = None,
    vector_store: LocalVectorStore | None = None,
) -> int:
    """Tira uma pasta do corpus: remove as notas sob ela (SQLite e Chroma) e esquece a raiz.

    Não apaga nada do disco. Devolve quantas notas foram removidas.
    """
    resolved_settings = settings or get_settings()
    ensure_runtime_dirs(resolved_settings)
    owns_connection = connection is None
    resolved_connection = connection or init_sqlite(resolved_settings.sqlite_path)
    resolved_vector_store = vector_store or LocalVectorStore(
        resolved_settings.vector_store_dir,
        collection_name=resolved_settings.vector_collection_name,
    )
    try:
        with corpus_write_lock:
            removed = delete_notes_by_source_path(
                root,
                folder=True,
                recursive=True,
                settings=resolved_settings,
                connection=resolved_connection,
                vector_store=resolved_vector_store,
            )
            forget_corpus_root(resolved_connection, root)
        return removed
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
