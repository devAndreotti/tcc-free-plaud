import json
from collections.abc import Callable
from dataclasses import dataclass
from time import perf_counter
from typing import Literal, Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from pydantic import BaseModel

from escolio.app.config import Settings, get_settings

AnswerProviderName = Literal['extractive', 'openai-compatible', 'ollama', 'lmstudio']
ProviderTestStatus = Literal['ok', 'error', 'not_applicable']
TEST_ANSWER_PROMPT = 'Responda somente: ok'
INVALID_BASE_URL_ERROR = 'Provider base_url invalida. Use http:// ou https://.'
NO_ANSWER_SENTINEL = 'NAO_ENCONTRADO: os dados recuperados nao sustentam resposta.'
EMPTY_ANSWER_ERROR = 'Provider retornou resposta vazia.'
REASONING_EMPTY_ANSWER_ERROR = (
    'Provider gerou apenas raciocinio (reasoning) sem resposta final. '
    'Modelos de reasoning gastam tokens pensando antes de responder: '
    'aumente answer_timeout_seconds, suba answer_max_tokens, ou use um modelo instruct.'
)
REASONING_KEYS = ('reasoning', 'reasoning_content')
GROUNDED_SYSTEM_PROMPT = (
    'Voce deve responder em portugues brasileiro usando exclusivamente os CONTEXTOS. '
    'Nao use conhecimento externo. Nao complete lacunas. '
    'Nao crie exemplos, listas ou explicacoes que nao estejam nos CONTEXTOS. '
    'Se os CONTEXTOS nao responderem diretamente a PERGUNTA, responda exatamente: '
    f'{NO_ANSWER_SENTINEL} '
    'Responda a PERGUNTA em frases completas, com suas proprias palavras. Termine cada frase com o numero do CONTEXTO que a sustenta entre colchetes, e use mais de um CONTEXTO quando a PERGUNTA pedir mais de um assunto (uma frase por assunto), '
    'por exemplo: O VLAN separa dominios de broadcast [1]. Nunca copie titulos, nomes de nota ou linhas de cabecalho. Nunca responda so com colchetes. '
    'Preserve numeros, nomes e termos tecnicos exatamente como aparecem.'
)


class AnswerProviderError(RuntimeError):
    """Falha operacional do provider de resposta generativa."""


class AnswerProviderTestResult(BaseModel):
    provider: str
    model: str
    base_url: str | None
    status: ProviderTestStatus
    latency_ms: int
    error: str | None = None


class AnswerProvider(Protocol):
    provider_name: str

    def answer(self, question: str, contexts: list[str]) -> str:
        """Gera resposta a partir de contextos citaveis ja recuperados."""


def _is_http_base_url(value: str) -> bool:
    try:
        parsed = urlparse(value)
    except ValueError:
        return False
    return parsed.scheme in {'http', 'https'} and bool(parsed.netloc)


def build_grounded_chat_messages(question: str, contexts: list[str]) -> list[dict[str, str]]:
    return [
        {
            'role': 'system',
            'content': GROUNDED_SYSTEM_PROMPT,
        },
        {
            'role': 'user',
            'content': (
                f'PERGUNTA:\n{question}\n\n'
                'CONTEXTOS:\n'
                + '\n\n'.join(contexts)
                + "\n\nResponda curto e direto usando somente os CONTEXTOS. Lembrete: fale com quem pergunta usando voce (ex.: 'Voce estudou redes [1].'). Nao use eu nem verbos em primeira pessoa."
            ),
        },
    ]


def _reasoning_text(message: dict[str, object]) -> str:
    """Texto de chain-of-thought emitido por modelos de reasoning, se houver."""
    for key in REASONING_KEYS:
        value = message.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ''


