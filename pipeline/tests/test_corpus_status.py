from pathlib import Path

from free_plaud.app.config import Settings
from free_plaud.corpus.service import get_corpus_status, index_corpus_file
from free_plaud.retrieval.models import Chunk
from free_plaud.storage.sqlite import get_notes_by_id, init_sqlite, list_chunks, replace_chunks_for_note, upsert_note
from free_plaud.storage.vector import LocalVectorStore


class FakeEmbedder:
    model_name = 'fake-hash'

    def embed(self, texts: list[str]) -> list[list[float]]:
        embeddings: list[list[float]] = []
        for text in texts:
            vector = [0.0] * 16
            for token in text.lower().split():
                vector[sum(ord(char) for char in token) % len(vector)] += 1.0
            embeddings.append(vector)
        return embeddings


def _settings(tmp_path: Path, collection_name: str = 'corpus_status_test') -> Settings:
    return Settings(
        workspace_dir=tmp_path,
        data_dir=tmp_path / 'data',
        notes_dir=tmp_path / 'data' / 'corpus' / 'notes',
        datasets_dir=tmp_path / 'data' / 'datasets',
        results_dir=tmp_path / 'data' / 'results',
        sqlite_path=tmp_path / 'data' / 'results' / 'free_plaud.sqlite3',
        vector_store_dir=tmp_path / 'data' / 'results' / 'vector_store',
        vector_collection_name=collection_name,
        embedding_model='fake-hash',
        default_chunk_size=140,
        default_chunk_overlap=20,
    )


def _chunk(chunk_id: str, note_id: str, text: str) -> Chunk:
    return Chunk(
        chunk_id=chunk_id,
        note_id=note_id,
        note_version=1,
        chunk_index=0,
        char_start=0,
        char_end=len(text),
        chunk_size=140,
        overlap=20,
        chunk_text=text,
        token_count=len(text.split()),
        strategy='fixed_window',
        normalized_text_sha256=f'{chunk_id}-normalized',
        text_sha256=f'{chunk_id}-text',
        pipeline_version='test',
    )


def test_corpus_status_reports_empty_clean_and_stale_vectors(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    connection = init_sqlite(settings.sqlite_path)
    vector_store = LocalVectorStore(settings.vector_store_dir, collection_name=settings.vector_collection_name)

    empty = get_corpus_status(settings=settings, connection=connection, vector_store=vector_store)
    assert empty.status == 'empty'
    assert empty.notes_count == 0
    assert empty.sqlite_chunks_count == 0
    assert empty.vector_chunks_count == 0

    source = tmp_path / 'broker.md'
    source.write_text('# Broker\n\nRabbitMQ foi adotado como message broker padrao.\n', encoding='utf-8')
    index_result = index_corpus_file(
        source,
        settings=settings,
        connection=connection,
        vector_store=vector_store,
        embedder=FakeEmbedder(),
    )

    clean = get_corpus_status(settings=settings, connection=connection, vector_store=vector_store)
    assert index_result.status == 'success'
    assert clean.status == 'clean'
    assert clean.notes_count == 1
    assert clean.sqlite_chunks_count == index_result.chunks_indexed
    assert clean.vector_chunks_count == index_result.chunks_indexed
    assert clean.stale_vector_chunks_count == 0
    assert clean.missing_vector_chunks_count == 0

    stale_chunk = _chunk('stale-chunk-1', 'stale-note', 'Conteudo stale que nao existe no SQLite.')
    vector_store.upsert_chunks([stale_chunk], [[1.0] + [0.0] * 15], embedding_model='fake-hash')

    inconsistent = get_corpus_status(settings=settings, connection=connection, vector_store=vector_store)
    assert inconsistent.status == 'inconsistent'
    assert inconsistent.stale_vector_chunks_count == 1
    assert inconsistent.missing_vector_chunks_count == 0
    assert inconsistent.orphan_vector_note_ids == ['stale-note']
    assert 'stale-chunk-1' in inconsistent.stale_vector_chunk_ids


def test_corpus_status_reports_sqlite_only_and_missing_vectors(tmp_path: Path) -> None:
    settings = _settings(tmp_path, collection_name='corpus_status_sqlite_only_test')
    connection = init_sqlite(settings.sqlite_path)
    vector_store = LocalVectorStore(settings.vector_store_dir, collection_name=settings.vector_collection_name)
    source = tmp_path / 'somente-sqlite.md'
    source.write_text(
        '# SQLite\n\n'
        'Apenas SQLite deve existir neste caso com muitas frases repetidas para gerar varios chunks. ' * 80,
        encoding='utf-8',
    )
    indexed = index_corpus_file(
        source,
        settings=settings,
        connection=connection,
        vector_store=vector_store,
        embedder=FakeEmbedder(),
    )
    assert indexed.chunks_indexed > 1
    note = next(iter(get_notes_by_id(connection, [indexed.note_id]).values()))
    chunks = list_chunks(connection)

    vector_store.reset()
    sqlite_only = get_corpus_status(settings=settings, connection=connection, vector_store=vector_store)
    assert sqlite_only.status == 'sqlite_only'
    assert sqlite_only.missing_vector_chunks_count == indexed.chunks_indexed

    upsert_note(connection, note)
    replace_chunks_for_note(connection, note.note_id, chunks)
    vector_store.upsert_chunks(chunks[:-1], FakeEmbedder().embed([chunk.chunk_text for chunk in chunks[:-1]]), embedding_model='fake-hash')

    missing = get_corpus_status(settings=settings, connection=connection, vector_store=vector_store)
    assert missing.status == 'inconsistent'
    assert missing.missing_vector_chunks_count == 1


def test_corpus_status_reports_embedding_model_mismatch(tmp_path: Path) -> None:
    settings = _settings(tmp_path, collection_name='corpus_status_embedding_model_mismatch')
    connection = init_sqlite(settings.sqlite_path)
    vector_store = LocalVectorStore(settings.vector_store_dir, collection_name=settings.vector_collection_name)
    source = tmp_path / 'broker.md'
    source.write_text('# Broker\n\nRabbitMQ foi adotado como message broker padrao.\n', encoding='utf-8')
    indexed = index_corpus_file(
        source,
        settings=settings,
        connection=connection,
        vector_store=vector_store,
        embedder=FakeEmbedder(),
    )
    changed_settings = settings.model_copy(update={'embedding_model': 'chroma-default'})

    status = get_corpus_status(settings=changed_settings, connection=connection, vector_store=vector_store)

    assert indexed.status == 'success'
    assert status.status == 'inconsistent'
    assert status.embedding_model_mismatch_count == indexed.chunks_indexed
    assert status.embedding_model_mismatch_chunk_ids
