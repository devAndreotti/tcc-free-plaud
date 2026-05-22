from pathlib import Path

from free_plaud.app.config import Settings
from free_plaud.corpus.service import index_corpus_file, rebuild_corpus
from free_plaud.storage.sqlite import count_chunks, count_notes, init_sqlite
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


def _settings(tmp_path: Path) -> Settings:
    return Settings(
        workspace_dir=tmp_path,
        data_dir=tmp_path / 'data',
        notes_dir=tmp_path / 'data' / 'corpus' / 'notes',
        datasets_dir=tmp_path / 'data' / 'datasets',
        results_dir=tmp_path / 'data' / 'results',
        sqlite_path=tmp_path / 'data' / 'results' / 'free_plaud.sqlite3',
        vector_store_dir=tmp_path / 'data' / 'results' / 'vector_store',
        vector_collection_name='corpus_rebuild_test',
        embedding_model='fake-hash',
        default_chunk_size=120,
        default_chunk_overlap=20,
    )


def _target_corpus(root: Path) -> None:
    root.mkdir()
    (root / 'broker.md').write_text('# Broker\n\nRabbitMQ foi adotado como broker.\n', encoding='utf-8')
    (root / 'runbook.md').write_text('# Runbook\n\nO time SRE ficou responsavel pelo runbook.\n', encoding='utf-8')
    (root / 'ignorado.docx').write_text('fora do escopo', encoding='utf-8')


def _dirty_source(tmp_path: Path) -> Path:
    source = tmp_path / 'velho.md'
    source.write_text('# Velho\n\nConteudo antigo que deve sumir depois do rebuild.\n', encoding='utf-8')
    return source


def test_rebuild_corpus_dry_run_keeps_current_corpus(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    target = tmp_path / 'target'
    _target_corpus(target)
    connection = init_sqlite(settings.sqlite_path)
    vector_store = LocalVectorStore(settings.vector_store_dir, collection_name=settings.vector_collection_name)
    index_corpus_file(_dirty_source(tmp_path), settings=settings, connection=connection, vector_store=vector_store, embedder=FakeEmbedder())
    notes_before = count_notes(connection)
    chunks_before = count_chunks(connection)
    vectors_before = vector_store.count()

    result = rebuild_corpus(
        target,
        settings=settings,
        connection=connection,
        vector_store=vector_store,
        embedder=FakeEmbedder(),
        recursive=True,
        dry_run=True,
    )

    assert result.status == 'preview'
    assert result.dry_run is True
    assert result.reset.status == 'preview'
    assert result.index_result is None
    assert count_notes(connection) == notes_before
    assert count_chunks(connection) == chunks_before
    assert vector_store.count() == vectors_before


def test_rebuild_corpus_yes_resets_and_indexes_target_only(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    target = tmp_path / 'target'
    _target_corpus(target)
    connection = init_sqlite(settings.sqlite_path)
    vector_store = LocalVectorStore(settings.vector_store_dir, collection_name=settings.vector_collection_name)
    index_corpus_file(_dirty_source(tmp_path), settings=settings, connection=connection, vector_store=vector_store, embedder=FakeEmbedder())

    result = rebuild_corpus(
        target,
        settings=settings,
        connection=connection,
        vector_store=vector_store,
        embedder=FakeEmbedder(),
        recursive=True,
        dry_run=False,
    )

    assert result.status == 'success'
    assert result.dry_run is False
    assert result.reset.status == 'reset'
    assert result.index_result is not None
    assert result.index_result.indexed_count == 2
    assert result.index_result.skipped_count == 1
    assert result.after_status is not None
    assert result.after_status.status == 'clean'
    assert result.after_status.notes_count == 2
    assert result.after_status.sqlite_chunks_count == result.after_status.vector_chunks_count
    assert connection.execute("SELECT COUNT(*) AS total FROM notes WHERE note_id = 'velho'").fetchone()['total'] == 0


def test_rebuild_corpus_missing_path_returns_structured_failure(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    connection = init_sqlite(settings.sqlite_path)
    vector_store = LocalVectorStore(settings.vector_store_dir, collection_name=settings.vector_collection_name)

    result = rebuild_corpus(
        tmp_path / 'nao-existe',
        settings=settings,
        connection=connection,
        vector_store=vector_store,
        embedder=FakeEmbedder(),
        recursive=True,
        dry_run=False,
    )

    assert result.status == 'failed'
    assert result.error_code == 'INPUT_NOT_FOUND'
    assert result.reset is None
    assert result.index_result is None
