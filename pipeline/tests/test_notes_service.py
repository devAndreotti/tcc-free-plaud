from pathlib import Path

from escolio.app.config import Settings
from escolio.corpus.service import index_corpus_file
from escolio.notes.service import (
    delete_note,
    get_note_detail,
    list_notes,
    reindex_note,
)
from escolio.storage.sqlite import connect_sqlite, count_chunks, count_notes
from escolio.storage.vector import LocalVectorStore


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


def _settings(tmp_path: Path) -> Settings:
    return Settings(
        workspace_dir=tmp_path,
        data_dir=tmp_path / 'data',
        notes_dir=tmp_path / 'data' / 'corpus' / 'notes',
        datasets_dir=tmp_path / 'data' / 'datasets',
        results_dir=tmp_path / 'data' / 'results',
        sqlite_path=tmp_path / 'data' / 'results' / 'escolio.sqlite3',
        vector_store_dir=tmp_path / 'data' / 'results' / 'vector_store',
        vector_collection_name='notes_service_test',
        embedding_model='fake-hash',
        default_chunk_size=120,
        default_chunk_overlap=20,
    )


def _index_fixture(settings: Settings, source: Path, text: str) -> str:
    source.write_text(text, encoding='utf-8')
    result = index_corpus_file(source, settings=settings, embedder=FakeEmbedder())
    assert result.status == 'success'
    assert result.note_id is not None
    return result.note_id


