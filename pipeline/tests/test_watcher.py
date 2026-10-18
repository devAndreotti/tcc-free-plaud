import time
from pathlib import Path

import pytest

from escolio.app.config import Settings
from escolio.corpus.dropped import DroppedFileEvent, DroppedFileIndexer
from escolio.corpus.service import index_corpus_path
from escolio.ingest.watcher import VaultWatcher, discover_files
from escolio.notes.service import delete_notes_by_source_path
from escolio.storage.sqlite import (
    count_chunks,
    count_fts_chunks,
    get_all_notes,
    init_sqlite,
    list_chunks,
)
from escolio.storage.vector import LocalVectorStore


class FakeEmbedder:
    model_name = 'fake-hash'

    def embed(self, texts: list[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for text in texts:
            vector = [0.0] * 16
            for token in text.lower().split():
                vector[sum(ord(char) for char in token) % 16] += 1.0
            vectors.append(vector)
        return vectors


def _settings(tmp_path: Path) -> Settings:
    return Settings(
        workspace_dir=tmp_path,
        data_dir=tmp_path / 'data',
        notes_dir=tmp_path / 'data' / 'corpus' / 'notes',
        datasets_dir=tmp_path / 'data' / 'datasets',
        results_dir=tmp_path / 'data' / 'results',
        sqlite_path=tmp_path / 'data' / 'results' / 'escolio.sqlite3',
        vector_store_dir=tmp_path / 'data' / 'results' / 'vector_store',
        vector_collection_name='watcher_test',
        embedding_model='fake-hash',
        default_chunk_size=120,
        default_chunk_overlap=20,
    )


_INDEXERS: list[DroppedFileIndexer] = []


@pytest.fixture(autouse=True)
def _drena_indexadores():
    # corpus_write_lock é global: trabalho que sobra na fila de um teste (eventos repetidos de
    # criar/editar) atrasaria o seguinte no runner lento do CI.
    yield
    while _INDEXERS:
        _INDEXERS.pop().join()


def _indexer(tmp_path: Path) -> tuple[DroppedFileIndexer, Settings, LocalVectorStore]:
    settings = _settings(tmp_path)
    store = LocalVectorStore(settings.vector_store_dir, collection_name=settings.vector_collection_name)
    indexer = DroppedFileIndexer(
        runner=lambda path: index_corpus_path(path, settings=settings, vector_store=store, embedder=FakeEmbedder()),
        remover=lambda path, folder: delete_notes_by_source_path(
            path, folder=folder, settings=settings, vector_store=store
        ),
    )
    _INDEXERS.append(indexer)
    return indexer, settings, store


def _wait_for(indexer: DroppedFileIndexer, seen: list[DroppedFileEvent], name: str, status: str, times: int = 1) -> None:
    deadline = time.monotonic() + 30  # teto; um teste verde sai assim que o evento chega
    while time.monotonic() < deadline:
        seen.extend(indexer.poll_events())
        if sum(1 for e in seen if e.name == name and e.status == status) >= times:
            return
        time.sleep(0.05)
    raise AssertionError(f'evento {status} de {name} nao chegou: {[(e.name, e.status) for e in seen]}')


def _db_notes(settings: Settings):
    connection = init_sqlite(settings.sqlite_path)
    try:
        return get_all_notes(connection)
    finally:
        connection.close()


def _db_chunk_texts(settings: Settings) -> list[str]:
    connection = init_sqlite(settings.sqlite_path)
    try:
        return [chunk.chunk_text for chunk in list_chunks(connection)]
    finally:
        connection.close()


def _make_root(tmp_path: Path) -> Path:
    root = tmp_path / 'vault'
    root.mkdir()
    return root


def test_discover_files_lists_only_files(tmp_path: Path) -> None:
    (tmp_path / "note.txt").write_text("conteudo", encoding="utf-8")
    (tmp_path / "subdir").mkdir()

    files = discover_files(tmp_path)

    assert [f.name for f in files] == ["note.txt"]


def test_discover_files_returns_empty_for_missing_directory(tmp_path: Path) -> None:
    missing = tmp_path / "missing"

    assert discover_files(missing) == []


def test_regressao_watcher_cria_md_e_grava_nota(tmp_path: Path) -> None:
    root = _make_root(tmp_path)
    indexer, settings, _store = _indexer(tmp_path)
    seen: list[DroppedFileEvent] = []

    with VaultWatcher(root, indexer=indexer, recursive=True, debounce_seconds=0.1):
        (root / 'nota.md').write_text('# Nota\n\nRabbitMQ e o broker da plataforma.\n', encoding='utf-8')
        _wait_for(indexer, seen, 'nota.md', 'indexed')

    assert [Path(note.source_path).name for note in _db_notes(settings)] == ['nota.md']


def test_regressao_watcher_edicao_torna_conteudo_novo_pesquisavel(tmp_path: Path) -> None:
    root = _make_root(tmp_path)
    indexer, settings, _store = _indexer(tmp_path)
    seen: list[DroppedFileEvent] = []

    with VaultWatcher(root, indexer=indexer, recursive=True, debounce_seconds=0.1):
        note = root / 'nota.md'
        note.write_text('# Nota\n\nRabbitMQ e o broker.\n', encoding='utf-8')
        _wait_for(indexer, seen, 'nota.md', 'indexed')
        note.write_text('# Nota\n\nKafka substituiu o broker.\n', encoding='utf-8')
        _wait_for(indexer, seen, 'nota.md', 'indexed', times=2)

    texts = ' '.join(_db_chunk_texts(settings))
    assert 'Kafka' in texts
    assert 'RabbitMQ' not in texts
    assert len(_db_notes(settings)) == 1


def test_regressao_watcher_apagar_arquivo_remove_nota_de_todas_as_tabelas(tmp_path: Path) -> None:
    root = _make_root(tmp_path)
    indexer, settings, store = _indexer(tmp_path)
    seen: list[DroppedFileEvent] = []

    with VaultWatcher(root, indexer=indexer, recursive=True, debounce_seconds=0.1):
        note = root / 'nota.md'
        note.write_text('# Nota\n\nRabbitMQ e o broker da plataforma.\n', encoding='utf-8')
        _wait_for(indexer, seen, 'nota.md', 'indexed')
        assert store.count() > 0
        note.unlink()
        _wait_for(indexer, seen, 'nota.md', 'removed')

    connection = init_sqlite(settings.sqlite_path)
    try:
        assert count_chunks(connection) == 0
        assert count_fts_chunks(connection) == 0
    finally:
        connection.close()
    assert _db_notes(settings) == []
    assert store.count() == 0


def test_regressao_watcher_renomear_troca_a_nota_antiga_pela_nova(tmp_path: Path) -> None:
    root = _make_root(tmp_path)
    indexer, settings, _store = _indexer(tmp_path)
    seen: list[DroppedFileEvent] = []

    with VaultWatcher(root, indexer=indexer, recursive=True, debounce_seconds=0.1):
        (root / 'antiga.md').write_text('# Nota\n\nConteudo renomeado.\n', encoding='utf-8')
        _wait_for(indexer, seen, 'antiga.md', 'indexed')
        (root / 'antiga.md').rename(root / 'nova.md')
        _wait_for(indexer, seen, 'antiga.md', 'removed')
        _wait_for(indexer, seen, 'nova.md', 'indexed')

    assert [Path(note.source_path).name for note in _db_notes(settings)] == ['nova.md']


def test_regressao_watcher_indexa_arquivo_em_subpasta(tmp_path: Path) -> None:
    root = _make_root(tmp_path)
    indexer, settings, _store = _indexer(tmp_path)
    seen: list[DroppedFileEvent] = []

    with VaultWatcher(root, indexer=indexer, recursive=True, debounce_seconds=0.1):
        (root / 'sub').mkdir()
        (root / 'sub' / 'profunda.md').write_text('# Profunda\n\nNota em subpasta.\n', encoding='utf-8')
        _wait_for(indexer, seen, 'profunda.md', 'indexed')

    notes = _db_notes(settings)
    assert [Path(note.source_path).parent.name for note in notes] == ['sub']


def test_regressao_watcher_ignora_extensao_nao_suportada_e_pastas_ignoradas(tmp_path: Path) -> None:
    root = _make_root(tmp_path)
    indexer, settings, _store = _indexer(tmp_path)
    seen: list[DroppedFileEvent] = []

    with VaultWatcher(root, indexer=indexer, recursive=True, debounce_seconds=0.1):
        (root / 'programa.exe').write_bytes(b'MZ')
        (root / '.git').mkdir()
        (root / '.git' / 'oculta.md').write_text('# Oculta\n\nNao deve entrar.\n', encoding='utf-8')
        time.sleep(0.6)
        seen.extend(indexer.poll_events())

    assert seen == []
    assert _db_notes(settings) == []


def test_vault_watcher_start_creates_directory(tmp_path: Path) -> None:
    target = tmp_path / "vault_novo"
    indexer, _settings_unused, _store = _indexer(tmp_path)
    watcher = VaultWatcher(target, indexer=indexer, recursive=False)

    try:
        watcher.start()
        assert target.exists()
    finally:
        watcher.stop()


def test_vault_watcher_start_is_idempotent(tmp_path: Path) -> None:
    indexer, _settings_unused, _store = _indexer(tmp_path)
    watcher = VaultWatcher(tmp_path, indexer=indexer, recursive=False)

    try:
        watcher.start()
        watcher.start()
    finally:
        watcher.stop()
