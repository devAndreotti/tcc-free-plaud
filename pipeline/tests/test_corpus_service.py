from pathlib import Path

from free_plaud.app.config import Settings
from free_plaud.corpus.service import get_corpus_status, index_corpus_file, index_corpus_path
from free_plaud.storage.sqlite import connect_sqlite, init_sqlite, list_chunk_ids
from free_plaud.storage.vector import LocalVectorStore


class FakeEmbedder:
    model_name = 'fake-hash'

    def embed(self, texts: list[str]) -> list[list[float]]:
        embeddings: list[list[float]] = []
        for text in texts:
            vector = [0.0] * 16
            for token in text.lower().split():
                slot = sum(ord(char) for char in token) % len(vector)
                vector[slot] += 1.0
            embeddings.append(vector)
        return embeddings


class BrokenEmbedder(FakeEmbedder):
    model_name = 'broken'

    def embed(self, texts: list[str]) -> list[list[float]]:
        return super().embed(texts[:-1])


def _settings(tmp_path: Path) -> Settings:
    return Settings(
        workspace_dir=tmp_path,
        data_dir=tmp_path / 'data',
        notes_dir=tmp_path / 'data' / 'corpus' / 'notes',
        datasets_dir=tmp_path / 'data' / 'datasets',
        results_dir=tmp_path / 'data' / 'results',
        sqlite_path=tmp_path / 'data' / 'results' / 'free_plaud.sqlite3',
        vector_store_dir=tmp_path / 'data' / 'results' / 'vector_store',
        vector_collection_name='corpus_service_test',
        embedding_model='fake-hash',
        default_chunk_size=120,
        default_chunk_overlap=20,
    )


