import json
from urllib.error import URLError

from typer.testing import CliRunner

from free_plaud.app.config import Settings
from free_plaud.cli import app
from free_plaud.providers.model_discovery import ModelDiscoveryResult, ModelInfo
from free_plaud.providers.provisioning import (
    MODEL_CATALOG,
    EnsureModelResult,
    PullProgress,
    catalog_entry,
    detect_runtime,
    ensure_model,
)

runner = CliRunner()


def _settings(tmp_path, *, provider='ollama', model='gemma2:2b-instruct-q4_K_M', base_url=None):  # noqa: ANN001
    return Settings(
        workspace_dir=tmp_path,
        data_dir=tmp_path / 'data',
        notes_dir=tmp_path / 'data' / 'corpus' / 'notes',
        datasets_dir=tmp_path / 'data' / 'datasets',
        results_dir=tmp_path / 'data' / 'results',
        sqlite_path=tmp_path / 'data' / 'results' / 'free_plaud.sqlite3',
        vector_store_dir=tmp_path / 'data' / 'results' / 'vector_store',
        answer_provider=provider,
        answer_model=model,
        answer_base_url=base_url,
    )


class FakeStreamResponse:
    def __init__(self, lines: list[bytes]) -> None:
        self._lines = lines

    def __enter__(self) -> 'FakeStreamResponse':
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def __iter__(self):  # noqa: ANN204
        return iter(self._lines)


def _discovery(status, models=None, base_url='http://localhost:11434', message=None):  # noqa: ANN001
    return ModelDiscoveryResult(
        provider='ollama',
        base_url=base_url,
        status=status,
        models=models or [],
        latency_ms=1,
        message=message,
    )


def test_catalog_seeded_with_both_gemmas() -> None:
    ids = {entry.catalog_id for entry in MODEL_CATALOG}
    assert {'gemma-veloz', 'gemma-inteligente'} <= ids

    veloz = catalog_entry('gemma-veloz')
    assert veloz is not None
    assert veloz.context_tokens == 128_000
    assert veloz.quantization == 'Q4_K_M'
    assert catalog_entry('inexistente') is None


def test_detect_runtime_ready_when_model_installed(monkeypatch, tmp_path) -> None:  # noqa: ANN001
    model = ModelInfo(id='gemma2:2b-instruct-q4_K_M', label='gemma2', provider='ollama')
    monkeypatch.setattr(
        'free_plaud.providers.provisioning.list_answer_models',
        lambda settings, **kwargs: _discovery('ok', models=[model]),
    )

    report = detect_runtime(_settings(tmp_path, model='gemma2:2b-instruct-q4_K_M'))

    assert report.status == 'ready'
    assert 'gemma2:2b-instruct-q4_K_M' in report.installed_models


def test_detect_runtime_no_model_when_server_up_but_model_missing(monkeypatch, tmp_path) -> None:  # noqa: ANN001
    other = ModelInfo(id='llama3.1:8b', label='llama', provider='ollama')
    monkeypatch.setattr(
        'free_plaud.providers.provisioning.list_answer_models',
        lambda settings, **kwargs: _discovery('ok', models=[other]),
    )

    report = detect_runtime(_settings(tmp_path, model='gemma2:2b-instruct-q4_K_M'))

    assert report.status == 'no_model'
    assert report.message is not None


def test_detect_runtime_offline_propagates(monkeypatch, tmp_path) -> None:  # noqa: ANN001
    monkeypatch.setattr(
        'free_plaud.providers.provisioning.list_answer_models',
        lambda settings, **kwargs: _discovery('offline', message='Servidor indisponivel ou timeout.'),
    )

    report = detect_runtime(_settings(tmp_path))

    assert report.status == 'offline'