def test_list_notes_returns_operational_summary(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    note_id = _index_fixture(
        settings,
        tmp_path / 'plataforma.md',
        '# Plataforma\n\nA plataforma usa RabbitMQ e SQLite no pipeline local-first.\n',
    )

    connection = connect_sqlite(settings.sqlite_path)
    summaries = list_notes(settings=settings, connection=connection)

    assert len(summaries) == 1
    assert summaries[0].note_id == note_id
    assert summaries[0].title == 'Plataforma'
    assert summaries[0].source_type == 'md'
    assert summaries[0].source_path.endswith('plataforma.md')
    assert summaries[0].chunk_count >= 1


def test_get_note_detail_returns_markdown_and_chunks(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    note_id = _index_fixture(
        settings,
        tmp_path / 'operacao.md',
        '# Operacao\n\nO runbook SRE documenta rollback, fila e alarme de latencia.\n',
    )

    connection = connect_sqlite(settings.sqlite_path)
    detail = get_note_detail(note_id, settings=settings, connection=connection)

    assert detail.note_id == note_id
    assert '# Operacao' in detail.structured_markdown
    assert detail.chunks
    assert detail.chunks[0].chunk_id.startswith(f'{note_id}::v1::')
    assert detail.chunks[0].snippet


def test_delete_note_removes_sqlite_and_chroma_records(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    note_id = _index_fixture(
        settings,
        tmp_path / 'remover.md',
        '# Remover\n\nEsta nota deve sair do SQLite, FTS e Chroma.\n',
    )
    connection = connect_sqlite(settings.sqlite_path)
    vector_store = LocalVectorStore(settings.vector_store_dir, collection_name=settings.vector_collection_name)

    assert count_notes(connection) == 1
    assert count_chunks(connection) >= 1
    assert vector_store.count() >= 1

    result = delete_note(note_id, settings=settings, connection=connection, vector_store=vector_store)

    assert result.ok is True
    assert result.note_id == note_id
    assert result.deleted_vectors >= 1
    assert count_notes(connection) == 0
    assert count_chunks(connection) == 0
    assert vector_store.count() == 0


def test_reindex_note_uses_existing_source_path(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    source = tmp_path / 'reindexavel.md'
    note_id = _index_fixture(settings, source, '# Reindexavel\n\nTexto antigo sobre fila.\n')
    source.write_text(
        '# Reindexavel\n\nTexto novo sobre benchmark, CUDA e cache lexical.\n',
        encoding='utf-8',
    )
    connection = connect_sqlite(settings.sqlite_path)
    vector_store = LocalVectorStore(settings.vector_store_dir, collection_name=settings.vector_collection_name)

    result = reindex_note(
        note_id,
        settings=settings,
        connection=connection,
        vector_store=vector_store,
        embedder=FakeEmbedder(),
    )

    assert result.ok is True
    assert result.note_id == note_id
    assert result.status == 'success'
    assert result.chunks_indexed >= 1
    detail = get_note_detail(note_id, settings=settings, connection=connection)
    assert 'Texto novo sobre benchmark' in detail.structured_markdown


def test_reindex_note_keeps_note_id_from_folder_index(tmp_path: Path) -> None:
    from escolio.corpus.service import index_corpus_path

    settings = _settings(tmp_path)
    vault = tmp_path / 'vault'
    (vault / 'estudos').mkdir(parents=True)
    source = vault / 'estudos' / 'nota.md'
    source.write_text('# Nota\n\nTexto sobre filas e chunks.\n', encoding='utf-8')
    vector_store = LocalVectorStore(settings.vector_store_dir, collection_name=settings.vector_collection_name)
    batch = index_corpus_path(vault, settings=settings, vector_store=vector_store, embedder=FakeEmbedder(), recursive=True)
    note_id = batch.results[0].note_id
    assert note_id and '--' in note_id  # id de pasta: slug + hash do caminho relativo

    connection = connect_sqlite(settings.sqlite_path)
    result = reindex_note(note_id, settings=settings, connection=connection, vector_store=vector_store, embedder=FakeEmbedder())

    assert result.note_id == note_id
    assert result.status == 'unchanged'  # mesmo id + mesmo conteúdo: nada a refazer
    assert count_notes(connection) == 1


def test_regressao_reindex_note_separa_arquivos_unicos_com_mesmo_nome(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    first_dir = tmp_path / 'a'
    second_dir = tmp_path / 'b'
    first_dir.mkdir()
    second_dir.mkdir()
    first_id = _index_fixture(settings, first_dir / 'notas.md', '# Notas\n\nTexto antigo da pasta a.\n')
    second_id = _index_fixture(settings, second_dir / 'notas.md', '# Notas\n\nTexto da pasta b.\n')
    (second_dir / 'notas.md').write_text('# Notas\n\nTexto novo da pasta b editado.\n', encoding='utf-8')
    connection = connect_sqlite(settings.sqlite_path)
    vector_store = LocalVectorStore(settings.vector_store_dir, collection_name=settings.vector_collection_name)

    result = reindex_note(second_id, settings=settings, connection=connection, vector_store=vector_store, embedder=FakeEmbedder())

    assert first_id != second_id
    assert count_notes(connection) == 2
    assert result.ok is True
    assert result.status == 'success'
    assert 'Texto novo da pasta b' in get_note_detail(second_id, settings=settings, connection=connection).structured_markdown


def test_regressao_reindex_note_aceita_id_antigo_so_slug(monkeypatch, tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    source = tmp_path / 'antiga.md'
    monkeypatch.setattr('escolio.notes.structurer.build_note_id', lambda path, **kwargs: 'antiga')
    legacy_id = _index_fixture(settings, source, '# Antiga\n\nTexto antigo da nota legada.\n')
    monkeypatch.undo()
    source.write_text('# Antiga\n\nTexto novo da nota legada.\n', encoding='utf-8')
    connection = connect_sqlite(settings.sqlite_path)
    vector_store = LocalVectorStore(settings.vector_store_dir, collection_name=settings.vector_collection_name)

    result = reindex_note(legacy_id, settings=settings, connection=connection, vector_store=vector_store, embedder=FakeEmbedder())

    assert legacy_id == 'antiga'
    assert result.ok is True
    assert result.status == 'success'
    assert result.note_id.startswith('antiga--')
    assert count_notes(connection) == 1
