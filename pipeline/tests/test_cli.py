import json
from pathlib import Path

from typer.testing import CliRunner

from free_plaud.app.config import Settings
from free_plaud.cli import app
from free_plaud.storage.sqlite import count_chunks, count_notes, init_sqlite
from free_plaud.storage.vector import LocalVectorStore

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


def test_corpus_status_cli_returns_consistency_json(monkeypatch, tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    monkeypatch.setattr('free_plaud.corpus.cli.get_settings', lambda: settings)

    result = runner.invoke(app, ['corpus', 'status'])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload['status'] == 'empty'
    assert payload['notes_count'] == 0
    assert payload['sqlite_chunks_count'] == 0
    assert payload['vector_chunks_count'] == 0


def test_corpus_reset_cli_previews_by_default_and_executes_with_yes(monkeypatch, tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    source = tmp_path / 'resetavel.md'
    source.write_text('# Resetavel\n\nRabbitMQ foi adotado como broker.\n', encoding='utf-8')
    monkeypatch.setattr('free_plaud.corpus.cli.get_settings', lambda: settings)
    monkeypatch.setattr('free_plaud.corpus.service.get_embedder', lambda model_name: FakeEmbedder())

    index_result = runner.invoke(app, ['corpus', 'index', str(source)])
    preview_result = runner.invoke(app, ['corpus', 'reset', '--dry-run'])
    connection = init_sqlite(settings.sqlite_path)
    vector_store = LocalVectorStore(settings.vector_store_dir, collection_name=settings.vector_collection_name)

    assert index_result.exit_code == 0
    assert preview_result.exit_code == 0
    preview = json.loads(preview_result.stdout)
    assert preview['status'] == 'preview'
    assert preview['dry_run'] is True
    assert count_notes(connection) == 1
    assert count_chunks(connection) > 0
    assert vector_store.count() > 0

    reset_result = runner.invoke(app, ['corpus', 'reset', '--yes'])
    reset = json.loads(reset_result.stdout)

    assert reset_result.exit_code == 0
    assert reset['status'] == 'reset'
    assert reset['dry_run'] is False
    assert count_notes(connection) == 0
    assert count_chunks(connection) == 0
    assert vector_store.count() == 0


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


def test_corpus_ask_cli_answers_against_indexed_directory(monkeypatch, tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    root = tmp_path / 'corpus'
    root.mkdir()
    (root / 'broker.md').write_text(
        '# Broker\n\nRabbitMQ foi adotado como message broker padrao do pipeline.\n',
        encoding='utf-8',
    )
    (root / 'runbook.md').write_text(
        '# Runbook\n\nO time SRE ficou responsavel pelo runbook de operacao.\n',
        encoding='utf-8',
    )
    monkeypatch.setattr('free_plaud.corpus.cli.get_settings', lambda: settings)
    monkeypatch.setattr('free_plaud.corpus.cli.get_embedder', lambda model_name: FakeEmbedder())
    monkeypatch.setattr('free_plaud.corpus.service.get_embedder', lambda model_name: FakeEmbedder())

    index_result = runner.invoke(app, ['corpus', 'index', str(root), '--recursive'])
    ask_result = runner.invoke(
        app,
        [
            'corpus',
            'ask',
            '--question',
            'Qual message broker foi adotado e qual equipe ficou responsavel pelo runbook?',
            '--strategy',
            'hybrid',
            '--top-k',
            '4',
        ],
    )

    assert index_result.exit_code == 0
    assert ask_result.exit_code == 0
    payload = json.loads(ask_result.stdout)
    assert payload['status'] == 'answer'
    assert 'RabbitMQ' in payload['answer']
    assert 'SRE' in payload['answer']
    assert len({citation['note_id'] for citation in payload['citations']}) >= 2
