import json
from io import BytesIO
from pathlib import Path
from typing import Self
from urllib.error import HTTPError

import pytest

from free_plaud.app.config import Settings
from free_plaud.providers.answer import (
    EMPTY_ANSWER_ERROR,
    REASONING_EMPTY_ANSWER_ERROR,
    AnswerProviderError,
    AnswerProviderTestResult,
    OpenAICompatibleAnswerProvider,
    build_grounded_chat_messages,
    get_answer_provider,
)
from free_plaud.providers.answer import (
    test_answer_provider as run_answer_provider_test,
)
from free_plaud.providers.smoke import run_provider_smoke_local


class FakeHTTPResponse:
    def __init__(self, payload: dict[str, object]) -> None:
        self.payload = payload

    def __enter__(self) -> Self:
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        return None

    def read(self) -> bytes:
        return json.dumps(self.payload).encode('utf-8')


class FakeSmokeAnswerProvider:
    provider_name = 'fake-smoke'
    model = 'fake-smoke-model'

    def __init__(self) -> None:
        self.questions: list[str] = []

    def answer(self, question: str, contexts: list[str]) -> str:
        self.questions.append(question)
        assert contexts
        return 'Estrutura Disco D descreve a organizacao do disco D para arquivos de trabalho e repositorios.'