def test_index_corpus_file_persists_note_chunks_and_embeddings(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    source = tmp_path / 'plataforma.md'
    source.write_text(
        '# Plataforma\n\n'
        'A plataforma adotou RabbitMQ como message broker padrao.\n'
        'O runbook de operacao ficou sob responsabilidade do time SRE.\n',
        encoding='utf-8',
    )

    result = index_corpus_file(source, settings=settings, embedder=FakeEmbedder())

    assert result.status == 'success'
    assert result.note_id == 'plataforma'
    assert result.chunks_indexed >= 1
    assert result.embedding_model == 'fake-hash'
    assert result.vector_collection_name == 'corpus_service_test'
    assert result.vector_entries_count == result.chunks_indexed

    connection = connect_sqlite(settings.sqlite_path)
    note_row = connection.execute('SELECT note_id, source_path FROM notes WHERE note_id = ?', ('plataforma',)).fetchone()
    chunk_rows = connection.execute('SELECT chunk_id FROM chunks WHERE note_id = ?', ('plataforma',)).fetchall()

    assert note_row['source_path'] == str(source)
    assert len(chunk_rows) == result.chunks_indexed


def test_index_corpus_file_is_idempotent_for_same_file(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    source = tmp_path / 'reindexavel.md'
    source.write_text(
        '# Reindexavel\n\n'
        'O SQLite deve substituir chunks da mesma nota sem duplicar registros.\n'
        'O Chroma deve receber upsert com os mesmos ids de chunk.\n',
        encoding='utf-8',
    )

    first = index_corpus_file(source, settings=settings, embedder=FakeEmbedder())
    second = index_corpus_file(source, settings=settings, embedder=FakeEmbedder())

    connection = connect_sqlite(settings.sqlite_path)
    note_count = connection.execute('SELECT COUNT(*) AS total FROM notes WHERE note_id = ?', ('reindexavel',)).fetchone()
    chunk_count = connection.execute('SELECT COUNT(*) AS total FROM chunks WHERE note_id = ?', ('reindexavel',)).fetchone()

    assert first.status == 'success'
    assert second.status == 'success'
    assert second.chunks_indexed == first.chunks_indexed
    assert second.vector_entries_count == first.vector_entries_count
    assert note_count['total'] == 1
    assert chunk_count['total'] == first.chunks_indexed


def test_index_corpus_file_removes_old_vectors_when_chunk_ids_change(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    source = tmp_path / 'rechunk.md'
    source.write_text(
        '# Rechunk\n\n'
        + 'A reindexacao precisa remover vetores antigos antes de gravar novos chunks. ' * 40,
        encoding='utf-8',
    )
    connection = init_sqlite(settings.sqlite_path)
    vector_store = LocalVectorStore(settings.vector_store_dir, collection_name=settings.vector_collection_name)

    first = index_corpus_file(
        source,
        settings=settings,
        connection=connection,
        vector_store=vector_store,
        embedder=FakeEmbedder(),
        chunk_size=120,
        overlap=20,
    )
    first_chunk_ids = list_chunk_ids(connection)
    second = index_corpus_file(
        source,
        settings=settings,
        connection=connection,
        vector_store=vector_store,
        embedder=FakeEmbedder(),
        chunk_size=100,
        overlap=20,
    )
    second_chunk_ids = list_chunk_ids(connection)
    status = get_corpus_status(settings=settings, connection=connection, vector_store=vector_store)

    assert first.status == 'success'
    assert second.status == 'success'
    assert first_chunk_ids != second_chunk_ids
    assert vector_store.count() == second.chunks_indexed
    assert status.status == 'clean'
    assert status.stale_vector_chunks_count == 0
    assert status.missing_vector_chunks_count == 0


def test_index_corpus_file_returns_failure_without_partial_write_for_invalid_input(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    source = tmp_path / 'vazio.md'
    source.write_text('   \n\n', encoding='utf-8')

    result = index_corpus_file(source, settings=settings, embedder=FakeEmbedder())

    assert result.status == 'failed'
    assert result.error_code == 'EMPTY_CONTENT'
    assert result.chunks_indexed == 0
    assert result.vector_entries_count == 0

    connection = connect_sqlite(settings.sqlite_path)
    note_count = connection.execute('SELECT COUNT(*) AS total FROM notes').fetchone()
    chunk_count = connection.execute('SELECT COUNT(*) AS total FROM chunks').fetchone()

    assert note_count['total'] == 0
    assert chunk_count['total'] == 0


def test_index_corpus_file_reports_unsupported_extension(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    source = tmp_path / 'planilha.xlsx'
    source.write_text('conteudo', encoding='utf-8')

    result = index_corpus_file(source, settings=settings, embedder=FakeEmbedder())

    assert result.status == 'failed'
    assert result.error_code == 'UNSUPPORTED_MEDIA_TYPE'
    assert result.note_id is None
    assert result.chunks_indexed == 0


def test_index_corpus_file_reports_indexing_failure_without_partial_sqlite_write(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    source = tmp_path / 'broken.md'
    source.write_text(
        '# Broken\n\n'
        'Este documento deve falhar antes de persistir nota e chunks quando embeddings nao batem.\n',
        encoding='utf-8',
    )

    result = index_corpus_file(source, settings=settings, embedder=BrokenEmbedder())

    assert result.status == 'failed'
    assert result.error_code == 'INDEXING_FAILED'
    assert result.note_id is None
    assert result.chunks_indexed == 0

    connection = connect_sqlite(settings.sqlite_path)
    note_count = connection.execute('SELECT COUNT(*) AS total FROM notes').fetchone()
    chunk_count = connection.execute('SELECT COUNT(*) AS total FROM chunks').fetchone()

    assert note_count['total'] == 0
    assert chunk_count['total'] == 0


def test_index_corpus_path_indexes_directory_without_stopping_on_file_failure(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    root = tmp_path / 'corpus'
    nested = root / 'nested'
    nested.mkdir(parents=True)
    (root / 'base.md').write_text(
        '# Base\n\n'
        'RabbitMQ foi adotado como message broker padrao.\n',
        encoding='utf-8',
    )
    (nested / 'detalhe.md').write_text(
        '# Detalhe\n\n'
        'O time SRE ficou responsavel pelo runbook.\n',
        encoding='utf-8',
    )
    (root / 'vazio.txt').write_text('   \n', encoding='utf-8')
    (root / 'planilha.xlsx').write_text('fora do escopo', encoding='utf-8')

    result = index_corpus_path(root, settings=settings, embedder=FakeEmbedder(), recursive=True)

    assert result.status == 'partial'
    assert result.total_found == 3
    assert result.indexed_count == 2
    assert result.failed_count == 1
    assert result.skipped_count == 1
    assert {item.note_id for item in result.results if item.status == 'success'} == {'base', 'detalhe'}
    failed = [item for item in result.results if item.status == 'failed']
    assert failed[0].error_code == 'EMPTY_CONTENT'


def test_index_corpus_path_non_recursive_skips_nested_files(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    root = tmp_path / 'corpus'
    nested = root / 'nested'
    nested.mkdir(parents=True)
    (root / 'base.md').write_text('# Base\n\nArquivo raiz.\n', encoding='utf-8')
    (nested / 'detalhe.md').write_text('# Detalhe\n\nArquivo aninhado.\n', encoding='utf-8')

    result = index_corpus_path(root, settings=settings, embedder=FakeEmbedder(), recursive=False)

    assert result.status == 'success'
    assert result.total_found == 1
    assert result.indexed_count == 1
    assert result.skipped_count == 1
    assert result.skipped[0].reason == 'directory_requires_recursive'
