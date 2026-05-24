import json
from io import BytesIO
from urllib.error import HTTPError

import pytest

from free_plaud.providers.answer import AnswerProviderError, OpenAICompatibleAnswerProvider, get_answer_provider


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
