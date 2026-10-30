import sqlite3

from escolio.app.config import Settings, get_settings
from escolio.app.paths import ensure_runtime_dirs
from escolio.corpus.models import CorpusStatusResult
from escolio.storage.sqlite import (
    count_chunks,
    count_fts_chunks,
    count_notes,
    init_sqlite,
    list_chunk_ids,
)
from escolio.storage.vector import LocalVectorStore


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
