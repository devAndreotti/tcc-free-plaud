import json
from dataclasses import dataclass
from time import perf_counter
from typing import Literal, Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from pydantic import BaseModel

from free_plaud.app.config import Settings, get_settings

AnswerProviderName = Literal['extractive', 'openai-compatible', 'ollama', 'lmstudio']
ProviderTestStatus = Literal['ok', 'error', 'not_applicable']
TEST_ANSWER_PROMPT = 'Responda somente: ok'
INVALID_BASE_URL_ERROR = 'Provider base_url invalida. Use http:// ou https://.'


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


@dataclass
class OpenAICompatibleAnswerProvider:
    base_url: str
    model: str
    api_key: str | None = None
    temperature: float = 0.2
    timeout_seconds: int = 60
    provider_name: str = 'openai-compatible'

    def answer(self, question: str, contexts: list[str]) -> str:
        if not contexts:
            raise ValueError('Provider de resposta exige pelo menos um contexto citavel.')
        if not _is_http_base_url(self.base_url):
            raise AnswerProviderError(INVALID_BASE_URL_ERROR)

        endpoint = f'{self.base_url.rstrip("/")}/chat/completions'
        messages = [
            {
                'role': 'system',
                'content': (
                    'Voce responde em portugues brasileiro usando somente os contextos fornecidos. '
                    'Nao invente fatos. Se a evidencia for insuficiente, diga que os dados recuperados nao sustentam resposta. '
                    'Seja direto, claro e preserve nomes tecnicos.'
                ),
            },
            {
                'role': 'user',
                'content': (
                    f'Pergunta:\n{question}\n\n'
                    'Contextos citaveis recuperados:\n'
                    + '\n\n'.join(contexts)
                    + '\n\nEscreva uma resposta final curta e bem estruturada.'
                ),
            },
        ]
        payload = {
            'model': self.model,
            'messages': messages,
            'temperature': self.temperature,
        }
        headers = {'Content-Type': 'application/json'}
        if self.api_key:
            headers['Authorization'] = f'Bearer {self.api_key}'

        request = Request(
            endpoint,
            data=json.dumps(payload).encode('utf-8'),
            headers=headers,
            method='POST',
        )
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                body = response.read()
        except HTTPError as exc:
            error_body = exc.read().decode('utf-8', errors='replace')
            raise AnswerProviderError(f'Provider respondeu HTTP {exc.code}: {error_body}') from exc
        except URLError as exc:
            raise AnswerProviderError(f'Provider indisponivel: {exc.reason}') from exc
        except TimeoutError as exc:
            raise AnswerProviderError('Provider excedeu timeout.') from exc
        except ValueError as exc:
            raise AnswerProviderError(INVALID_BASE_URL_ERROR) from exc

        try:
            decoded = json.loads(body.decode('utf-8'))
            content = decoded['choices'][0]['message']['content']
        except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
            raise AnswerProviderError('Provider retornou payload invalido.') from exc

        answer = str(content).strip()
        if not answer:
            raise AnswerProviderError('Provider retornou resposta vazia.')
        return answer


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
    timeout_seconds: int = 60,
) -> AnswerProvider | None:
    if provider_name == 'extractive':
        return None
    return OpenAICompatibleAnswerProvider(
        base_url=_default_base_url(provider_name, base_url),
        model=model,
        api_key=api_key,
        temperature=temperature,
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
    payload = {
        'model': resolved.answer_model,
        'messages': [{'role': 'user', 'content': TEST_ANSWER_PROMPT}],
        'temperature': 0,
    }
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
        content = str(decoded['choices'][0]['message']['content']).strip()
    except (KeyError, IndexError, TypeError, json.JSONDecodeError):
        return result('error', 'Provider retornou payload invalido.')

    if not content:
        return result('error', 'Provider retornou resposta vazia.')
    return result('ok')
