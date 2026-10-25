import sqlite3
from collections.abc import Callable
from pathlib import Path

from escolio.app.config import Settings, get_settings
from escolio.app.paths import ensure_runtime_dirs
from escolio.corpus.index_commit import (
    PendingCorpusIndex,
    PreparationFailure,
    delete_superseded_source_notes,
)
from escolio.corpus.index_results import (
    error_code_for_exception,
    failure_result,
    unchanged_result,
)
from escolio.corpus.models import CorpusIndexResult
from escolio.ingest.models import IngestedDocument
from escolio.ingest.validators import has_indexable_content
from escolio.notes.extraction import enrich_note
from escolio.notes.structurer import structure_document
from escolio.providers.embed import Embedder
from escolio.retrieval.indexer import index_note
from escolio.storage.sqlite import (
    corpus_root_for_path,
    get_note_content_hash,
    get_note_title,
    init_sqlite,
    list_chunk_ids_for_note,
    note_chunks_match_config,
    replace_chunks_for_note,
    split_ignored,
    upsert_note,
)
from escolio.storage.vector import LocalVectorStore

# loader e get_embedder_fn chegam por parametro (a fachada service passa load_document e get_embedder
# em tempo de chamada), para que monkeypatch em escolio.corpus.service continue valendo.
LoaderFn = Callable[[Path], IngestedDocument]
EmbedderFactory = Callable[..., Embedder]


def load_structure_chunk_corpus_file(
    path: Path,
    *,
    chunk_size: int,
    overlap: int,
    loader: LoaderFn,
    source_root: Path | None = None,
) -> PendingCorpusIndex | PreparationFailure:
    try:
        document = loader(path)
        if not has_indexable_content(document):
            raise ValueError('EMPTY_CONTENT')
        # Só age com `extract_structure` ligada nas settings (desligada por padrão: custa uma chamada de LLM por nota).
        note = enrich_note(structure_document(document, source_root=source_root, hash_unrooted=True))
        return PendingCorpusIndex(
            source_path=document.source_path,
            note=note,
            chunks=index_note(note, chunk_size=chunk_size, overlap=overlap),
        )
    except (OSError, ValueError) as exc:
        return PreparationFailure(
            source_path=path,
            error_code=error_code_for_exception(exc),
            message=str(exc),
        )


def resolve_prepared_corpus_file(
    prepared: PendingCorpusIndex | PreparationFailure,
    *,
    connection: sqlite3.Connection,
    vector_store: LocalVectorStore,
    embedder: Embedder,
    chunk_size: int,
    overlap: int,
) -> PendingCorpusIndex | CorpusIndexResult:
    if isinstance(prepared, PreparationFailure):
        return failure_result(
            prepared.source_path,
            error_code=prepared.error_code,
            message=prepared.message,
            vector_store=vector_store,
            embedding_model=embedder.model_name,
        )

    existing_hash = get_note_content_hash(connection, prepared.note.note_id)
    existing_title = get_note_title(connection, prepared.note.note_id)
    existing_chunk_ids = list_chunk_ids_for_note(connection, prepared.note.note_id)
    chunks_match_config = note_chunks_match_config(
        connection,
        prepared.note.note_id,
        chunk_size=chunk_size,
        overlap=overlap,
    )
    # Título recalculado (ex.: regra de frontmatter) também conta como mudança: sem isso a nota nunca seria corrigida.
    if (
        existing_hash == prepared.note.content_hash
        and existing_title == prepared.note.title
        and chunks_match_config
        and vector_store.has_chunk_ids(existing_chunk_ids)
    ):
        return unchanged_result(
            prepared.note,
            source_path=prepared.source_path,
            chunk_ids=existing_chunk_ids,
            vector_store=vector_store,
            embedding_model=embedder.model_name,
        )
    return prepared


def prepare_corpus_file(
    path: Path,
    *,
    connection: sqlite3.Connection,
    vector_store: LocalVectorStore,
    embedder: Embedder,
    chunk_size: int,
    overlap: int,
    loader: LoaderFn,
    source_root: Path | None = None,
) -> PendingCorpusIndex | CorpusIndexResult:
    prepared = load_structure_chunk_corpus_file(
        path,
        chunk_size=chunk_size,
        overlap=overlap,
        loader=loader,
        source_root=source_root,
    )
    return resolve_prepared_corpus_file(
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
    loader: LoaderFn,
    get_embedder_fn: EmbedderFactory,
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
    resolved_embedder = embedder or get_embedder_fn(
        resolved_settings.embedding_model,
        device=resolved_settings.embedding_device,
    )
    resolved_chunk_size = chunk_size or resolved_settings.default_chunk_size
    resolved_overlap = resolved_settings.default_chunk_overlap if overlap is None else overlap

    try:
        # Arquivo que o usuário mandou ignorar fica fora do índice (watcher, área de soltar, "tentar de novo").
        if not split_ignored(resolved_connection, [source_path])[0]:
            return CorpusIndexResult(
                source_path=str(source_path),
                status='unchanged',
                embedding_model=resolved_embedder.model_name,
                vector_collection_name=resolved_vector_store.collection_name,
                vector_entries_count=resolved_vector_store.count(),
                message='Arquivo ignorado na indexação.',
            )
        document = loader(source_path)
        if not has_indexable_content(document):
            raise ValueError('EMPTY_CONTENT')

        # Arquivo de uma pasta já indexada (watcher, área de soltar) mantém o note_id da Fila.
        if source_root is None:
            source_root = corpus_root_for_path(resolved_connection, source_path)
        note = enrich_note(structure_document(document, source_root=source_root, hash_unrooted=True), resolved_settings)
        existing_hash = get_note_content_hash(resolved_connection, note.note_id)
        existing_title = get_note_title(resolved_connection, note.note_id)
        existing_chunk_ids = list_chunk_ids_for_note(resolved_connection, note.note_id)
        chunks_match_config = note_chunks_match_config(
            resolved_connection,
            note.note_id,
            chunk_size=resolved_chunk_size,
            overlap=resolved_overlap,
        )
        if (
            existing_hash == note.content_hash
            and existing_title == note.title
            and chunks_match_config
            and resolved_vector_store.has_chunk_ids(existing_chunk_ids)
        ):
            return unchanged_result(
                note,
                source_path=document.source_path,
                chunk_ids=existing_chunk_ids,
                vector_store=resolved_vector_store,
                embedding_model=resolved_embedder.model_name,
            )

        chunks = index_note(note, chunk_size=resolved_chunk_size, overlap=resolved_overlap)
        embeddings = resolved_embedder.embed([chunk.chunk_text for chunk in chunks])
        if len(embeddings) != len(chunks):
            raise ValueError('A quantidade de vetores precisa bater com a quantidade de trechos.')

        delete_superseded_source_notes(resolved_connection, resolved_vector_store, note)
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
    except (OSError, ValueError) as exc:
        return failure_result(
            source_path,
            error_code=error_code_for_exception(exc),
            message=str(exc),
            vector_store=resolved_vector_store,
            embedding_model=resolved_embedder.model_name,
        )
    finally:
        if owns_connection:
            resolved_connection.close()
