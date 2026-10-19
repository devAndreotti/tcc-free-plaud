"""Pré-carregamento do modelo de resposta no Ollama: a primeira pergunta não paga o carregamento."""

import json
import logging
from urllib.request import Request, urlopen

from escolio.app.config import Settings
from escolio.providers.answer import _default_base_url
from escolio.providers.model_discovery import _strip_v1_path

logger = logging.getLogger(__name__)


def warm_up_answer_model(settings: Settings) -> bool:
    """POST /api/generate sem prompt: o Ollama carrega o modelo na VRAM. True só com HTTP 200."""
    if settings.answer_provider != 'ollama':
        return False
    root = _strip_v1_path(_default_base_url('ollama', settings.answer_base_url))
    request = Request(
        f'{root}/api/generate',
        data=json.dumps({'model': settings.answer_model}).encode('utf-8'),
        headers={'Content-Type': 'application/json'},
        method='POST',
    )
    try:
        with urlopen(request, timeout=settings.answer_timeout_seconds) as response:
            return response.status == 200
    except Exception as exc:  # aquecer é otimização: a falha só vai para o log
        logger.warning('Aquecimento do modelo de resposta falhou: %s', exc)
        return False