def _extract_answer_text(decoded: object) -> tuple[str, dict[str, object], object]:
    """Extrai (content normalizado, message, finish_reason) de um payload chat/completions.

    Levanta KeyError/IndexError/TypeError quando o payload nao tem o formato esperado,
    para o chamador traduzir em 'payload invalido'. Trata content ausente ou null como
    string vazia (modelos de reasoning costumam emitir content=null).
    """
    choice = decoded['choices'][0]  # type: ignore[index]
    message = choice['message']
    if not isinstance(message, dict):
        raise TypeError('message do provider nao e um objeto')
    content = message.get('content')
    text = content.strip() if isinstance(content, str) else ''
    finish_reason = choice.get('finish_reason') if isinstance(choice, dict) else None
    return text, message, finish_reason


def _empty_answer_error_message(message: dict[str, object], finish_reason: object) -> str:
    """Mensagem acionavel quando content vem vazio.

    Distingue o modelo de reasoning (so emitiu raciocinio, ou truncou em
    finish_reason='length') do vazio puro. NUNCA usa o texto de reasoning como resposta:
    ele e chain-of-thought, nao a resposta fundamentada nos contextos.
    """
    if _reasoning_text(message) or finish_reason == 'length':
        return REASONING_EMPTY_ANSWER_ERROR
    return EMPTY_ANSWER_ERROR


def _transport_error(exc: Exception) -> AnswerProviderError:
    if isinstance(exc, HTTPError):
        return AnswerProviderError(f'Provider respondeu HTTP {exc.code}.')
    if isinstance(exc, URLError):
        return AnswerProviderError(f'Provider indisponivel: {exc.reason}')
    if isinstance(exc, TimeoutError):
        return AnswerProviderError('Provider excedeu timeout.')
    return AnswerProviderError(INVALID_BASE_URL_ERROR)


@dataclass
class OpenAICompatibleAnswerProvider:
    base_url: str
    model: str
    api_key: str | None = None
    temperature: float = 0.2
    max_tokens: int | None = None
    timeout_seconds: int = 60
    provider_name: str = 'openai-compatible'

    def _chat_request(self, question: str, contexts: list[str], *, stream: bool = False) -> Request:
        if not contexts:
            raise ValueError('Provider de resposta exige pelo menos um contexto citavel.')
        return self._messages_request(build_grounded_chat_messages(question, contexts), stream=stream)

    def _messages_request(
        self,
        messages: list[dict[str, str]],
        *,
        stream: bool = False,
        temperature: float | None = None,
    ) -> Request:
        if not _is_http_base_url(self.base_url):
            raise AnswerProviderError(INVALID_BASE_URL_ERROR)

        payload: dict[str, object] = {
            'model': self.model,
            'messages': messages,
            'temperature': self.temperature if temperature is None else temperature,
        }
        if stream:
            payload['stream'] = True
        if self.max_tokens is not None:
            payload['max_tokens'] = self.max_tokens
        headers = {'Content-Type': 'application/json'}
        if self.api_key:
            headers['Authorization'] = f'Bearer {self.api_key}'
        endpoint = f'{self.base_url.rstrip("/")}/chat/completions'
        return Request(endpoint, data=json.dumps(payload).encode('utf-8'), headers=headers, method='POST')

    def complete(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: float | None = None,
    ) -> str:
        """Chamada chat/completions genérica (sem prompt de resposta fundamentada).

        Usada por tarefas auxiliares, como a extração estruturada de notas, para
        reaproveitar o mesmo endpoint, chave e timeout do provider de resposta.
        """
        request = self._messages_request(messages, temperature=temperature)
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                body = response.read()
        except (URLError, TimeoutError, ValueError) as exc:
            raise _transport_error(exc) from exc

        try:
            decoded = json.loads(body.decode('utf-8'))
            answer, message, finish_reason = _extract_answer_text(decoded)
        except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
            raise AnswerProviderError('Provider retornou payload invalido.') from exc

        if not answer:
            raise AnswerProviderError(_empty_answer_error_message(message, finish_reason))
        return answer

    def answer(self, question: str, contexts: list[str]) -> str:
        if not contexts:
            raise ValueError('Provider de resposta exige pelo menos um contexto citavel.')
        return self.complete(build_grounded_chat_messages(question, contexts))

    def answer_stream(self, question: str, contexts: list[str], on_delta: Callable[[str], None]) -> str:
        from escolio.providers.answer_stream import read_sse_answer  # evita ciclo

        request = self._chat_request(question, contexts, stream=True)
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                return read_sse_answer(response, on_delta)
        except (URLError, TimeoutError) as exc:
            raise _transport_error(exc) from exc


