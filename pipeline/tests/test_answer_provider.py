import json
from io import BytesIO
from pathlib import Path
from typing import Self
from urllib.error import HTTPError, URLError

import pytest

from escolio.app.config import Settings
from escolio.providers.answer import (
    EMPTY_ANSWER_ERROR,
    REASONING_EMPTY_ANSWER_ERROR,
    AnswerProviderError,
    AnswerProviderTestResult,
    OpenAICompatibleAnswerProvider,
    build_grounded_chat_messages,
    get_answer_provider,
)
from escolio.providers.answer import (
    test_answer_provider as run_answer_provider_test,
)
from escolio.providers.answer_warmup import warm_up_answer_model
from escolio.providers.smoke import run_provider_smoke_local


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

    monkeypatch.setattr('escolio.providers.answer.urlopen', fake_urlopen)

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
    assert 'Responda a PERGUNTA em frases completas' in system_prompt
    assert 'use mais de um CONTEXTO' in system_prompt
    assert 'Nunca responda so com colchetes' in system_prompt
    assert 'Preserve numeros, nomes e termos tecnicos exatamente' in system_prompt
    assert 'seja criativo' not in system_prompt.lower()
    assert 'PERGUNTA:\nQual broker?' in user_prompt
    assert 'CONTEXTOS:\n[1]' in user_prompt


def test_grounded_user_message_asks_second_person_and_forbids_first_person() -> None:
    messages = build_grounded_chat_messages(
        'O que estudei na Cisco?',
        ['[1]\nsource_path: note.md\nchunk_id: c1\ntrecho:\nEstudei redes e seguranca de perimetro.'],
    )

    user_prompt = messages[1]['content']
    assert 'fale com quem pergunta usando voce' in user_prompt
    assert 'Nao use eu nem verbos em primeira pessoa' in user_prompt


def test_openai_compatible_provider_wraps_http_errors(monkeypatch) -> None:
    def fake_urlopen(request, timeout):
        raise HTTPError(
            url=request.full_url,
            code=401,
            msg='Unauthorized',
            hdrs=None,
            fp=BytesIO(b'{"error":"bad key"}'),
        )

    monkeypatch.setattr('escolio.providers.answer.urlopen', fake_urlopen)
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

    monkeypatch.setattr('escolio.providers.answer.urlopen', fake_urlopen)
    provider = OpenAICompatibleAnswerProvider(base_url='http://localhost:11434/v1', model='gemma4-cuda')

    provider.answer('Pergunta?', ['[chunk] Evidencia.'])

    assert 'max_tokens' not in captured['body']  # type: ignore[operator]