def test_openai_compatible_provider_posts_chat_completion(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_urlopen(request, timeout):
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
    def fake_urlopen(request, timeout):
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


def test_get_answer_provider_forwards_max_tokens() -> None:
    provider = get_answer_provider('ollama', model='gemma4-cuda', max_tokens=512)

    assert isinstance(provider, OpenAICompatibleAnswerProvider)
    assert provider.max_tokens == 512


def test_openai_compatible_provider_omits_max_tokens_by_default(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_urlopen(request, timeout):
        captured['body'] = json.loads(request.data.decode('utf-8'))
        return FakeHTTPResponse({'choices': [{'message': {'content': 'ok'}}]})

    monkeypatch.setattr('free_plaud.providers.answer.urlopen', fake_urlopen)
    provider = OpenAICompatibleAnswerProvider(base_url='http://localhost:11434/v1', model='gemma4-cuda')

    provider.answer('Pergunta?', ['[chunk] Evidencia.'])

    assert 'max_tokens' not in captured['body']  # type: ignore[operator]


def test_openai_compatible_provider_sends_max_tokens_when_set(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_urlopen(request, timeout):
        captured['body'] = json.loads(request.data.decode('utf-8'))
        return FakeHTTPResponse({'choices': [{'message': {'content': 'ok'}}]})

    monkeypatch.setattr('free_plaud.providers.answer.urlopen', fake_urlopen)
    provider = OpenAICompatibleAnswerProvider(
        base_url='http://localhost:11434/v1',
        model='gemma4-cuda',
        max_tokens=256,
    )

    provider.answer('Pergunta?', ['[chunk] Evidencia.'])

    assert captured['body']['max_tokens'] == 256  # type: ignore[index]


def test_openai_compatible_provider_flags_reasoning_without_final_answer(monkeypatch) -> None:
    def fake_urlopen(request, timeout):
        return FakeHTTPResponse(
            {
                'choices': [
                    {
                        'message': {'content': '', 'reasoning': 'CADEIA_DE_PENSAMENTO_NAO_DEVE_VAZAR'},
                        'finish_reason': 'length',
                    }
                ]
            }
        )

    monkeypatch.setattr('free_plaud.providers.answer.urlopen', fake_urlopen)
    provider = OpenAICompatibleAnswerProvider(base_url='http://localhost:11434/v1', model='gemma4-cuda')

    with pytest.raises(AnswerProviderError) as excinfo:
        provider.answer('Pergunta?', ['[chunk] Evidencia.'])

    message = str(excinfo.value)
    assert message == REASONING_EMPTY_ANSWER_ERROR
    assert 'reasoning' in message
    assert 'answer_max_tokens' in message
    assert 'instruct' in message
    # O chain-of-thought nunca pode vazar como resposta.
    assert 'CADEIA_DE_PENSAMENTO_NAO_DEVE_VAZAR' not in message


def test_openai_compatible_provider_treats_null_content_with_reasoning_as_empty(monkeypatch) -> None:
    def fake_urlopen(request, timeout):
        return FakeHTTPResponse(
            {'choices': [{'message': {'content': None, 'reasoning_content': 'pensando...'}}]}
        )

    monkeypatch.setattr('free_plaud.providers.answer.urlopen', fake_urlopen)
    provider = OpenAICompatibleAnswerProvider(base_url='http://localhost:11434/v1', model='gemma-pt')

    with pytest.raises(AnswerProviderError, match='reasoning'):
        provider.answer('Pergunta?', ['[chunk] Evidencia.'])


def test_openai_compatible_provider_flags_length_truncation_without_reasoning(monkeypatch) -> None:
    def fake_urlopen(request, timeout):
        return FakeHTTPResponse({'choices': [{'message': {'content': ''}, 'finish_reason': 'length'}]})

    monkeypatch.setattr('free_plaud.providers.answer.urlopen', fake_urlopen)
    provider = OpenAICompatibleAnswerProvider(base_url='http://localhost:11434/v1', model='gemma4-cuda')

    with pytest.raises(AnswerProviderError) as excinfo:
        provider.answer('Pergunta?', ['[chunk] Evidencia.'])

    assert str(excinfo.value) == REASONING_EMPTY_ANSWER_ERROR


def test_openai_compatible_provider_keeps_generic_empty_error_without_reasoning(monkeypatch) -> None:
    def fake_urlopen(request, timeout):
        return FakeHTTPResponse({'choices': [{'message': {'content': '   '}, 'finish_reason': 'stop'}]})

    monkeypatch.setattr('free_plaud.providers.answer.urlopen', fake_urlopen)
    provider = OpenAICompatibleAnswerProvider(base_url='http://localhost:11434/v1', model='llama3.1:8b')

    with pytest.raises(AnswerProviderError) as excinfo:
        provider.answer('Pergunta?', ['[chunk] Evidencia.'])

    assert str(excinfo.value) == EMPTY_ANSWER_ERROR


def _settings(tmp_path: Path, **overrides) -> Settings:
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

    def fake_urlopen(request, timeout):
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
    def fake_urlopen(request, timeout):
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
    def fake_urlopen(request, timeout):
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
    def fake_urlopen(request, timeout):
        raise ValueError('unknown url type: localhost')

    monkeypatch.setattr('free_plaud.providers.answer.urlopen', fake_urlopen)

    result = run_answer_provider_test(_settings(tmp_path))

    assert result.status == 'error'
    assert result.error == 'Provider base_url invalida. Use http:// ou https://.'


def test_provider_test_accepts_non_empty_model_response(monkeypatch, tmp_path: Path) -> None:
    def fake_urlopen(request, timeout):
        return FakeHTTPResponse({'choices': [{'message': {'content': 'servico pronto'}}]})

    monkeypatch.setattr('free_plaud.providers.answer.urlopen', fake_urlopen)

    result = run_answer_provider_test(_settings(tmp_path))

    assert result.status == 'ok'
    assert result.error is None


def test_provider_test_rejects_empty_content(monkeypatch, tmp_path: Path) -> None:
    def fake_urlopen(request, timeout):
        return FakeHTTPResponse({'choices': [{'message': {'content': '   '}}]})

    monkeypatch.setattr('free_plaud.providers.answer.urlopen', fake_urlopen)

    result = run_answer_provider_test(_settings(tmp_path))

    assert result.status == 'error'
    assert result.error == 'Provider retornou resposta vazia.'


def test_provider_test_rejects_invalid_payload(monkeypatch, tmp_path: Path) -> None:
    def fake_urlopen(request, timeout):
        return FakeHTTPResponse({'choices': []})

    monkeypatch.setattr('free_plaud.providers.answer.urlopen', fake_urlopen)

    result = run_answer_provider_test(_settings(tmp_path))

    assert result.status == 'error'
    assert result.error == 'Provider retornou payload invalido.'


def test_provider_test_flags_reasoning_empty_answer(monkeypatch, tmp_path: Path) -> None:
    def fake_urlopen(request, timeout):
        return FakeHTTPResponse(
            {'choices': [{'message': {'content': '', 'reasoning': 'pensando...'}, 'finish_reason': 'length'}]}
        )

    monkeypatch.setattr('free_plaud.providers.answer.urlopen', fake_urlopen)

    result = run_answer_provider_test(_settings(tmp_path))

    assert result.status == 'error'
    assert result.error == REASONING_EMPTY_ANSWER_ERROR


def test_provider_test_sends_max_tokens_when_configured(monkeypatch, tmp_path: Path) -> None:
    captured: dict[str, object] = {}

    def fake_urlopen(request, timeout):
        captured['body'] = json.loads(request.data.decode('utf-8'))
        return FakeHTTPResponse({'choices': [{'message': {'content': 'ok'}}]})

    monkeypatch.setattr('free_plaud.providers.answer.urlopen', fake_urlopen)

    result = run_answer_provider_test(_settings(tmp_path, answer_max_tokens=1024))

    assert result.status == 'ok'
    assert captured['body']['max_tokens'] == 1024  # type: ignore[index]


def test_provider_test_extractive_is_not_applicable(tmp_path: Path) -> None:
    result = run_answer_provider_test(_settings(tmp_path, answer_provider='extractive'))

    assert result.status == 'not_applicable'
    assert result.provider == 'extractive'
    assert result.error is None


def test_provider_smoke_local_uses_temp_corpus_and_does_not_call_provider_for_missing_question(tmp_path: Path) -> None:
    provider = FakeSmokeAnswerProvider()
    result = run_provider_smoke_local(
        settings=_settings(tmp_path),
        strategy='lexical',
        top_k=4,
        answer_provider=provider,
        provider_test_result=AnswerProviderTestResult(
            provider='ollama',
            model='llama3.1:8b',
            base_url='http://localhost:11434/v1',
            status='ok',
            latency_ms=5,
            error=None,
        ),
    )

    assert result.status == 'ok'
    assert result.known_question.status == 'answer'
    assert 'Disco D' in (result.known_question.answer or '')
    assert result.known_question.citations_count >= 1
    assert result.missing_question.status == 'no_answer'
    assert provider.questions == ['O que e Estrutura Disco D?']
    assert result.workspace_dir is None
