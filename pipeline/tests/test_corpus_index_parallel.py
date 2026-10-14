from pathlib import Path
from threading import current_thread

from escolio.app.config import Settings
from escolio.corpus import service
from escolio.corpus.service import index_corpus_path


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


def _settings(tmp_path: Path, *, workers: int, collection_name: str) -> Settings:
    return Settings(
        workspace_dir=tmp_path,
        data_dir=tmp_path / 'data',
        notes_dir=tmp_path / 'data' / 'corpus' / 'notes',
        datasets_dir=tmp_path / 'data' / 'datasets',
        results_dir=tmp_path / 'data' / 'results',
        sqlite_path=tmp_path / 'data' / 'results' / 'escolio.sqlite3',
        vector_store_dir=tmp_path / 'data' / 'results' / 'vector_store',
        vector_collection_name=collection_name,
        embedding_model='fake-hash',
        default_chunk_size=240,
        default_chunk_overlap=40,
        corpus_index_workers=workers,
    )


def _write_fixture(root: Path) -> None:
    root.mkdir()
    (root / 'a.md').write_text('# A\n\nRabbitMQ foi adotado.\n', encoding='utf-8')
    (root / 'b.md').write_text('# B\n\nO time SRE fez o runbook.\n', encoding='utf-8')
    (root / 'c.txt').write_text('Bronze Silver Gold organizam o pipeline.\n', encoding='utf-8')
    (root / 'd.md').write_text('   \n', encoding='utf-8')


def _summary(result):
    return [(Path(item.source_path).name, item.status, item.note_id, item.error_code) for item in result.results]


def test_parallel_workers_keep_deterministic_results(tmp_path: Path) -> None:
    serial_root = tmp_path / 'serial'
    parallel_root = tmp_path / 'parallel'
    _write_fixture(serial_root)
    _write_fixture(parallel_root)

    serial = index_corpus_path(
        serial_root,
        settings=_settings(tmp_path / 'serial-workspace', workers=1, collection_name='parallel_serial_test'),
        embedder=FakeEmbedder(),
        recursive=True,
    )
    parallel = index_corpus_path(
        parallel_root,
        settings=_settings(tmp_path / 'parallel-workspace', workers=4, collection_name='parallel_workers_test'),
        embedder=FakeEmbedder(),
        recursive=True,
    )

    assert parallel.status == 'partial'
    assert parallel.indexed_count == 3
    assert parallel.failed_count == 1
    assert _summary(parallel) == _summary(serial)


def test_parallel_workers_prepare_files_outside_main_thread(monkeypatch, tmp_path: Path) -> None:
    settings = _settings(tmp_path, workers=4, collection_name='parallel_thread_test')
    root = tmp_path / 'corpus'
    _write_fixture(root)
    original_load_document = service.load_document
    thread_names: set[str] = set()

    def tracked_load_document(path):
        thread_names.add(current_thread().name)
        return original_load_document(path)

    monkeypatch.setattr(service, 'load_document', tracked_load_document)

    result = index_corpus_path(root, settings=settings, embedder=FakeEmbedder(), recursive=True)

    assert result.status == 'partial'
    assert any(name != 'MainThread' for name in thread_names)
