from pathlib import Path

from escolio.app.config import Settings
from escolio.corpus.service import index_corpus_path, reset_corpus
from escolio.storage.models import BenchmarkRunRecord
from escolio.storage.sqlite import (
    count_chunks,
    count_notes,
    init_sqlite,
    insert_benchmark_run,
)
from escolio.storage.vector import LocalVectorStore


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
        sqlite_path=tmp_path / 'data' / 'results' / 'escolio.sqlite3',
        vector_store_dir=tmp_path / 'data' / 'results' / 'vector_store',
        vector_collection_name='corpus_reset_test',
        embedding_model='fake-hash',
        default_chunk_size=120,
        default_chunk_overlap=20,
    )


def _build_corpus(root: Path) -> None:
    root.mkdir()
    (root / 'broker.md').write_text('# Broker\n\nRabbitMQ foi adotado como broker.\n', encoding='utf-8')
    (root / 'runbook.md').write_text('# Runbook\n\nO time SRE ficou responsavel pelo runbook.\n', encoding='utf-8')


def test_reset_corpus_dry_run_reports_counts_without_deleting(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    root = tmp_path / 'corpus'
    _build_corpus(root)
    connection = init_sqlite(settings.sqlite_path)
    vector_store = LocalVectorStore(settings.vector_store_dir, collection_name=settings.vector_collection_name)
    index_corpus_path(root, settings=settings, connection=connection, vector_store=vector_store, embedder=FakeEmbedder())

    result = reset_corpus(settings=settings, connection=connection, vector_store=vector_store, dry_run=True)

    assert result.status == 'preview'
    assert result.dry_run is True
    assert result.would_delete_notes == 2
    assert result.would_delete_chunks == count_chunks(connection)
    assert result.would_delete_vectors == vector_store.count()
    assert result.deleted_notes == 0
    assert result.deleted_chunks == 0
    assert result.deleted_vectors == 0
    assert count_notes(connection) == 2
    assert vector_store.count() == result.would_delete_vectors


def test_reset_corpus_yes_clears_notes_chunks_and_vectors_but_keeps_benchmark(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    root = tmp_path / 'corpus'
    _build_corpus(root)
    connection = init_sqlite(settings.sqlite_path)
    vector_store = LocalVectorStore(settings.vector_store_dir, collection_name=settings.vector_collection_name)
    index_corpus_path(root, settings=settings, connection=connection, vector_store=vector_store, embedder=FakeEmbedder())
    insert_benchmark_run(
        connection,
        BenchmarkRunRecord(
            benchmark_run_id='bench-1',
            run_name='baseline',
            dataset_name='demo',
            corpus_snapshot='before-reset',
            retrieval_strategy='hybrid',
            chunking_strategy='fixed_window',
            embedding_model='fake-hash',
            top_k=3,
            query_count=0,
            pipeline_version='test',
            status='success',
        ),
    )

    result = reset_corpus(settings=settings, connection=connection, vector_store=vector_store, dry_run=False)
    second = reset_corpus(settings=settings, connection=connection, vector_store=vector_store, dry_run=False)

    assert result.status == 'reset'
    assert result.dry_run is False
    assert result.deleted_notes == 2
    assert result.deleted_chunks > 0
    assert result.deleted_vectors > 0
    assert count_notes(connection) == 0
    assert count_chunks(connection) == 0
    assert vector_store.count() == 0
    assert connection.execute('SELECT COUNT(*) AS total FROM benchmark_runs').fetchone()['total'] == 1
    assert second.status == 'reset'
    assert second.deleted_notes == 0
    assert second.deleted_chunks == 0
    assert second.deleted_vectors == 0


def test_reset_corpus_preserves_sqlite_when_vector_reset_fails(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    root = tmp_path / 'corpus'
    _build_corpus(root)
    connection = init_sqlite(settings.sqlite_path)
    vector_store = LocalVectorStore(settings.vector_store_dir, collection_name=settings.vector_collection_name)
    index_corpus_path(root, settings=settings, connection=connection, vector_store=vector_store, embedder=FakeEmbedder())

    class FailingVectorStore:
        collection_name = vector_store.collection_name

        def count(self) -> int:
            return vector_store.count()

        def reset(self) -> None:
            raise RuntimeError('vector reset failed')

    notes_before = count_notes(connection)
    chunks_before = count_chunks(connection)

    try:
        reset_corpus(settings=settings, connection=connection, vector_store=FailingVectorStore(), dry_run=False)  # type: ignore[arg-type]
    except RuntimeError as exc:
        assert str(exc) == 'vector reset failed'
    else:
        raise AssertionError('reset_corpus deveria propagar falha de reset vetorial')

    assert count_notes(connection) == notes_before
    assert count_chunks(connection) == chunks_before
