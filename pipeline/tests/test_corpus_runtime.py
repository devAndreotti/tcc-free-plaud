from pathlib import Path

from escolio.app.config import Settings
from escolio.corpus.runtime import CorpusRuntime


class FakeEmbedder:
    model_name = 'fake-runtime'

    def __init__(self) -> None:
        self.calls = 0

    def embed(self, texts: list[str]) -> list[list[float]]:
        self.calls += 1
        return [[float(len(text))] + [0.0] * 15 for text in texts]


def _settings(tmp_path: Path) -> Settings:
    return Settings(
        workspace_dir=tmp_path,
        data_dir=tmp_path / 'data',
        notes_dir=tmp_path / 'data' / 'corpus' / 'notes',
        datasets_dir=tmp_path / 'data' / 'datasets',
        results_dir=tmp_path / 'data' / 'results',
        sqlite_path=tmp_path / 'data' / 'results' / 'escolio.sqlite3',
        vector_store_dir=tmp_path / 'data' / 'results' / 'vector_store',
        vector_collection_name='runtime_test',
        embedding_model='sentence-transformer:fake-runtime',
        embedding_device='cpu',
    )


def test_corpus_runtime_reuses_embedder_and_warms_once(monkeypatch, tmp_path: Path) -> None:
    created: list[FakeEmbedder] = []

    def fake_get_embedder(model_name: str, *, device: str):
        assert model_name == 'sentence-transformer:fake-runtime'
        assert device == 'cpu'
        embedder = FakeEmbedder()
        created.append(embedder)
        return embedder

    monkeypatch.setattr('escolio.corpus.runtime.get_embedder', fake_get_embedder)
    runtime = CorpusRuntime(_settings(tmp_path))

    first = runtime.warmup_embedder()
    second = runtime.warmup_embedder()

    assert len(created) == 1
    assert first.already_warm is False
    assert second.already_warm is True
    assert created[0].calls == 1
    assert runtime.get_embedder() is created[0]


def test_corpus_runtime_reuses_vector_store(tmp_path: Path) -> None:
    runtime = CorpusRuntime(_settings(tmp_path))

    first = runtime.get_vector_store()
    second = runtime.get_vector_store()
    runtime.clear_vector_store()
    third = runtime.get_vector_store()

    assert first is second
    assert third is not first
