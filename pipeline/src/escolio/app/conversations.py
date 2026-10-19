"""Conversas do chat salvas entre aberturas do app.

Ficam em `results_dir/conversations.json`. O PyWebView abre com private_mode, então o localStorage
some a cada abertura e a persistência precisa estar no backend. O arquivo é global (não por vault).
"""

from __future__ import annotations

import json
import logging
import os
import threading
from pathlib import Path
from typing import Any

from escolio.app.config import Settings, get_settings

CONVERSATIONS_FILENAME = 'conversations.json'
MAX_CONVERSATIONS_BYTES = 5 * 1024 * 1024

logger = logging.getLogger('escolio.app')
# Dois salvamentos ao mesmo tempo dividiriam o mesmo .tmp: o lock põe um depois do outro.
_write_lock = threading.Lock()


def _path(settings: Settings | None) -> Path:
    return (settings or get_settings()).results_dir / CONVERSATIONS_FILENAME


def _check_shape(payload: Any) -> None:
    """Fronteira de confiança: o que chega do front é conferido antes de ir para o disco."""
    if not isinstance(payload, dict):
        raise ValueError('Conversas precisam ser um objeto JSON.')
    if not isinstance(payload.get('tabs'), list):
        raise ValueError('Conversas: "tabs" precisa ser uma lista.')
    if 'activeTabId' not in payload or (payload['activeTabId'] is not None and not isinstance(payload['activeTabId'], str)):
        raise ValueError('Conversas: "activeTabId" precisa ser texto ou null.')
    if not isinstance(payload.get('tabMessages'), dict):
        raise ValueError('Conversas: "tabMessages" precisa ser um objeto.')


def load_conversations(settings: Settings | None = None) -> dict | None:
    """Conversas salvas, ou None sem arquivo. Arquivo ilegível ou de outra forma também vira None: o app começa do zero."""
    path = _path(settings)
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding='utf-8'))
        _check_shape(payload)
    except (OSError, ValueError) as exc:
        logger.warning('Conversas salvas ignoradas (%s): %s', path, exc)
        return None
    return payload


def save_conversations(payload: dict, settings: Settings | None = None) -> None:
    """Grava as conversas de forma atômica: escreve um .tmp e troca pelo arquivo, sem JSON pela metade se cair no meio."""
    _check_shape(payload)
    text = json.dumps(payload, ensure_ascii=False)
    if len(text.encode('utf-8')) > MAX_CONVERSATIONS_BYTES:
        raise ValueError('Conversas grandes demais para salvar (limite de 5 MB).')
    path = _path(settings)
    with _write_lock:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(path.name + '.tmp')
        tmp.write_text(text, encoding='utf-8')
        os.replace(tmp, path)
