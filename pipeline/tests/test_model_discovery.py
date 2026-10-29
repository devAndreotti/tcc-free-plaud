import json
from io import BytesIO
from typing import Self
from urllib.error import HTTPError, URLError

import pytest

from escolio.app.config import Settings
from escolio.providers.model_discovery import (
    clear_model_discovery_cache,
    list_answer_models,
)


class FakeResponse:
    def __init__(self, payload: object | bytes) -> None:
        self.payload = payload if isinstance(payload, bytes) else json.dumps(payload).encode('utf-8')

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def read(self) -> bytes:
        return self.payload


def _settings(tmp_path, *, provider='ollama', base_url=None, api_key=None) -> Settings:
    return Settings(
        workspace_dir=tmp_path,
        data_dir=tmp_path / 'data',
        notes_dir=tmp_path / 'data' / 'corpus' / 'notes',
        datasets_dir=tmp_path / 'data' / 'datasets',
        results_dir=tmp_path / 'data' / 'results',
        sqlite_path=tmp_path / 'data' / 'results' / 'escolio.sqlite3',
        vector_store_dir=tmp_path / 'data' / 'results' / 'vector_store',
        answer_provider=provider,
        answer_base_url=base_url,
        answer_api_key=api_key,
    )


def test_extractive_returns_not_applicable_without_network(monkeypatch, tmp_path) -> None:
    def fail_urlopen(*args, **kwargs):
        raise AssertionError('extractive nao deve chamar rede')

    monkeypatch.setattr('escolio.providers.model_discovery.urlopen', fail_urlopen)

    result = list_answer_models(_settings(tmp_path, provider='extractive'))

    assert result.status == 'not_applicable'
    assert result.provider == 'extractive'
    assert result.base_url is None
    assert result.models == []


def test_ollama_default_calls_api_tags(monkeypatch, tmp_path) -> None:
    clear_model_discovery_cache()
    called_urls: list[str] = []

    def fake_urlopen(request, timeout):
        called_urls.append(request.full_url)
        assert timeout == pytest.approx(2.0)
        return FakeResponse({'models': [{'name': 'llama3.1:8b', 'size': 123, 'details': {'family': 'llama'}}]})

    monkeypatch.setattr('escolio.providers.model_discovery.urlopen', fake_urlopen)

    result = list_answer_models(_settings(tmp_path, provider='ollama'))

    assert called_urls == ['http://localhost:11434/api/tags']
    assert result.status == 'ok'
    assert result.base_url == 'http://localhost:11434'
    assert result.models[0].id == 'llama3.1:8b'
    assert result.models[0].details['size'] == 123
    assert result.models[0].details['family'] == 'llama'


def test_ollama_deixa_modelos_de_embedding_fora_da_lista_de_resposta(monkeypatch, tmp_path) -> None:
    clear_model_discovery_cache()
    tags = {
        'models': [
            {'name': 'qchat:latest', 'details': {'family': 'qwen2'}},
            {'name': 'nomic-embed-text:latest', 'details': {'family': 'nomic-bert'}},
            {'name': 'all-minilm:22m', 'details': {'family': 'bert'}},
        ]
    }
    monkeypatch.setattr('escolio.providers.model_discovery.urlopen', lambda request, timeout: FakeResponse(tags))

    result = list_answer_models(_settings(tmp_path, provider='ollama'))

    assert [model.id for model in result.models] == ['qchat:latest']


def test_ollama_strips_v1_from_base_url(monkeypatch, tmp_path) -> None:
    clear_model_discovery_cache()
    called_urls: list[str] = []

    def fake_urlopen(request, timeout):
        called_urls.append(request.full_url)
        return FakeResponse({'models': []})

    monkeypatch.setattr('escolio.providers.model_discovery.urlopen', fake_urlopen)

    result = list_answer_models(_settings(tmp_path, provider='ollama', base_url='http://localhost:11434/v1/'))

    assert called_urls == ['http://localhost:11434/api/tags']
    assert result.status == 'ok'


def test_lmstudio_calls_v1_models(monkeypatch, tmp_path) -> None:
    clear_model_discovery_cache()
    called_urls: list[str] = []

    def fake_urlopen(request, timeout):
        called_urls.append(request.full_url)
        return FakeResponse({'data': [{'id': 'local-model', 'object': 'model'}]})

    monkeypatch.setattr('escolio.providers.model_discovery.urlopen', fake_urlopen)

    result = list_answer_models(_settings(tmp_path, provider='lmstudio'))

    assert called_urls == ['http://localhost:1234/v1/models']
    assert result.status == 'ok'
    assert result.models[0].id == 'local-model'
    assert result.models[0].details['object'] == 'model'