def _default_base_url(provider_name: AnswerProviderName, base_url: str | None) -> str:
    if base_url:
        return base_url
    if provider_name == 'ollama':
        return 'http://localhost:11434/v1'
    if provider_name == 'lmstudio':
        return 'http://localhost:1234/v1'
    return 'https://api.openai.com/v1'


def get_answer_provider(
    provider_name: AnswerProviderName,
    *,
    model: str,
    base_url: str | None = None,
    api_key: str | None = None,
    temperature: float = 0.2,
    max_tokens: int | None = None,
    timeout_seconds: int = 60,
) -> AnswerProvider | None:
    if provider_name == 'extractive':
        return None
    return OpenAICompatibleAnswerProvider(
        base_url=_default_base_url(provider_name, base_url),
        model=model,
        api_key=api_key,
        temperature=temperature,
        max_tokens=max_tokens,
        timeout_seconds=timeout_seconds,
        provider_name=provider_name,
    )


def test_answer_provider(settings: Settings | None = None) -> AnswerProviderTestResult:
    resolved = settings or get_settings()
    started_at = perf_counter()
    if resolved.answer_provider == 'extractive':
        return AnswerProviderTestResult(
            provider=resolved.answer_provider,
            model=resolved.answer_model,
            base_url=resolved.answer_base_url,
            status='not_applicable',
            latency_ms=0,
            error=None,
        )

    base_url = _default_base_url(resolved.answer_provider, resolved.answer_base_url)
    if not _is_http_base_url(base_url):
        return AnswerProviderTestResult(
            provider=resolved.answer_provider,
            model=resolved.answer_model,
            base_url=base_url,
            status='error',
            latency_ms=0,
            error=INVALID_BASE_URL_ERROR,
        )
    endpoint = f'{base_url.rstrip("/")}/chat/completions'
    payload: dict[str, object] = {
        'model': resolved.answer_model,
        'messages': [{'role': 'user', 'content': TEST_ANSWER_PROMPT}],
        'temperature': 0,
    }
    if resolved.answer_max_tokens is not None:
        payload['max_tokens'] = resolved.answer_max_tokens
    headers = {'Content-Type': 'application/json'}
    if resolved.answer_api_key:
        headers['Authorization'] = f'Bearer {resolved.answer_api_key}'

    request = Request(
        endpoint,
        data=json.dumps(payload).encode('utf-8'),
        headers=headers,
        method='POST',
    )

    def result(status: ProviderTestStatus, error: str | None = None) -> AnswerProviderTestResult:
        latency_ms = int((perf_counter() - started_at) * 1000)
        return AnswerProviderTestResult(
            provider=resolved.answer_provider,
            model=resolved.answer_model,
            base_url=base_url,
            status=status,
            latency_ms=latency_ms,
            error=error,
        )

    try:
        with urlopen(request, timeout=resolved.answer_timeout_seconds) as response:
            body = response.read()
    except HTTPError as exc:
        return result('error', f'HTTP {exc.code}: {exc.msg}')
    except URLError as exc:
        return result('error', f'Provider indisponivel: {exc.reason}')
    except TimeoutError:
        return result('error', 'Provider excedeu timeout.')
    except ValueError:
        return result('error', INVALID_BASE_URL_ERROR)

    try:
        decoded = json.loads(body.decode('utf-8'))
        content, message, finish_reason = _extract_answer_text(decoded)
    except (KeyError, IndexError, TypeError, json.JSONDecodeError):
        return result('error', 'Provider retornou payload invalido.')

    if not content:
        return result('error', _empty_answer_error_message(message, finish_reason))
    return result('ok')