def test_ensure_model_streams_progress_until_success(monkeypatch, tmp_path) -> None:  # noqa: ANN001
    lines = [
        json.dumps({'status': 'pulling manifest'}).encode('utf-8'),
        json.dumps({'status': 'downloading', 'completed': 50, 'total': 100}).encode('utf-8'),
        json.dumps({'status': 'success'}).encode('utf-8'),
    ]
    captured: dict[str, object] = {}

    def fake_urlopen(request, timeout):  # noqa: ANN001, ANN202
        captured['url'] = request.full_url
        captured['body'] = json.loads(request.data.decode('utf-8'))
        return FakeStreamResponse(lines)

    monkeypatch.setattr('free_plaud.providers.provisioning.urlopen', fake_urlopen)

    events: list[PullProgress] = []
    result = ensure_model('gemma2:2b-instruct-q4_K_M', _settings(tmp_path), on_progress=events.append)

    assert captured['url'] == 'http://localhost:11434/api/pull'
    assert captured['body'] == {'name': 'gemma2:2b-instruct-q4_K_M', 'stream': True}
    assert isinstance(result, EnsureModelResult)
    assert result.ok is True
    assert result.final_status == 'success'
    assert any(event.completed == 50 and event.total == 100 for event in events)
    assert events[-1].status == 'success'


def test_ensure_model_surfaces_error_event(monkeypatch, tmp_path) -> None:  # noqa: ANN001
    lines = [json.dumps({'error': 'pull model manifest: file does not exist'}).encode('utf-8')]
    monkeypatch.setattr(
        'free_plaud.providers.provisioning.urlopen',
        lambda request, timeout: FakeStreamResponse(lines),
    )

    result = ensure_model('inexistente:q4', _settings(tmp_path))

    assert result.ok is False
    assert result.error is not None
    assert 'file does not exist' in result.error


def test_ensure_model_reports_offline(monkeypatch, tmp_path) -> None:  # noqa: ANN001
    def boom(request, timeout):  # noqa: ANN001, ANN202
        raise URLError('connection refused')

    monkeypatch.setattr('free_plaud.providers.provisioning.urlopen', boom)

    result = ensure_model('gemma2:2b-instruct-q4_K_M', _settings(tmp_path))

    assert result.ok is False
    assert 'indisponivel' in result.error


def test_ensure_model_rejects_non_ollama_without_network(monkeypatch, tmp_path) -> None:  # noqa: ANN001
    def fail(*args, **kwargs):  # noqa: ANN002, ANN003
        raise AssertionError('nao deve tocar a rede para provider nao-ollama')

    monkeypatch.setattr('free_plaud.providers.provisioning.urlopen', fail)

    result = ensure_model('gpt-4o-mini', _settings(tmp_path, provider='openai-compatible'))

    assert result.ok is False
    assert 'ollama' in result.error


def test_provider_catalog_cli_lists_presets() -> None:
    result = runner.invoke(app, ['provider', 'catalog'])

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    catalog_ids = {entry['catalog_id'] for entry in payload}
    assert {'gemma-veloz', 'gemma-inteligente'} <= catalog_ids


def test_provider_pull_cli_resolves_catalog_and_streams(monkeypatch, tmp_path) -> None:  # noqa: ANN001
    lines = [
        json.dumps({'status': 'downloading', 'completed': 10, 'total': 10}).encode('utf-8'),
        json.dumps({'status': 'success'}).encode('utf-8'),
    ]
    captured: dict[str, object] = {}

    def fake_urlopen(request, timeout):  # noqa: ANN001, ANN202
        captured['body'] = json.loads(request.data.decode('utf-8'))
        return FakeStreamResponse(lines)

    monkeypatch.setattr('free_plaud.providers.provisioning.urlopen', fake_urlopen)
    monkeypatch.setattr('free_plaud.providers.provisioning.get_settings', lambda: _settings(tmp_path))

    result = runner.invoke(app, ['provider', 'pull', 'gemma-veloz'])

    assert result.exit_code == 0, result.output
    # catalog_id 'gemma-veloz' deve ser resolvido para a tag de pull concreta.
    assert captured['body'] == {'name': 'gemma2:2b-instruct-q4_K_M', 'stream': True}
    payload = json.loads(result.stdout)
    assert payload['ok'] is True
