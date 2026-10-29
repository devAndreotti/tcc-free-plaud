import os
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from escolio.app.config import Settings, get_settings
from escolio.app.paths import ensure_runtime_dirs
from escolio.notes.metadata import find_note_root
from escolio.notes.readable import readable_chunk_text
from escolio.providers.embed import Embedder
from escolio.retrieval.models import Chunk
from escolio.storage.sqlite import (
    delete_note_and_chunks,
    delete_notes_and_chunks,
    get_all_notes,
    get_notes_by_id,
    init_sqlite,
    list_chunks_for_note,
)
from escolio.storage.vector import LocalVectorStore


class NoteSummary(BaseModel):
    note_id: str
    title: str
    source_type: str
    source_path: str
    created_at: str
    tags: list[str] = Field(default_factory=list)
    chunk_count: int = 0


class NoteChunkSummary(BaseModel):
    chunk_id: str
    chunk_index: int
    char_start: int
    char_end: int
    token_count: int
    snippet: str


class NoteDetail(NoteSummary):
    structured_markdown: str
    chunks: list[NoteChunkSummary] = Field(default_factory=list)


class NoteDeleteResult(BaseModel):
    ok: bool
    note_id: str
    deleted_vectors: int


class NoteReindexResult(BaseModel):
    ok: bool
    note_id: str
    status: Literal['success', 'failed', 'cancelled', 'unchanged']
    chunks_indexed: int
    message: str | None = None


@contextmanager
def _managed_connection(settings: Settings, connection: sqlite3.Connection | None) -> Iterator[sqlite3.Connection]:
    if connection is not None:
        yield connection
        return

    managed = init_sqlite(settings.sqlite_path)
    try:
        yield managed
    finally:
        managed.close()


def _vector_store(settings: Settings, vector_store: LocalVectorStore | None) -> LocalVectorStore:
    return vector_store or LocalVectorStore(settings.vector_store_dir, collection_name=settings.vector_collection_name)


def _chunk_counts(connection: sqlite3.Connection) -> dict[str, int]:
    rows = connection.execute(
        """
        SELECT note_id, COUNT(*) AS chunk_count
        FROM chunks
        GROUP BY note_id
        """
    ).fetchall()
    return {str(row['note_id']): int(row['chunk_count']) for row in rows}


def _summary_from_note(note, *, chunk_count: int) -> NoteSummary:
    return NoteSummary(
        note_id=note.note_id,
        title=note.title,
        source_type=note.source_type,
        source_path=str(note.source_path),
        created_at=note.created_at.isoformat(),
        tags=note.tags,
        chunk_count=chunk_count,
    )


def _chunk_summary(chunk: Chunk) -> NoteChunkSummary:
    # Mesmo texto legível do chat; trecho que é só frontmatter aparece como está, para não ficar vazio.
    snippet = (readable_chunk_text(chunk.chunk_text) or chunk.chunk_text).replace('\n', ' ').strip()
    return NoteChunkSummary(
        chunk_id=chunk.chunk_id,
        chunk_index=chunk.chunk_index,
        char_start=chunk.char_start,
        char_end=chunk.char_end,
        token_count=chunk.token_count,
        snippet=snippet[:240],
    )


def list_notes(*, settings: Settings | None = None, connection: sqlite3.Connection | None = None) -> list[NoteSummary]:
    """Lista notas persistidas com metadados suficientes para auditoria visual."""
    resolved_settings = settings or get_settings()
    ensure_runtime_dirs(resolved_settings)
    with _managed_connection(resolved_settings, connection) as resolved_connection:
        counts = _chunk_counts(resolved_connection)
        return [
            _summary_from_note(note, chunk_count=counts.get(note.note_id, 0))
            for note in get_all_notes(resolved_connection)
        ]


def get_note_detail(
    note_id: str,
    *,
    settings: Settings | None = None,
    connection: sqlite3.Connection | None = None,
) -> NoteDetail:
    """Abre uma nota indexada com Markdown estruturado e chunks persistidos."""
    resolved_settings = settings or get_settings()
    ensure_runtime_dirs(resolved_settings)
    with _managed_connection(resolved_settings, connection) as resolved_connection:
        note = get_notes_by_id(resolved_connection, [note_id]).get(note_id)
        if note is None:
            raise KeyError(f'Nota nao encontrada: {note_id}')
        chunks = list_chunks_for_note(resolved_connection, note_id)
        summary = _summary_from_note(note, chunk_count=len(chunks))
        return NoteDetail(
            **summary.model_dump(),
            structured_markdown=note.structured_markdown,
            chunks=[_chunk_summary(chunk) for chunk in chunks],
        )


