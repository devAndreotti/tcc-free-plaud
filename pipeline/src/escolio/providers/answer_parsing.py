EMPTY_ANSWER_ERROR = 'Provider retornou resposta vazia.'
REASONING_EMPTY_ANSWER_ERROR = (
    'Provider gerou apenas raciocinio (reasoning) sem resposta final. '
    'Modelos de reasoning gastam tokens pensando antes de responder: '
    'aumente answer_timeout_seconds, suba answer_max_tokens, ou use um modelo instruct.'
)
REASONING_KEYS = ('reasoning', 'reasoning_content')

class AnswerProviderError(RuntimeError):
    """Falha operacional do provider de resposta generativa."""


def _reasoning_text(message: dict[str, object]) -> str:
    """Texto de chain-of-thought emitido por modelos de reasoning, se houver."""
    for key in REASONING_KEYS:
        value = message.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ''


def extract_answer_text(decoded: object) -> tuple[str, dict[str, object], object]:
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
