import json
from pathlib import Path

from typer.testing import CliRunner

from free_plaud.app.config import Settings
from free_plaud.cli import app

runner = CliRunner()


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
        sqlite_path=tmp_path / 'data' / 'results' / 'free_plaud.sqlite3',
        vector_store_dir=tmp_path / 'data' / 'results' / 'vector_store',
        vector_collection_name='corpus_cli_test',
        embedding_model='fake-hash',
        default_chunk_size=120,
        default_chunk_overlap=20,
    )


def test_root_help_works() -> None:
    result = runner.invoke(app, ['--help'])
    assert result.exit_code == 0
    assert 'ingest' in result.stdout
    assert 'benchmark' in result.stdout
    assert 'corpus' in result.stdout


def test_doctor_creates_runtime_directories(monkeypatch, tmp_path: Path) -> None:
    settings = Settings(
        workspace_dir=tmp_path,
        data_dir=tmp_path / 'data',
        notes_dir=tmp_path / 'data' / 'corpus' / 'notes',
        datasets_dir=tmp_path / 'data' / 'datasets',
        results_dir=tmp_path / 'data' / 'results',
        sqlite_path=tmp_path / 'data' / 'results' / 'free_plaud.sqlite3',
        vector_store_dir=tmp_path / 'data' / 'results' / 'vector_store',
    )

    monkeypatch.setattr('free_plaud.cli.get_settings', lambda: settings)

    result = runner.invoke(app, ['doctor'])

    assert result.exit_code == 0
    assert settings.data_dir.exists()
    assert settings.notes_dir.exists()
    assert settings.datasets_dir.exists()
    assert settings.results_dir.exists()
    assert settings.vector_store_dir.exists()


def test_corpus_index_cli_persists_file(monkeypatch, tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    source = tmp_path / 'documento com espaco.md'
    source.write_text(
        '# Documento\n\n'
        'O corpus local deve indexar arquivos com path contendo espaco.\n',
        encoding='utf-8',
    )
    monkeypatch.setattr('free_plaud.corpus.cli.get_settings', lambda: settings)
    monkeypatch.setattr('free_plaud.corpus.service.get_embedder', lambda model_name: FakeEmbedder())

    result = runner.invoke(app, ['corpus', 'index', *str(source).split(' ')])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload['status'] == 'success'
    assert payload['note_id'] == 'documento-com-espaco'
    assert payload['chunks_indexed'] >= 1
    assert payload['embedding_model'] == 'fake-hash'


def test_corpus_index_cli_returns_non_zero_for_invalid_file(monkeypatch, tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    source = tmp_path / 'planilha.xlsx'
    source.write_text('conteudo', encoding='utf-8')
    monkeypatch.setattr('free_plaud.corpus.cli.get_settings', lambda: settings)
    monkeypatch.setattr('free_plaud.corpus.service.get_embedder', lambda model_name: FakeEmbedder())

    result = runner.invoke(app, ['corpus', 'index', str(source)])

    assert result.exit_code == 1
    payload = json.loads(result.stdout)
    assert payload['status'] == 'failed'
    assert payload['error_code'] == 'UNSUPPORTED_MEDIA_TYPE'


def test_corpus_index_cli_accepts_recursive_directory(monkeypatch, tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    root = tmp_path / 'corpus'
    nested = root / 'nested'
    nested.mkdir(parents=True)
    (root / 'base.md').write_text('# Base\n\nArquivo raiz.\n', encoding='utf-8')
    (nested / 'detalhe.md').write_text('# Detalhe\n\nArquivo aninhado.\n', encoding='utf-8')
    monkeypatch.setattr('free_plaud.corpus.cli.get_settings', lambda: settings)
    monkeypatch.setattr('free_plaud.corpus.service.get_embedder', lambda model_name: FakeEmbedder())

    result = runner.invoke(app, ['corpus', 'index', str(root), '--recursive'])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload['status'] == 'success'
    assert payload['total_found'] == 2
    assert payload['indexed_count'] == 2