def test_openai_compatible_provider_sends_max_tokens_when_set(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_urlopen(request, timeout):
        captured['body'] = json.loads(request.data.decode('utf-8'))
        return FakeHTTPResponse({'choices': [{'message': {'content': 'ok'}}]})

    monkeypatch.setattr('escolio.providers.answer.urlopen', fake_urlopen)
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

    monkeypatch.setattr('escolio.providers.answer.urlopen', fake_urlopen)
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

    monkeypatch.setattr('escolio.providers.answer.urlopen', fake_urlopen)
    provider = OpenAICompatibleAnswerProvider(base_url='http://localhost:11434/v1', model='gemma-pt')

    with pytest.raises(AnswerProviderError, match='reasoning'):
        provider.answer('Pergunta?', ['[chunk] Evidencia.'])


def test_openai_compatible_provider_flags_length_truncation_without_reasoning(monkeypatch) -> None:
    def fake_urlopen(request, timeout):
        return FakeHTTPResponse({'choices': [{'message': {'content': ''}, 'finish_reason': 'length'}]})

    monkeypatch.setattr('escolio.providers.answer.urlopen', fake_urlopen)
    provider = OpenAICompatibleAnswerProvider(base_url='http://localhost:11434/v1', model='gemma4-cuda')

    with pytest.raises(AnswerProviderError) as excinfo:
        provider.answer('Pergunta?', ['[chunk] Evidencia.'])

    assert str(excinfo.value) == REASONING_EMPTY_ANSWER_ERROR


def test_openai_compatible_provider_keeps_generic_empty_error_without_reasoning(monkeypatch) -> None:
    def fake_urlopen(request, timeout):
        return FakeHTTPResponse({'choices': [{'message': {'content': '   '}, 'finish_reason': 'stop'}]})

    monkeypatch.setattr('escolio.providers.answer.urlopen', fake_urlopen)
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
        'sqlite_path': tmp_path / 'data' / 'results' / 'escolio.sqlite3',
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

    monkeypatch.setattr('escolio.providers.answer.urlopen', fake_urlopen)

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

    monkeypatch.setattr('escolio.providers.answer.urlopen', fake_urlopen)

    result = run_answer_provider_test(_settings(tmp_path, answer_api_key='sk-secret'))

    assert result.status == 'error'
    assert result.error == 'HTTP 401: Unauthorized'
    assert 'sk-secret' not in result.model_dump_json()


def test_provider_test_timeout_returns_controlled_error(monkeypatch, tmp_path: Path) -> None:
    def fake_urlopen(request, timeout):
        raise TimeoutError

    monkeypatch.setattr('escolio.providers.answer.urlopen', fake_urlopen)

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

    monkeypatch.setattr('escolio.providers.answer.urlopen', fake_urlopen)

    result = run_answer_provider_test(_settings(tmp_path))

    assert result.status == 'error'
    assert result.error == 'Provider base_url invalida. Use http:// ou https://.'


def test_provider_test_accepts_non_empty_model_response(monkeypatch, tmp_path: Path) -> None:
    def fake_urlopen(request, timeout):
        return FakeHTTPResponse({'choices': [{'message': {'content': 'servico pronto'}}]})

    monkeypatch.setattr('escolio.providers.answer.urlopen', fake_urlopen)

    result = run_answer_provider_test(_settings(tmp_path))

    assert result.status == 'ok'
    assert result.error is None


def test_provider_test_rejects_empty_content(monkeypatch, tmp_path: Path) -> None:
    def fake_urlopen(request, timeout):
        return FakeHTTPResponse({'choices': [{'message': {'content': '   '}}]})

    monkeypatch.setattr('escolio.providers.answer.urlopen', fake_urlopen)

    result = run_answer_provider_test(_settings(tmp_path))

    assert result.status == 'error'
    assert result.error == 'Provider retornou resposta vazia.'


def test_provider_test_rejects_invalid_payload(monkeypatch, tmp_path: Path) -> None:
    def fake_urlopen(request, timeout):
        return FakeHTTPResponse({'choices': []})

    monkeypatch.setattr('escolio.providers.answer.urlopen', fake_urlopen)

    result = run_answer_provider_test(_settings(tmp_path))

    assert result.status == 'error'
    assert result.error == 'Provider retornou payload invalido.'


def test_provider_test_flags_reasoning_empty_answer(monkeypatch, tmp_path: Path) -> None:
    def fake_urlopen(request, timeout):
        return FakeHTTPResponse(
            {'choices': [{'message': {'content': '', 'reasoning': 'pensando...'}, 'finish_reason': 'length'}]}
        )

    monkeypatch.setattr('escolio.providers.answer.urlopen', fake_urlopen)

    result = run_answer_provider_test(_settings(tmp_path))

    assert result.status == 'error'
    assert result.error == REASONING_EMPTY_ANSWER_ERROR


def test_provider_test_sends_max_tokens_when_configured(monkeypatch, tmp_path: Path) -> None:
    captured: dict[str, object] = {}

    def fake_urlopen(request, timeout):
        captured['body'] = json.loads(request.data.decode('utf-8'))
        return FakeHTTPResponse({'choices': [{'message': {'content': 'ok'}}]})

    monkeypatch.setattr('escolio.providers.answer.urlopen', fake_urlopen)

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


class FakeStreamResponse:
    """Stream SSE falso: itera linhas em bytes, como o HTTPResponse do urllib."""

    def __init__(self, lines: list[bytes], fail_after: Exception | None = None) -> None:
        self.lines = lines
        self.fail_after = fail_after

    def __enter__(self) -> Self:
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        return None

    def __iter__(self):
        yield from self.lines
        if self.fail_after is not None:
            raise self.fail_after


class FakeStatusResponse:
    def __init__(self, status: int) -> None:
        self.status = status

    def __enter__(self) -> Self:
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        return None


def _sse_chunk(delta: dict[str, object], finish_reason: str | None = None) -> bytes:
    event = {'choices': [{'delta': delta, 'finish_reason': finish_reason}]}
    return f'data: {json.dumps(event)}\n'.encode()


def _stream_provider(
    monkeypatch, lines: list[bytes], captured: dict[str, object] | None = None
) -> OpenAICompatibleAnswerProvider:
    def fake_urlopen(request, timeout):
        if captured is not None:
            captured['url'] = request.full_url
            captured['body'] = json.loads(request.data.decode('utf-8'))
        return FakeStreamResponse(lines)

    monkeypatch.setattr('escolio.providers.answer.urlopen', fake_urlopen)
    return OpenAICompatibleAnswerProvider(base_url='http://localhost:11434/v1', model='llama3.1:8b', max_tokens=64)


def test_answer_stream_monta_texto_e_repassa_pedacos_em_ordem(monkeypatch) -> None:
    captured: dict[str, object] = {}
    provider = _stream_provider(
        monkeypatch,
        [
            _sse_chunk({'role': 'assistant'}),
            _sse_chunk({'reasoning_content': 'pensando antes de responder'}),
            _sse_chunk({'content': 'Resposta '}),
            b'\n',
            _sse_chunk({'content': 'curta.'}, 'stop'),
            b'data: [DONE]\n',
            _sse_chunk({'content': ' depois do DONE não conta'}),
        ],
        captured,
    )
    pieces: list[str] = []

    answer = provider.answer_stream('Qual broker?', ['[chunk-1] RabbitMQ foi adotado.'], pieces.append)

    assert answer == 'Resposta curta.'
    assert pieces == ['Resposta ', 'curta.']
    assert captured['url'] == 'http://localhost:11434/v1/chat/completions'
    assert captured['body']['stream'] is True  # type: ignore[index]
    assert captured['body']['max_tokens'] == 64  # type: ignore[index]


def test_answer_stream_so_raciocinio_vira_erro_de_reasoning(monkeypatch) -> None:
    provider = _stream_provider(
        monkeypatch,
        [_sse_chunk({'reasoning': 'CADEIA_DE_PENSAMENTO'}), _sse_chunk({}, 'length'), b'data: [DONE]\n'],
    )
    pieces: list[str] = []

    with pytest.raises(AnswerProviderError) as excinfo:
        provider.answer_stream('Qual broker?', ['[chunk] Evidencia.'], pieces.append)

    assert str(excinfo.value) == REASONING_EMPTY_ANSWER_ERROR
    assert pieces == []


def test_answer_stream_sem_texto_nem_raciocinio_vira_resposta_vazia(monkeypatch) -> None:
    provider = _stream_provider(monkeypatch, [_sse_chunk({'role': 'assistant'}, 'stop'), b'data: [DONE]\n'])

    with pytest.raises(AnswerProviderError) as excinfo:
        provider.answer_stream('Qual broker?', ['[chunk] Evidencia.'], lambda piece: None)

    assert str(excinfo.value) == EMPTY_ANSWER_ERROR


def test_answer_stream_payload_invalido_vira_erro_de_formato(monkeypatch) -> None:
    provider = _stream_provider(monkeypatch, [b'data: {nao e json\n'])

    with pytest.raises(AnswerProviderError, match='payload invalido'):
        provider.answer_stream('Qual broker?', ['[chunk] Evidencia.'], lambda piece: None)


def test_answer_stream_timeout_no_meio_do_stream_mantem_pedacos_recebidos(monkeypatch) -> None:
    def fake_urlopen(request, timeout):
        return FakeStreamResponse([_sse_chunk({'content': 'Parcial'})], fail_after=TimeoutError('timed out'))

    monkeypatch.setattr('escolio.providers.answer.urlopen', fake_urlopen)
    provider = OpenAICompatibleAnswerProvider(base_url='http://localhost:11434/v1', model='llama3.1:8b')
    pieces: list[str] = []

    with pytest.raises(AnswerProviderError, match='timeout'):
        provider.answer_stream('Qual broker?', ['[chunk] Evidencia.'], pieces.append)

    assert pieces == ['Parcial']


def test_answer_stream_http_error_usa_a_mesma_mensagem_de_answer(monkeypatch) -> None:
    def fake_urlopen(request, timeout):
        raise HTTPError(
            url=request.full_url,
            code=401,
            msg='Unauthorized',
            hdrs=None,
            fp=BytesIO(b'{"error":"bad key"}'),
        )

    monkeypatch.setattr('escolio.providers.answer.urlopen', fake_urlopen)
    provider = OpenAICompatibleAnswerProvider(base_url='https://api.example/v1', model='model')

    with pytest.raises(AnswerProviderError, match='401'):
        provider.answer_stream('Pergunta?', ['[chunk] Evidencia.'], lambda piece: None)


def test_answer_stream_erro_do_callback_nao_vira_erro_do_provider(monkeypatch) -> None:
    provider = _stream_provider(monkeypatch, [_sse_chunk({'content': 'Texto'})])

    def quebra(piece: str) -> None:
        raise ValueError('callback quebrou')

    with pytest.raises(ValueError, match='callback quebrou'):
        provider.answer_stream('Qual broker?', ['[chunk] Evidencia.'], quebra)


def test_warm_up_answer_model_posta_api_generate_na_raiz_do_ollama(monkeypatch, tmp_path: Path) -> None:
    captured: dict[str, object] = {}

    def fake_urlopen(request, timeout):
        captured['url'] = request.full_url
        captured['timeout'] = timeout
        captured['body'] = json.loads(request.data.decode('utf-8'))
        return FakeStatusResponse(200)

    monkeypatch.setattr('escolio.providers.answer_warmup.urlopen', fake_urlopen)

    assert warm_up_answer_model(_settings(tmp_path)) is True
    assert captured['url'] == 'http://localhost:11434/api/generate'
    assert captured['body'] == {'model': 'llama3.1:8b'}
    assert captured['timeout'] == 12


def test_warm_up_answer_model_so_age_com_ollama_e_engole_falhas(monkeypatch, tmp_path: Path) -> None:
    def sem_rede(request, timeout):
        raise AssertionError('fora do ollama não pode haver chamada de rede')

    monkeypatch.setattr('escolio.providers.answer_warmup.urlopen', sem_rede)
    assert warm_up_answer_model(_settings(tmp_path, answer_provider='lmstudio')) is False
    assert warm_up_answer_model(_settings(tmp_path, answer_provider='extractive')) is False

    def offline(request, timeout):
        raise URLError('connection refused')

    monkeypatch.setattr('escolio.providers.answer_warmup.urlopen', offline)
    assert warm_up_answer_model(_settings(tmp_path)) is False
