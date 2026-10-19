"""Leitura incremental (SSE) da resposta de chat/completions com stream=True.

Importado só de dentro de OpenAICompatibleAnswerProvider.answer_stream: este módulo
importa os erros de answer.py, e answer.py não pode importá-lo no topo (ciclo).
"""

import json
from collections.abc import Callable, Iterable

from escolio.providers.answer import (
    REASONING_KEYS,
    AnswerProviderError,
    _empty_answer_error_message,
)


def _delta_of(data: str) -> tuple[dict[str, object], object]:
    """(delta, finish_reason) de um chunk; formato inesperado vira erro de payload."""
    try:
        choice = json.loads(data)['choices'][0]
        delta = choice.get('delta') or {}
        if not isinstance(delta, dict):
            raise TypeError('delta do provider não é um objeto')
        return delta, choice.get('finish_reason')
    except (AttributeError, IndexError, KeyError, TypeError, ValueError) as exc:
        raise AnswerProviderError('Provider retornou payload invalido.') from exc


def read_sse_answer(lines: Iterable[bytes], on_delta: Callable[[str], None]) -> str:
    """Monta o texto do stream e repassa cada pedaço não vazio a on_delta, na ordem.

    Raciocínio (reasoning/reasoning_content) não entra no texto nem em on_delta: só escolhe
    a mensagem de erro quando nenhuma resposta final chega.
    """
    parts: list[str] = []
    reasoning: list[str] = []
    finish_reason: object = None
    for raw in lines:
        line = raw.decode('utf-8', errors='replace').strip()
        if not line.startswith('data:'):
            continue
        data = line.removeprefix('data:').strip()
        if data == '[DONE]':
            break
        delta, reason = _delta_of(data)
        finish_reason = reason or finish_reason
        for key in REASONING_KEYS:
            value = delta.get(key)
            if isinstance(value, str):
                reasoning.append(value)
        content = delta.get('content')
        if isinstance(content, str) and content:
            parts.append(content)
            on_delta(content)
    text = ''.join(parts).strip()
    if not text:
        raise AnswerProviderError(_empty_answer_error_message({'reasoning': ''.join(reasoning)}, finish_reason))
    return text
