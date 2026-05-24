import json
from dataclasses import dataclass
from typing import Literal, Protocol
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

AnswerProviderName = Literal['extractive', 'openai-compatible', 'ollama', 'lmstudio']


class AnswerProviderError(RuntimeError):
    """Falha operacional do provider de resposta generativa."""


class AnswerProvider(Protocol):
    provider_name: str

    def answer(self, question: str, contexts: list[str]) -> str:
        """Gera resposta a partir de contextos citaveis ja recuperados."""


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
