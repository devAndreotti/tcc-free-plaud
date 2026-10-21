from pathlib import Path

import pytest

from escolio.app.config import Settings
from escolio.corpus.cancellation import CancellationToken
from escolio.corpus.service import (
    get_corpus_status,
    index_corpus_file,
    index_corpus_path,
)
from escolio.ingest.loaders import load_document
from escolio.notes.metadata import build_note_id
from escolio.storage.sqlite import (
    connect_sqlite,
    count_notes,
    get_all_notes,
    init_sqlite,
    list_chunk_ids,
)
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


class BrokenEmbedder(FakeEmbedder):
    model_name = 'broken'

    def embed(self, texts: list[str]) -> list[list[float]]:
        return super().embed(texts[:-1])


class CountingEmbedder(FakeEmbedder):
    def __init__(self) -> None:
        self.calls = 0

    def embed(self, texts: list[str]) -> list[list[float]]:
        self.calls += 1
        return super().embed(texts)


def _settings(tmp_path: Path) -> Settings:
    return Settings(
        workspace_dir=tmp_path,
        data_dir=tmp_path / 'data',
        notes_dir=tmp_path / 'data' / 'corpus' / 'notes',
        datasets_dir=tmp_path / 'data' / 'datasets',
        results_dir=tmp_path / 'data' / 'results',
        sqlite_path=tmp_path / 'data' / 'results' / 'escolio.sqlite3',
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
    assert result.note_id == build_note_id(source, hash_unrooted=True)
    assert result.chunks_indexed >= 1
    assert result.embedding_model == 'fake-hash'
    assert result.vector_collection_name == 'corpus_service_test'
    assert result.vector_entries_count == result.chunks_indexed

    connection = connect_sqlite(settings.sqlite_path)
    note_row = connection.execute('SELECT note_id, source_path FROM notes WHERE note_id = ?', (result.note_id,)).fetchone()
    chunk_rows = connection.execute('SELECT chunk_id FROM chunks WHERE note_id = ?', (result.note_id,)).fetchall()

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

    second_embedder = CountingEmbedder()

    first = index_corpus_file(source, settings=settings, embedder=FakeEmbedder())
    second = index_corpus_file(source, settings=settings, embedder=second_embedder)

    connection = connect_sqlite(settings.sqlite_path)
    note_count = connection.execute('SELECT COUNT(*) AS total FROM notes WHERE note_id = ?', (first.note_id,)).fetchone()
    chunk_count = connection.execute('SELECT COUNT(*) AS total FROM chunks WHERE note_id = ?', (first.note_id,)).fetchone()

    assert first.status == 'success'
    assert second.status == 'unchanged'
    assert second.chunks_indexed == first.chunks_indexed
    assert second.vector_entries_count == first.vector_entries_count
    assert second_embedder.calls == 0
    assert note_count['total'] == 1
    assert chunk_count['total'] == first.chunks_indexed


def test_index_corpus_file_reindexes_same_hash_when_vectors_are_missing(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    source = tmp_path / 'reparavel.md'
    source.write_text('# Reparavel\n\nTexto que deve ser reindexado se vetor sumir.\n', encoding='utf-8')
    connection = init_sqlite(settings.sqlite_path)
    vector_store = LocalVectorStore(settings.vector_store_dir, collection_name=settings.vector_collection_name)

    first = index_corpus_file(
        source,
        settings=settings,
        connection=connection,
        vector_store=vector_store,
        embedder=FakeEmbedder(),
    )
    vector_store.reset()
    second_embedder = CountingEmbedder()
    second = index_corpus_file(
        source,
        settings=settings,
        connection=connection,
        vector_store=vector_store,
        embedder=second_embedder,
    )

    assert first.status == 'success'
    assert second.status == 'success'
    assert second_embedder.calls == 1


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


def test_index_corpus_path_uses_distinct_note_ids_for_same_stem_files(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    root = tmp_path / 'vault'
    nested = root / 'AI'
    nested.mkdir(parents=True)
    (nested / 'AI.md').write_text('# AI\n\nNota sobre modelos generativos.\n', encoding='utf-8')
    (nested / '🤖 AI.md').write_text('# AI\n\nNota sobre agentes locais.\n', encoding='utf-8')
    connection = init_sqlite(settings.sqlite_path)
    vector_store = LocalVectorStore(settings.vector_store_dir, collection_name=settings.vector_collection_name)

    result = index_corpus_path(
        root,
        settings=settings,
        connection=connection,
        vector_store=vector_store,
        embedder=FakeEmbedder(),
        recursive=True,
        commit_mode='atomic',
    )
    status = get_corpus_status(settings=settings, connection=connection, vector_store=vector_store)
    success_ids = [item.note_id for item in result.results if item.status == 'success']

    assert result.status == 'success'
    assert result.indexed_count == 2
    assert len(success_ids) == 2
    assert len(set(success_ids)) == 2
    assert all(note_id and note_id.startswith('ai--') for note_id in success_ids)
    assert count_notes(connection) == 2
    assert status.status == 'clean'
    assert status.stale_vector_chunks_count == 0


def test_index_corpus_path_fails_batch_when_note_id_duplicates_remain(monkeypatch, tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    root = tmp_path / 'corpus'
    root.mkdir()
    (root / 'a.md').write_text('# A\n\nPrimeira nota.\n', encoding='utf-8')
    (root / 'b.md').write_text('# B\n\nSegunda nota.\n', encoding='utf-8')
    connection = init_sqlite(settings.sqlite_path)
    vector_store = LocalVectorStore(settings.vector_store_dir, collection_name=settings.vector_collection_name)
    monkeypatch.setattr('escolio.notes.structurer.build_note_id', lambda path, **kwargs: 'duplicado')

    result = index_corpus_path(
        root,
        settings=settings,
        connection=connection,
        vector_store=vector_store,
        embedder=FakeEmbedder(),
        recursive=True,
        commit_mode='atomic',
    )

    assert result.status == 'failed'
    assert result.indexed_count == 0
    assert result.failed_count == 2
    assert {item.error_code for item in result.results} == {'DUPLICATE_NOTE_ID'}
    assert count_notes(connection) == 0
    assert vector_store.count() == 0


def test_index_corpus_path_replaces_legacy_file_note_id_for_same_source_path(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    root = tmp_path / 'corpus'
    root.mkdir()
    source = root / 'migravel.md'
    source.write_text('# Migravel\n\nNota que muda de ID quando passa a ser indexada por pasta.\n', encoding='utf-8')
    connection = init_sqlite(settings.sqlite_path)
    vector_store = LocalVectorStore(settings.vector_store_dir, collection_name=settings.vector_collection_name)

    legacy = index_corpus_file(
        source,
        settings=settings,
        connection=connection,
        vector_store=vector_store,
        embedder=FakeEmbedder(),
    )
    migrated = index_corpus_path(
        root,
        settings=settings,
        connection=connection,
        vector_store=vector_store,
        embedder=FakeEmbedder(),
        recursive=True,
        commit_mode='atomic',
    )
    new_note_id = build_note_id(source, root_path=root)
    status = get_corpus_status(settings=settings, connection=connection, vector_store=vector_store)
    note_ids = [
        row['note_id']
        for row in connection.execute('SELECT note_id FROM notes ORDER BY note_id').fetchall()
    ]

    assert legacy.status == 'success'
    assert legacy.note_id == build_note_id(source, hash_unrooted=True)
    assert migrated.status == 'success'
    assert migrated.results[0].note_id == new_note_id
    assert note_ids == [new_note_id]
    assert count_notes(connection) == 1
    assert status.status == 'clean'
    assert status.stale_vector_chunks_count == 0


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


def test_index_corpus_file_reports_os_error_as_failed(tmp_path: Path, monkeypatch) -> None:
    settings = _settings(tmp_path)
    source = tmp_path / 'trancado.md'
    source.write_text('# Trancado\n\nConteudo.\n', encoding='utf-8')

    def denied(path):
        raise PermissionError('Acesso negado')

    monkeypatch.setattr('escolio.corpus.service.load_document', denied)

    result = index_corpus_file(source, settings=settings, embedder=FakeEmbedder())

    assert result.status == 'failed'
    assert result.error_code == 'PermissionError'
    assert result.note_id is None


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
    assert {item.note_id for item in result.results if item.status == 'success'} == {
        build_note_id(root / 'base.md', root_path=root),
        build_note_id(nested / 'detalhe.md', root_path=root),
    }
    failed = [item for item in result.results if item.status == 'failed']
    assert failed[0].error_code == 'EMPTY_CONTENT'


@pytest.mark.parametrize('workers', [1, 2])
def test_index_corpus_path_keeps_indexing_when_one_file_is_unreadable(monkeypatch, tmp_path: Path, workers: int) -> None:
    settings = _settings(tmp_path).model_copy(update={'corpus_index_workers': workers})
    root = tmp_path / 'corpus'
    root.mkdir()
    (root / 'a.md').write_text('# A\n\nRabbitMQ foi adotado como message broker padrao.\n', encoding='utf-8')
    (root / 'b.md').write_text('# B\n\nO time SRE ficou responsavel pelo runbook.\n', encoding='utf-8')
    (root / 'bloqueado.md').write_text('# Bloqueado\n\nConteudo que outro programa mantem aberto.\n', encoding='utf-8')

    def load_document_locking_one_file(path: Path):
        if path.name == 'bloqueado.md':
            raise PermissionError(13, 'Permission denied', str(path))
        return load_document(path)

    monkeypatch.setattr('escolio.corpus.service.load_document', load_document_locking_one_file)

    result = index_corpus_path(root, settings=settings, embedder=FakeEmbedder(), recursive=True)

    assert result.status == 'partial'
    assert result.indexed_count == 2
    assert result.failed_count == 1
    failed = [item for item in result.results if item.status == 'failed']
    assert Path(failed[0].source_path).name == 'bloqueado.md'
    assert failed[0].error_code == 'PermissionError'


def test_regressao_index_corpus_file_rejects_markdown_with_only_frontmatter(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    source = tmp_path / 'so-frontmatter.md'
    source.write_text('---\ntitle: x\n---\n', encoding='utf-8')

    result = index_corpus_file(source, settings=settings, embedder=FakeEmbedder())

    assert result.status == 'failed'
    assert result.error_code == 'EMPTY_CONTENT'
    assert result.note_id is None
    assert result.chunks_indexed == 0


def test_regressao_index_corpus_path_rejects_frontmatter_only_note_and_indexes_others(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    root = tmp_path / 'corpus'
    root.mkdir()
    (root / 'base.md').write_text('# Base\n\nRabbitMQ foi adotado como broker.\n', encoding='utf-8')
    (root / 'so-frontmatter.md').write_text('---\ntitle: x\n---\n', encoding='utf-8')
    (root / 'com-corpo.md').write_text('---\ntitle: y\n---\n\nO time SRE ficou com o runbook.\n', encoding='utf-8')

    result = index_corpus_path(root, settings=settings, embedder=FakeEmbedder(), recursive=True)

    assert result.status == 'partial'
    assert result.indexed_count == 2
    assert result.failed_count == 1
    failed = [item for item in result.results if item.status == 'failed']
    assert failed[0].error_code == 'EMPTY_CONTENT'


def test_index_corpus_path_emits_progress_events_for_directory(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    root = tmp_path / 'corpus'
    nested = root / 'nested'
    nested.mkdir(parents=True)
    (root / 'base.md').write_text('# Base\n\nArquivo raiz.\n', encoding='utf-8')
    (nested / 'detalhe.md').write_text('# Detalhe\n\nArquivo aninhado.\n', encoding='utf-8')
    (root / 'image.png').write_text('fora do escopo', encoding='utf-8')
    events = []

    result = index_corpus_path(
        root,
        settings=settings,
        embedder=FakeEmbedder(),
        recursive=True,
        progress=events.append,
    )

    assert result.status == 'success'
    assert next(event.phase for event in events) == 'discovering'
    assert 'loading' in {event.phase for event in events}
    assert 'embedding' in {event.phase for event in events}
    assert events[-1].phase == 'finished'
    assert events[-1].total_found == 2
    assert events[-1].processed_count == 2
    assert events[-1].indexed_count == 2
    assert events[-1].failed_count == 0
    assert events[-1].skipped_count == 1


def test_index_corpus_path_honors_cancel_token_before_processing(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    source = tmp_path / 'cancelavel.md'
    source.write_text('# Cancelavel\n\nTexto.', encoding='utf-8')
    token = CancellationToken()
    token.cancel()

    result = index_corpus_path(source, settings=settings, embedder=FakeEmbedder(), cancel_token=token)

    assert result.status == 'cancelled'
    assert result.total_found == 1
    assert result.indexed_count == 0
    assert result.failed_count == 0


def test_index_corpus_path_stops_between_files_when_cancelled(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    root = tmp_path / 'corpus'
    root.mkdir()
    (root / 'a.md').write_text('# A\n\nPrimeiro arquivo.', encoding='utf-8')
    (root / 'b.md').write_text('# B\n\nSegundo arquivo.', encoding='utf-8')
    token = CancellationToken()

    def cancel_after_first(progress) -> None:
        if progress.phase == 'loading' and progress.processed_count == 1:
            token.cancel()

    result = index_corpus_path(
        root,
        settings=settings,
        embedder=FakeEmbedder(),
        recursive=True,
        progress=cancel_after_first,
        cancel_token=token,
    )

    assert result.status == 'cancelled'
    assert result.total_found == 2
    assert result.indexed_count == 0
    assert len(result.results) == 0


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


def test_regressao_arquivos_unicos_com_mesmo_nome_nao_se_sobrescrevem(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    first_dir = tmp_path / 'a'
    second_dir = tmp_path / 'b'
    first_dir.mkdir()
    second_dir.mkdir()
    first = first_dir / 'notas.md'
    second = second_dir / 'notas.md'
    first.write_text('# Notas\n\nFerias de julho da equipe financeira.\n', encoding='utf-8')
    second.write_text('# Notas\n\nMigracao do cluster de banco de dados.\n', encoding='utf-8')
    connection = init_sqlite(settings.sqlite_path)
    vector_store = LocalVectorStore(settings.vector_store_dir, collection_name=settings.vector_collection_name)

    first_result = index_corpus_file(first, settings=settings, connection=connection, vector_store=vector_store, embedder=FakeEmbedder())
    second_result = index_corpus_file(second, settings=settings, connection=connection, vector_store=vector_store, embedder=FakeEmbedder())

    assert first_result.status == 'success'
    assert second_result.status == 'success'
    assert first_result.note_id != second_result.note_id
    assert count_notes(connection) == 2
    found_note_ids = {
        hit.chunk.note_id
        for text in ('Ferias de julho', 'Migracao do cluster')
        for hit in vector_store.query(FakeEmbedder().embed([text])[0], top_k=5)
    }
    assert found_note_ids == {first_result.note_id, second_result.note_id}


def test_regressao_nota_com_id_so_slug_e_substituida_sem_duplicata(monkeypatch, tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    root = tmp_path / 'corpus'
    root.mkdir()
    source = root / 'legada.md'
    source.write_text('# Legada\n\nNota gravada com o id antigo, so pelo slug.\n', encoding='utf-8')
    connection = init_sqlite(settings.sqlite_path)
    vector_store = LocalVectorStore(settings.vector_store_dir, collection_name=settings.vector_collection_name)
    monkeypatch.setattr('escolio.notes.structurer.build_note_id', lambda path, **kwargs: 'legada')
    legacy = index_corpus_file(source, settings=settings, connection=connection, vector_store=vector_store, embedder=FakeEmbedder())
    monkeypatch.undo()

    current = index_corpus_file(source, settings=settings, connection=connection, vector_store=vector_store, embedder=FakeEmbedder())
    note_ids = [row['note_id'] for row in connection.execute('SELECT note_id FROM notes').fetchall()]

    assert legacy.note_id == 'legada'
    assert current.status == 'success'
    assert note_ids == [current.note_id]
    assert count_notes(connection) == 1
    assert vector_store.count() == current.chunks_indexed


def _notes_by_name(settings: Settings) -> list[str]:
    connection = init_sqlite(settings.sqlite_path)
    try:
        return sorted(Path(note.source_path).name for note in get_all_notes(connection))
    finally:
        connection.close()


def test_regressao_indexacao_de_pasta_remove_nota_de_arquivo_apagado(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    root = tmp_path / 'vault'
    root.mkdir()
    (root / 'a.md').write_text('# A\n\nPrimeiro conteudo do corpus.\n', encoding='utf-8')
    (root / 'b.md').write_text('# B\n\nSegundo conteudo do corpus.\n', encoding='utf-8')
    index_corpus_path(root, settings=settings, embedder=FakeEmbedder(), recursive=True)
    assert _notes_by_name(settings) == ['a.md', 'b.md']

    (root / 'a.md').unlink()
    result = index_corpus_path(root, settings=settings, embedder=FakeEmbedder(), recursive=True)

    assert _notes_by_name(settings) == ['b.md']
    assert result.removed_count == 1


def test_regressao_arquivo_de_pasta_indexada_mantem_note_id_ao_ser_indexado_sozinho(tmp_path: Path) -> None:
    # Watcher e área de soltar indexam um arquivo por vez; o id tem de ser o mesmo da Fila.
    settings = _settings(tmp_path)
    root = tmp_path / 'vault'
    (root / 'sub').mkdir(parents=True)
    source = root / 'sub' / 'nota.md'
    source.write_text('# Nota\n\nTexto original da vault.\n', encoding='utf-8')
    folder_id = index_corpus_path(root, settings=settings, embedder=FakeEmbedder(), recursive=True).results[0].note_id

    source.write_text('# Nota\n\nTexto editado no Obsidian.\n', encoding='utf-8')
    single = index_corpus_file(source, settings=settings, embedder=FakeEmbedder())

    assert single.status == 'success'
    assert single.note_id == folder_id == build_note_id(source, root_path=root)
    connection = connect_sqlite(settings.sqlite_path)
    try:
        assert count_notes(connection) == 1
    finally:
        connection.close()


def test_regressao_indexacao_de_pasta_nao_mexe_em_notas_fora_da_raiz(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    outside = tmp_path / 'outra-pasta'
    outside.mkdir()
    (outside / 'fora.md').write_text('# Fora\n\nNota de outra raiz.\n', encoding='utf-8')
    index_corpus_path(outside, settings=settings, embedder=FakeEmbedder(), recursive=True)
    (outside / 'fora.md').unlink()

    root = tmp_path / 'vault'
    root.mkdir()
    (root / 'dentro.md').write_text('# Dentro\n\nNota da raiz indexada.\n', encoding='utf-8')
    result = index_corpus_path(root, settings=settings, embedder=FakeEmbedder(), recursive=True)

    assert _notes_by_name(settings) == ['dentro.md', 'fora.md']
    assert result.removed_count == 0


def test_regressao_indexacao_nao_recursiva_so_remove_filhos_diretos(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    root = tmp_path / 'vault'
    (root / 'sub').mkdir(parents=True)
    (root / 'a.md').write_text('# A\n\nFilho direto da raiz.\n', encoding='utf-8')
    (root / 'sub' / 's.md').write_text('# S\n\nNeto da raiz.\n', encoding='utf-8')
    index_corpus_path(root, settings=settings, embedder=FakeEmbedder(), recursive=True)

    (root / 'a.md').unlink()
    (root / 'sub' / 's.md').unlink()
    result = index_corpus_path(root, settings=settings, embedder=FakeEmbedder(), recursive=False)

    assert _notes_by_name(settings) == ['s.md']
    assert result.removed_count == 1


def test_regressao_reindexa_nota_com_titulo_salvo_errado_mesmo_com_conteudo_igual(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    source = tmp_path / 'Trilha Cisco.md'
    source.write_text(
        '---\ntype: index\ntags:\n  - tema/cisco\n---\n\nTrilha de cursos Cisco para o time de rede.\n',
        encoding='utf-8',
    )
    first = index_corpus_file(source, settings=settings, embedder=FakeEmbedder())
    connection = connect_sqlite(settings.sqlite_path)
    connection.execute('UPDATE notes SET title = ? WHERE note_id = ?', ('tags:', first.note_id))
    connection.commit()

    second_embedder = CountingEmbedder()
    second = index_corpus_file(source, settings=settings, embedder=second_embedder)
    third = index_corpus_file(source, settings=settings, embedder=CountingEmbedder())

    title = connection.execute('SELECT title FROM notes WHERE note_id = ?', (first.note_id,)).fetchone()['title']
    assert first.status == 'success'
    assert second.status == 'success'
    assert second_embedder.calls == 1
    assert title == 'Trilha Cisco'
    assert third.status == 'unchanged'
