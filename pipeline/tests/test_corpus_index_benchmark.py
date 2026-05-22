import json
from pathlib import Path

from typer.testing import CliRunner

from free_plaud.app.config import Settings
from free_plaud.cli import app
from free_plaud.corpus.service import benchmark_corpus_indexing

runner = CliRunner()


class FakeEmbedder:
    model_name = 'fake-hash'

    def __init__(self) -> None:
        self.calls = 0

    def embed(self, texts: list[str]) -> list[list[float]]:
        self.calls += 1
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
        sqlite_path=tmp_path / 'data' / 'results' / 'free_plaud.sqlite3',
        vector_store_dir=tmp_path / 'data' / 'results' / 'vector_store',
        vector_collection_name='corpus_index_benchmark_test',
        embedding_model='fake-hash',
        default_chunk_size=120,
        default_chunk_overlap=20,
    )


def test_benchmark_corpus_indexing_measures_repeat_and_unchanged(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    embedder = FakeEmbedder()

    result = benchmark_corpus_indexing(
        files=6,
        repeat=2,
        settings=settings,
        embedder=embedder,
    )

    assert result.status == 'success'
    assert result.files_requested == 6
    assert result.supported_files == 6
    assert result.ignored_files == 3
    assert result.repeat == 2
    assert result.runs[0].indexed_count == 6
    assert result.runs[0].unchanged_count == 0
    assert result.runs[0].embedding_calls > 0
    assert result.runs[1].indexed_count == 0
    assert result.runs[1].unchanged_count == 6
    assert result.runs[1].embedding_calls == 0
    assert result.embedding_calls == embedder.calls
    assert result.chunks_indexed >= 6
    assert result.files_per_second > 0


def test_corpus_index_benchmark_cli_outputs_json(monkeypatch, tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    monkeypatch.setattr('free_plaud.corpus.cli.get_settings', lambda: settings)
    monkeypatch.setattr('free_plaud.corpus.service.get_embedder', lambda model_name: FakeEmbedder())

    result = runner.invoke(app, ['corpus', 'index-benchmark', '--files', '4', '--repeat', '2'])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload['status'] == 'success'
    assert payload['files_requested'] == 4
    assert payload['supported_files'] == 4
    assert payload['ignored_files'] == 3
    assert payload['runs'][0]['indexed_count'] == 4
    assert payload['runs'][1]['unchanged_count'] == 4
