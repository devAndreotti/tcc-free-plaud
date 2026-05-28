import json
from pathlib import Path

from typer.testing import CliRunner

from free_plaud.app.config import Settings, get_settings
from free_plaud.app.doctor_models import DoctorCheck, DoctorReport
from free_plaud.cli import app
from free_plaud.providers.model_discovery import ModelDiscoveryResult, ModelInfo
from free_plaud.providers.answer import AnswerProviderTestResult
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
    assert 'menu' in result.stdout


def test_config_cli_saves_user_settings(monkeypatch, tmp_path: Path) -> None:
    results_dir = tmp_path / 'data' / 'results'
    monkeypatch.setenv('FREE_PLAUD_RESULTS_DIR', str(results_dir))
    get_settings.cache_clear()

    result = runner.invoke(app, ['config', 'set', 'embedding_device', 'cuda'])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload['embedding_device'] == 'cuda'
    assert (results_dir / 'user_settings.json').exists()
    get_settings.cache_clear()


def test_config_preset_preview_does_not_save(monkeypatch, tmp_path: Path) -> None:
    results_dir = tmp_path / 'data' / 'results'
    monkeypatch.setenv('FREE_PLAUD_WORKSPACE_DIR', str(tmp_path))
    monkeypatch.setenv('FREE_PLAUD_RESULTS_DIR', str(results_dir))
    get_settings.cache_clear()

    result = runner.invoke(app, ['config', 'preset', 'preview', 'cpu_rapido'])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload['preset']['key'] == 'cpu_rapido'
    assert payload['values']['retrieval_top_k'] == 4
    assert not (results_dir / 'user_settings.json').exists()
    get_settings.cache_clear()


def test_config_preset_apply_saves_transactional_payload(monkeypatch, tmp_path: Path) -> None:
    results_dir = tmp_path / 'data' / 'results'
    monkeypatch.setenv('FREE_PLAUD_WORKSPACE_DIR', str(tmp_path))
    monkeypatch.setenv('FREE_PLAUD_RESULTS_DIR', str(results_dir))
    get_settings.cache_clear()

    result = runner.invoke(app, ['config', 'preset', 'apply', 'vault_grande'])

    assert result.exit_code == 0
    payload = json.loads((results_dir / 'user_settings.json').read_text(encoding='utf-8'))
    assert payload['corpus_commit_mode'] == 'microbatch'
    assert payload['corpus_embedding_batch_size'] == 64
    assert payload['corpus_index_workers'] == 2
    assert payload['corpus_recursive_default'] is True
    assert 'answer_api_key' not in payload
    get_settings.cache_clear()


def test_doctor_cli_renders_structured_report(monkeypatch, tmp_path: Path) -> None:
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
    monkeypatch.setattr(
        'free_plaud.cli.run_doctor',
        lambda *, settings: DoctorReport(
            status='warning',
            checks=[
                DoctorCheck(
                    code='settings.embedding_model',
                    status='error',
                    message='fake-hash e modelo de teste.',
                    action='Use chroma-default.',
                    latency_ms=1,
                ),
                DoctorCheck(code='corpus', status='ok', message='Corpus consistente.', latency_ms=2),
            ],
            latency_ms=3,
            ok_count=1,
            warning_count=0,
            error_count=1,
        ),
    )

    result = runner.invoke(app, ['doctor'])

    assert result.exit_code == 0
    assert 'status: warning' in result.stdout
    assert '- settings.embedding_model: error - fake-hash e modelo de teste.' in result.stdout
    assert 'acao: Use chroma-default.' in result.stdout
    assert '- corpus: ok - Corpus consistente.' in result.stdout
    assert settings.data_dir.exists()
    assert settings.notes_dir.exists()
    assert settings.datasets_dir.exists()
    assert settings.results_dir.exists()
    assert settings.vector_store_dir.exists()


def test_provider_test_answer_cli_returns_json(monkeypatch) -> None:
    monkeypatch.setattr(
        'free_plaud.providers.cli.test_answer_provider',
        lambda: AnswerProviderTestResult(
            provider='ollama',
            model='llama3.1:8b',
            base_url='http://localhost:11434/v1',
            status='ok',
            latency_ms=7,
            error=None,
        ),
    )

    result = runner.invoke(app, ['provider', 'test-answer'])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload['status'] == 'ok'
    assert payload['provider'] == 'ollama'
    assert payload['latency_ms'] == 7


def test_provider_list_models_cli_returns_json(monkeypatch) -> None:
    monkeypatch.setattr(
        'free_plaud.providers.cli.list_answer_models',
        lambda: ModelDiscoveryResult(
            provider='ollama',
            base_url='http://localhost:11434',
            status='ok',
            models=[ModelInfo(id='llama3.1:8b', label='llama3.1:8b', provider='ollama', details={'size': 123})],
            latency_ms=5,
        ),
    )

    result = runner.invoke(app, ['provider', 'list-models'])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload['status'] == 'ok'
    assert payload['models'][0]['id'] == 'llama3.1:8b'
    assert payload['models'][0]['details']['size'] == 123


