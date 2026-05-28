import json
from io import BytesIO
from pathlib import Path
from urllib.error import HTTPError

import pytest

from free_plaud.app.config import Settings
from free_plaud.providers.answer import (
    AnswerProviderError,
    AnswerProviderTestResult,
    OpenAICompatibleAnswerProvider,
    build_grounded_chat_messages,
    get_answer_provider,
    test_answer_provider as run_answer_provider_test,
)


class FakeHTTPResponse:
    def __init__(self, payload: dict[str, object]) -> None:
        self.payload = payload

    def __enter__(self) -> 'FakeHTTPResponse':
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:  # noqa: ANN001
        return None

    def read(self) -> bytes:
        return json.dumps(self.payload).encode('utf-8')


def test_openai_compatible_provider_posts_chat_completion(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_urlopen(request, timeout):  # noqa: ANN001, ANN202
        captured['url'] = request.full_url
        captured['timeout'] = timeout
        captured['headers'] = dict(request.header_items())
        captured['body'] = json.loads(request.data.decode('utf-8'))
        return FakeHTTPResponse({'choices': [{'message': {'content': 'Resposta melhorada.'}}]})

    monkeypatch.setattr('free_plaud.providers.answer.urlopen', fake_urlopen)

    provider = OpenAICompatibleAnswerProvider(
        base_url='http://localhost:11434/v1',
        model='llama3.1:8b',
        api_key='local-key',
        temperature=0.1,
        timeout_seconds=12,
    )

    answer = provider.answer('Qual broker?', ['[chunk-1] RabbitMQ foi adotado.'])

    assert answer == 'Resposta melhorada.'
    assert captured['url'] == 'http://localhost:11434/v1/chat/completions'
    assert captured['timeout'] == 12
    assert captured['headers']['Authorization'] == 'Bearer local-key'
    body = captured['body']
    assert body['model'] == 'llama3.1:8b'  # type: ignore[index]
    assert body['temperature'] == 0.1  # type: ignore[index]
    assert 'RabbitMQ foi adotado' in body['messages'][1]['content']  # type: ignore[index]


def test_grounded_chat_messages_forbid_external_knowledge_and_define_sentinel() -> None:
    messages = build_grounded_chat_messages(
        'Qual broker?',
        ['[1]\nsource_path: note.md\nchunk_id: c1\ntrecho:\nRabbitMQ foi adotado.'],
    )

    system_prompt = messages[0]['content']
    user_prompt = messages[1]['content']
    assert 'usando exclusivamente os CONTEXTOS' in system_prompt
    assert 'Nao use conhecimento externo' in system_prompt
    assert 'Nao complete lacunas' in system_prompt
    assert 'NAO_ENCONTRADO' in system_prompt
    assert 'nao sustentam resposta' in system_prompt
    assert 'Cada frase factual precisa estar suportada' in system_prompt
    assert 'Preserve numeros, nomes e termos tecnicos exatamente' in system_prompt
    assert 'seja criativo' not in system_prompt.lower()
    assert 'PERGUNTA:\nQual broker?' in user_prompt
    assert 'CONTEXTOS:\n[1]' in user_prompt


def test_openai_compatible_provider_wraps_http_errors(monkeypatch) -> None:
    def fake_urlopen(request, timeout):  # noqa: ANN001, ANN202
        raise HTTPError(
            url=request.full_url,
            code=401,
            msg='Unauthorized',
            hdrs=None,
            fp=BytesIO(b'{"error":"bad key"}'),
        )

    monkeypatch.setattr('free_plaud.providers.answer.urlopen', fake_urlopen)
    provider = OpenAICompatibleAnswerProvider(base_url='https://api.example/v1', model='model')

    with pytest.raises(AnswerProviderError, match='401'):
        provider.answer('Pergunta?', ['[chunk] Evidencia.'])


def test_get_answer_provider_uses_local_defaults_and_keeps_extract_empty() -> None:
    assert get_answer_provider('extractive', model='unused') is None

    ollama = get_answer_provider('ollama', model='llama3.1:8b')
    lmstudio = get_answer_provider('lmstudio', model='local-model')

    assert isinstance(ollama, OpenAICompatibleAnswerProvider)
    assert ollama.base_url == 'http://localhost:11434/v1'
    assert isinstance(lmstudio, OpenAICompatibleAnswerProvider)
    assert lmstudio.base_url == 'http://localhost:1234/v1'


def _settings(tmp_path: Path, **overrides) -> Settings:  # noqa: ANN003
    data = {
        'workspace_dir': tmp_path,
        'data_dir': tmp_path / 'data',
        'notes_dir': tmp_path / 'data' / 'corpus' / 'notes',
        'datasets_dir': tmp_path / 'data' / 'datasets',
        'results_dir': tmp_path / 'data' / 'results',
        'sqlite_path': tmp_path / 'data' / 'results' / 'free_plaud.sqlite3',
        'vector_store_dir': tmp_path / 'data' / 'results' / 'vector_store',
        'answer_provider': 'ollama',
        'answer_model': 'llama3.1:8b',
        'answer_base_url': 'http://localhost:11434/v1',
        'answer_timeout_seconds': 12,
    }
    data.update(overrides)
    return Settings(**data)


def test_provider_test_posts_synthetic_prompt_and_returns_ok(monkeypatch, tmp_path: Path) -> None:
    captured: dict[str, object] = {}

    def fake_urlopen(request, timeout):  # noqa: ANN001, ANN202
        captured['url'] = request.full_url
        captured['timeout'] = timeout
        captured['headers'] = dict(request.header_items())
        captured['body'] = json.loads(request.data.decode('utf-8'))
        return FakeHTTPResponse({'choices': [{'message': {'content': 'ok'}}]})

    monkeypatch.setattr('free_plaud.providers.answer.urlopen', fake_urlopen)

    result = run_answer_provider_test(_settings(tmp_path))

    assert isinstance(result, AnswerProviderTestResult)
    assert result.status == 'ok'
    assert result.provider == 'ollama'
    assert result.model == 'llama3.1:8b'
    assert result.base_url == 'http://localhost:11434/v1'
    assert result.error is None
    assert captured['url'] == 'http://localhost:11434/v1/chat/completions'
    assert captured['timeout'] == 12
    body = captured['body']
    assert body['messages'] == [{'role': 'user', 'content': 'Responda somente: ok'}]  # type: ignore[index]


def test_provider_test_http_401_returns_controlled_error_without_secret(monkeypatch, tmp_path: Path) -> None:
    def fake_urlopen(request, timeout):  # noqa: ANN001, ANN202
        raise HTTPError(
            url=request.full_url,
            code=401,
            msg='Unauthorized',
            hdrs=None,
            fp=BytesIO(b'{"error":"bad key sk-secret"}'),
        )

    monkeypatch.setattr('free_plaud.providers.answer.urlopen', fake_urlopen)

    result = run_answer_provider_test(_settings(tmp_path, answer_api_key='sk-secret'))

    assert result.status == 'error'
    assert result.error == 'HTTP 401: Unauthorized'
    assert 'sk-secret' not in result.model_dump_json()


def test_provider_test_timeout_returns_controlled_error(monkeypatch, tmp_path: Path) -> None:
    def fake_urlopen(request, timeout):  # noqa: ANN001, ANN202
        raise TimeoutError

    monkeypatch.setattr('free_plaud.providers.answer.urlopen', fake_urlopen)

    result = run_answer_provider_test(_settings(tmp_path))

    assert result.status == 'error'
    assert result.error == 'Provider excedeu timeout.'


def test_provider_test_invalid_base_url_returns_controlled_error(tmp_path: Path) -> None:
    result = run_answer_provider_test(_settings(tmp_path, answer_base_url='localhost:11434/v1'))

    assert result.status == 'error'
    assert result.error == 'Provider base_url invalida. Use http:// ou https://.'


def test_provider_test_urlopen_value_error_returns_controlled_error(monkeypatch, tmp_path: Path) -> None:
    def fake_urlopen(request, timeout):  # noqa: ANN001, ANN202
        raise ValueError('unknown url type: localhost')

    monkeypatch.setattr('free_plaud.providers.answer.urlopen', fake_urlopen)

    result = run_answer_provider_test(_settings(tmp_path))

    assert result.status == 'error'
    assert result.error == 'Provider base_url invalida. Use http:// ou https://.'


def test_provider_test_accepts_non_empty_model_response(monkeypatch, tmp_path: Path) -> None:
    def fake_urlopen(request, timeout):  # noqa: ANN001, ANN202
        return FakeHTTPResponse({'choices': [{'message': {'content': 'servico pronto'}}]})

    monkeypatch.setattr('free_plaud.providers.answer.urlopen', fake_urlopen)

    result = run_answer_provider_test(_settings(tmp_path))

    assert result.status == 'ok'
    assert result.error is None


def test_provider_test_rejects_empty_content(monkeypatch, tmp_path: Path) -> None:
    def fake_urlopen(request, timeout):  # noqa: ANN001, ANN202
        return FakeHTTPResponse({'choices': [{'message': {'content': '   '}}]})

    monkeypatch.setattr('free_plaud.providers.answer.urlopen', fake_urlopen)

    result = run_answer_provider_test(_settings(tmp_path))

    assert result.status == 'error'
    assert result.error == 'Provider retornou resposta vazia.'


def test_provider_test_rejects_invalid_payload(monkeypatch, tmp_path: Path) -> None:
    def fake_urlopen(request, timeout):  # noqa: ANN001, ANN202
        return FakeHTTPResponse({'choices': []})

    monkeypatch.setattr('free_plaud.providers.answer.urlopen', fake_urlopen)

    result = run_answer_provider_test(_settings(tmp_path))

    assert result.status == 'error'
    assert result.error == 'Provider retornou payload invalido.'


def test_provider_test_extractive_is_not_applicable(tmp_path: Path) -> None:
    result = run_answer_provider_test(_settings(tmp_path, answer_provider='extractive'))

    assert result.status == 'not_applicable'
    assert result.provider == 'extractive'
    assert result.error is None