def test_openai_compatible_custom_calls_models_without_api_key(monkeypatch, tmp_path) -> None:
    clear_model_discovery_cache()
    called_headers: list[dict[str, str]] = []

    def fake_urlopen(request, timeout):
        called_headers.append(dict(request.header_items()))
        assert request.full_url == 'http://localhost:9999/v1/models'
        return FakeResponse({'data': [{'id': 'custom-model'}]})

    monkeypatch.setattr('escolio.providers.model_discovery.urlopen', fake_urlopen)

    result = list_answer_models(
        _settings(tmp_path, provider='openai-compatible', base_url='http://localhost:9999/v1')
    )

    assert result.status == 'ok'
    assert result.models[0].id == 'custom-model'
    assert 'Authorization' not in called_headers[0]


def test_openai_compatible_default_without_api_key_returns_unauthorized(monkeypatch, tmp_path) -> None:
    def fail_urlopen(*args, **kwargs):
        raise AssertionError('default OpenAI sem chave nao deve chamar rede')

    monkeypatch.setattr('escolio.providers.model_discovery.urlopen', fail_urlopen)

    result = list_answer_models(_settings(tmp_path, provider='openai-compatible'))

    assert result.status == 'unauthorized'
    assert result.models == []


def test_http_unauthorized_is_safe(monkeypatch, tmp_path) -> None:
    clear_model_discovery_cache()

    def fake_urlopen(request, timeout):
        raise HTTPError(request.full_url, 401, 'Unauthorized', hdrs=None, fp=BytesIO(b'token sk-secret leaked'))

    monkeypatch.setattr('escolio.providers.model_discovery.urlopen', fake_urlopen)

    result = list_answer_models(
        _settings(tmp_path, provider='openai-compatible', base_url='http://localhost:9999/v1', api_key='sk-secret')
    )

    assert result.status == 'unauthorized'
    assert 'sk-secret' not in (result.message or '')
    assert 'token' not in (result.message or '').lower()


def test_connection_error_is_offline(monkeypatch, tmp_path) -> None:
    clear_model_discovery_cache()

    def fake_urlopen(request, timeout):
        raise URLError('connection refused')

    monkeypatch.setattr('escolio.providers.model_discovery.urlopen', fake_urlopen)

    result = list_answer_models(_settings(tmp_path, provider='ollama'))

    assert result.status == 'offline'
    assert result.base_url == 'http://localhost:11434'
    assert result.models == []


def test_offline_result_is_not_cached(monkeypatch, tmp_path) -> None:
    clear_model_discovery_cache()
    online = False

    def fake_urlopen(request, timeout):
        if not online:
            raise URLError('connection refused')
        return FakeResponse({'models': [{'name': 'qchat:latest'}]})

    monkeypatch.setattr('escolio.providers.model_discovery.urlopen', fake_urlopen)

    offline = list_answer_models(_settings(tmp_path, provider='ollama'))
    online = True
    retry = list_answer_models(_settings(tmp_path, provider='ollama'))

    assert offline.status == 'offline'
    assert retry.status == 'ok'


def test_invalid_json_is_error(monkeypatch, tmp_path) -> None:
    clear_model_discovery_cache()

    def fake_urlopen(request, timeout):
        return FakeResponse(b'{')

    monkeypatch.setattr('escolio.providers.model_discovery.urlopen', fake_urlopen)

    result = list_answer_models(_settings(tmp_path, provider='ollama'))

    assert result.status == 'error'
    assert 'payload' in (result.message or '')


def test_cache_is_scoped_by_provider_and_base_url(monkeypatch, tmp_path) -> None:
    clear_model_discovery_cache()
    calls: list[str] = []

    def fake_urlopen(request, timeout):
        calls.append(request.full_url)
        return FakeResponse({'models': [{'name': f'model-{len(calls)}'}]})

    monkeypatch.setattr('escolio.providers.model_discovery.urlopen', fake_urlopen)

    first = list_answer_models(_settings(tmp_path, provider='ollama', base_url='http://localhost:11434'))
    second = list_answer_models(_settings(tmp_path, provider='ollama', base_url='http://localhost:11434'))
    third = list_answer_models(_settings(tmp_path, provider='ollama', base_url='http://localhost:11435'))

    assert first.cached is False
    assert second.cached is True
    assert second.models[0].id == first.models[0].id
    assert third.cached is False
    assert calls == ['http://localhost:11434/api/tags', 'http://localhost:11435/api/tags']