def delete_note(
    note_id: str,
    *,
    settings: Settings | None = None,
    connection: sqlite3.Connection | None = None,
    vector_store: LocalVectorStore | None = None,
) -> NoteDeleteResult:
    """Remove a nota do SQLite/FTS e os vetores correspondentes no Chroma."""
    resolved_settings = settings or get_settings()
    ensure_runtime_dirs(resolved_settings)
    resolved_vector_store = _vector_store(resolved_settings, vector_store)
    with _managed_connection(resolved_settings, connection) as resolved_connection:
        deleted_vectors = resolved_vector_store.delete_by_note_id(note_id)
        delete_note_and_chunks(resolved_connection, note_id)
    return NoteDeleteResult(ok=True, note_id=note_id, deleted_vectors=deleted_vectors)


def source_key(path: Path | str) -> str:
    """Chave de comparação de caminho: absoluta e normalizada para o SO (no Windows, sem caixa)."""
    return os.path.normcase(os.path.abspath(os.path.expanduser(str(path))))


def _source_matches(source: str, target: str, *, folder: bool, recursive: bool) -> bool:
    key = source_key(source)
    if not folder:
        return key == target
    if not recursive:
        return os.path.dirname(key) == target
    # Com separador no prefixo, `cul` não casa com `culinaria`.
    prefix = target if target.endswith(os.sep) else target + os.sep
    return key.startswith(prefix)


def delete_notes_by_source_path(
    path: Path | str,
    *,
    folder: bool = False,
    recursive: bool = True,
    missing_only: bool = False,
    settings: Settings | None = None,
    connection: sqlite3.Connection | None = None,
    vector_store: LocalVectorStore | None = None,
) -> int:
    """Remove do SQLite/FTS e do Chroma as notas cujo `source_path` é `path` (ou está sob a pasta `path`).

    `missing_only` restringe a remoção a notas cujo arquivo não existe mais no disco.
    Devolve quantas notas foram removidas.
    """
    resolved_settings = settings or get_settings()
    ensure_runtime_dirs(resolved_settings)
    resolved_vector_store = _vector_store(resolved_settings, vector_store)
    target = source_key(path)
    with _managed_connection(resolved_settings, connection) as resolved_connection:
        note_ids = [
            note.note_id
            for note in get_all_notes(resolved_connection)
            if _source_matches(note.source_path, target, folder=folder, recursive=recursive)
            and (not missing_only or not Path(note.source_path).exists())
        ]
        if note_ids:
            resolved_vector_store.delete_by_note_ids(note_ids)
            delete_notes_and_chunks(resolved_connection, note_ids)
    return len(note_ids)


def reindex_note(
    note_id: str,
    *,
    settings: Settings | None = None,
    connection: sqlite3.Connection | None = None,
    vector_store: LocalVectorStore | None = None,
    embedder: Embedder | None = None,
    runtime=None,
) -> NoteReindexResult:
    """Reindexa uma nota a partir do source_path já salvo no banco."""
    resolved_settings = settings or get_settings()
    ensure_runtime_dirs(resolved_settings)
    with _managed_connection(resolved_settings, connection) as resolved_connection:
        detail = get_note_detail(note_id, settings=resolved_settings, connection=resolved_connection)
        source_path = Path(detail.source_path)
        if not source_path.exists():
            return NoteReindexResult(
                ok=False,
                note_id=note_id,
                status='failed',
                chunks_indexed=0,
                message=f'Arquivo original nao encontrado: {source_path}',
            )

        resolved_vector_store = vector_store or (runtime.get_vector_store() if runtime is not None else None)
        resolved_embedder = embedder or (runtime.get_embedder() if runtime is not None else None)

        from escolio.corpus.service import index_corpus_file

        result = index_corpus_file(
            source_path,
            settings=resolved_settings,
            connection=resolved_connection,
            vector_store=resolved_vector_store,
            embedder=resolved_embedder,
            source_root=find_note_root(source_path, note_id),
        )
        return NoteReindexResult(
            ok=result.status in {'success', 'unchanged'},
            note_id=result.note_id or note_id,
            status=result.status,
            chunks_indexed=result.chunks_indexed,
            message=result.message,
        )