def test_corpus_index_cli_persists_file(monkeypatch, tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    source = tmp_path / 'documento com espaco.md'
    source.write_text(
        '# Documento\n\n'
        'O corpus local deve indexar arquivos com path contendo espaco.\n',
        encoding='utf-8',
    )
    monkeypatch.setattr('free_plaud.corpus.cli.get_settings', lambda: settings)
    monkeypatch.setattr('free_plaud.corpus.service.get_embedder', lambda model_name, **kwargs: FakeEmbedder())

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


def test_corpus_ask_hybrid_rejects_fake_hash_with_actionable_error(monkeypatch, tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    monkeypatch.setattr('free_plaud.corpus.cli.get_settings', lambda: settings)

    result = runner.invoke(
        app,
        [
            'corpus',
            'ask',
            '--question',
            'O que e o corpus?',
            '--strategy',
            'hybrid',
        ],
    )

    combined_output = f'{result.stdout}\n{result.stderr}\n{result.exception or ""}'
    assert result.exit_code == 1
    assert 'fake-hash e modelo de teste' in combined_output
    assert 'uv run free-plaud config preset apply cpu_rapido' in combined_output
    assert 'Traceback' not in combined_output


def test_corpus_ask_lexical_allows_fake_hash_without_embedder(monkeypatch, tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    monkeypatch.setattr('free_plaud.corpus.cli.get_settings', lambda: settings)

    def fail_get_embedder(*args, **kwargs):  # noqa: ANN002, ANN003
        raise AssertionError('lexical nao deve inicializar embedder')

    monkeypatch.setattr('free_plaud.corpus.cli.get_embedder', fail_get_embedder)

    result = runner.invoke(
        app,
        [
            'corpus',
            'ask',
            '--question',
            'O que e o corpus?',
            '--strategy',
            'lexical',
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload['status'] == 'no_answer'
    assert payload['reason_for_no_answer'] == 'empty_corpus'


def test_corpus_embedding_info_cli_reports_device(monkeypatch, tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    settings.embedding_model = 'chroma-default'
    settings.embedding_device = 'cuda'
    monkeypatch.setattr('free_plaud.corpus.cli.get_settings', lambda: settings)

    result = runner.invoke(app, ['corpus', 'embedding-info'])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload['model_name'] == 'chroma-default'
    assert payload['requested_device'] == 'cuda'
    assert payload['device_applicable'] is False


def test_corpus_reset_cli_previews_by_default_and_executes_with_yes(monkeypatch, tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    source = tmp_path / 'resetavel.md'
    source.write_text('# Resetavel\n\nRabbitMQ foi adotado como broker.\n', encoding='utf-8')
    monkeypatch.setattr('free_plaud.corpus.cli.get_settings', lambda: settings)
    monkeypatch.setattr('free_plaud.corpus.service.get_embedder', lambda model_name, **kwargs: FakeEmbedder())

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


def test_corpus_rebuild_cli_rebuilds_directory_with_yes(monkeypatch, tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    target = tmp_path / 'target'
    target.mkdir()
    (target / 'broker.md').write_text('# Broker\n\nRabbitMQ foi adotado como broker.\n', encoding='utf-8')
    (target / 'runbook.md').write_text('# Runbook\n\nO time SRE ficou responsavel pelo runbook.\n', encoding='utf-8')
    monkeypatch.setattr('free_plaud.corpus.cli.get_settings', lambda: settings)
    monkeypatch.setattr('free_plaud.corpus.service.get_embedder', lambda model_name, **kwargs: FakeEmbedder())

    preview_result = runner.invoke(app, ['corpus', 'rebuild', str(target), '--recursive', '--dry-run'])
    rebuild_result = runner.invoke(app, ['corpus', 'rebuild', str(target), '--recursive', '--yes'])

    assert preview_result.exit_code == 0
    preview = json.loads(preview_result.stdout)
    assert preview['status'] == 'preview'
    assert preview['dry_run'] is True
    assert preview['index_result'] is None

    assert rebuild_result.exit_code == 0
    payload = json.loads(rebuild_result.stdout)
    assert payload['status'] == 'success'
    assert payload['dry_run'] is False
    assert payload['index_result']['indexed_count'] == 2
    assert payload['after_status']['status'] == 'clean'


def test_corpus_index_cli_returns_non_zero_for_invalid_file(monkeypatch, tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    source = tmp_path / 'planilha.xlsx'
    source.write_text('conteudo', encoding='utf-8')
    monkeypatch.setattr('free_plaud.corpus.cli.get_settings', lambda: settings)
    monkeypatch.setattr('free_plaud.corpus.service.get_embedder', lambda model_name, **kwargs: FakeEmbedder())

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
    monkeypatch.setattr('free_plaud.corpus.service.get_embedder', lambda model_name, **kwargs: FakeEmbedder())

    result = runner.invoke(app, ['corpus', 'index', str(root), '--recursive'])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload['status'] == 'success'
    assert payload['total_found'] == 2
    assert payload['indexed_count'] == 2


def test_corpus_ask_cli_answers_against_indexed_directory(monkeypatch, tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    settings.embedding_model = 'sentence-transformer:fake-hash'
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
    monkeypatch.setattr('free_plaud.corpus.cli.get_embedder', lambda model_name, **kwargs: FakeEmbedder())
    monkeypatch.setattr('free_plaud.corpus.service.get_embedder', lambda model_name, **kwargs: FakeEmbedder())

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
    assert 'debug' not in payload

    debug_result = runner.invoke(
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
            '--debug',
        ],
    )

    assert debug_result.exit_code == 0
    debug_payload = json.loads(debug_result.stdout)
    assert debug_payload['debug']['strategy'] == 'hybrid'
    assert debug_payload['debug']['hits']
    assert debug_payload['debug']['hits'][0]['score'] > 0
