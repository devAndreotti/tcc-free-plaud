import json
from time import perf_counter, time
from typing import Literal
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse, urlunparse
from urllib.request import Request, urlopen

from pydantic import BaseModel, Field

from escolio.app.config import Settings, get_settings
from escolio.providers.answer import (
    INVALID_BASE_URL_ERROR,
    _default_base_url,
    _is_http_base_url,
)

ModelDiscoveryStatus = Literal['ok', 'not_applicable', 'offline', 'unauthorized', 'error']
CACHE_TTL_SECONDS = 10.0
OLLAMA_DETAIL_KEYS = ('size', 'modified_at', 'digest')
OLLAMA_NESTED_DETAIL_KEYS = ('family', 'parameter_size', 'quantization_level')


class ModelInfo(BaseModel):
    id: str
    label: str
    provider: str
    details: dict[str, object] = Field(default_factory=dict)


class ModelDiscoveryResult(BaseModel):
    provider: str
    base_url: str | None
    status: ModelDiscoveryStatus
    models: list[ModelInfo] = Field(default_factory=list)
    latency_ms: int
    cached: bool = False
    message: str | None = None


_CACHE: dict[tuple[str, str | None, bool], tuple[float, ModelDiscoveryResult]] = {}


def clear_model_discovery_cache() -> None:
    _CACHE.clear()


def _safe_result(
    settings: Settings,
    *,
    base_url: str | None,
    status: ModelDiscoveryStatus,
    started_at: float,
    models: list[ModelInfo] | None = None,
    message: str | None = None,
) -> ModelDiscoveryResult:
    return ModelDiscoveryResult(
        provider=settings.answer_provider,
        base_url=base_url,
        status=status,
        models=models or [],
        latency_ms=int((perf_counter() - started_at) * 1000),
        message=message,
    )


def _strip_v1_path(base_url: str) -> str:
    parsed = urlparse(base_url)
    path = parsed.path.rstrip('/')
    if path.endswith('/v1'):
        path = path[:-3].rstrip('/')
    return urlunparse((parsed.scheme, parsed.netloc, path, '', '', '')).rstrip('/')


def _discovery_base_url(settings: Settings) -> str | None:
    if settings.answer_provider == 'extractive':
        return None
    base_url = _default_base_url(settings.answer_provider, settings.answer_base_url)
    if settings.answer_provider == 'ollama':
        return _strip_v1_path(base_url)
    return base_url.rstrip('/')


def _endpoint_for(settings: Settings, base_url: str) -> str:
    if settings.answer_provider == 'ollama':
        return f'{base_url}/api/tags'
    return f'{base_url}/models'


def _request(endpoint: str, settings: Settings, timeout_seconds: float) -> bytes:
    headers = {'Accept': 'application/json'}
    if settings.answer_api_key:
        headers['Authorization'] = f'Bearer {settings.answer_api_key}'
    request = Request(endpoint, headers=headers, method='GET')
    with urlopen(request, timeout=timeout_seconds) as response:
        return response.read()


def _model_items(payload: object, key: str) -> list[object]:
    if not isinstance(payload, dict) or not isinstance(payload.get(key), list):
        raise ValueError('resposta nao contem modelos')
    return payload[key]


def _copy_details(source: dict[str, object], keys: tuple[str, ...]) -> dict[str, object]:
    return {key: source[key] for key in keys if key in source}


def _ollama_details(item: dict[str, object]) -> dict[str, object]:
    details = _copy_details(item, OLLAMA_DETAIL_KEYS)
    raw_details = item.get('details')
    if isinstance(raw_details, dict):
        details.update(_copy_details(raw_details, OLLAMA_NESTED_DETAIL_KEYS))
    return details


def _is_embedding_model(item: dict[str, object]) -> bool:
    # nomic-embed-text, all-minilm, mxbai-embed... só geram vetores: não servem para escrever a resposta.
    details = item.get('details')
    family = str(details.get('family', '')) if isinstance(details, dict) else ''
    return 'embed' in str(item['name']) or family.endswith('bert')


def _ollama_model(item: object) -> ModelInfo | None:
    if not isinstance(item, dict) or not item.get('name') or _is_embedding_model(item):
        return None
    model_id = str(item['name'])
    return ModelInfo(id=model_id, label=model_id, provider='ollama', details=_ollama_details(item))


def _ollama_models(payload: object) -> list[ModelInfo]:
    return [model for item in _model_items(payload, 'models') if (model := _ollama_model(item)) is not None]


def _openai_models(payload: object, provider: str) -> list[ModelInfo]:
    models: list[ModelInfo] = []
    for item in _model_items(payload, 'data'):
        if not isinstance(item, dict) or not item.get('id'):
            continue
        model_id = str(item['id'])
        details = {key: value for key, value in item.items() if key != 'id'}
        models.append(ModelInfo(id=model_id, label=model_id, provider=provider, details=details))
    return models


def _parse_models(settings: Settings, body: bytes) -> list[ModelInfo]:
    try:
        payload = json.loads(body.decode('utf-8'))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError('payload invalido') from exc
    if settings.answer_provider == 'ollama':
        return _ollama_models(payload)
    return _openai_models(payload, settings.answer_provider)


def _cache_key(settings: Settings, base_url: str | None) -> tuple[str, str | None, bool]:
    return (settings.answer_provider, base_url, bool(settings.answer_api_key))


def _from_cache(key: tuple[str, str | None, bool]) -> ModelDiscoveryResult | None:
    cached = _CACHE.get(key)
    if cached is None:
        return None
    stored_at, result = cached
    if time() - stored_at > CACHE_TTL_SECONDS:
        _CACHE.pop(key, None)
        return None
    return result.model_copy(update={'cached': True})


def _save_cache(key: tuple[str, str | None, bool], result: ModelDiscoveryResult) -> None:
    _CACHE[key] = (time(), result)


def _default_openai_without_key(settings: Settings) -> bool:
    return (
        settings.answer_provider == 'openai-compatible'
        and not settings.answer_base_url
        and not settings.answer_api_key
    )


def _not_applicable_result(settings: Settings, started_at: float) -> ModelDiscoveryResult:
    return _safe_result(
        settings,
        base_url=None,
        status='not_applicable',
        started_at=started_at,
        message='Provider extractive nao usa modelo generativo.',
    )


def _invalid_base_url_result(settings: Settings, base_url: str | None, started_at: float) -> ModelDiscoveryResult:
    return _safe_result(
        settings,
        base_url=base_url,
        status='error',
        started_at=started_at,
        message=INVALID_BASE_URL_ERROR,
    )


def _unauthorized_result(settings: Settings, base_url: str, started_at: float) -> ModelDiscoveryResult:
    return _safe_result(
        settings,
        base_url=base_url,
        status='unauthorized',
        started_at=started_at,
        message='API key ausente para listar modelos do provider remoto.',
    )


def _request_models_result(
    settings: Settings,
    *,
    base_url: str,
    timeout_seconds: float,
    started_at: float,
) -> ModelDiscoveryResult:
    try:
        body = _request(_endpoint_for(settings, base_url), settings, timeout_seconds)
        models = _parse_models(settings, body)
    except HTTPError as exc:
        return _http_error_result(settings, base_url=base_url, started_at=started_at, exc=exc)
    except (URLError, TimeoutError):
        return _safe_result(
            settings,
            base_url=base_url,
            status='offline',
            started_at=started_at,
            message='Servidor indisponivel ou timeout.',
        )
    except ValueError as exc:
        return _safe_result(settings, base_url=base_url, status='error', started_at=started_at, message=str(exc))
    return _safe_result(settings, base_url=base_url, status='ok', started_at=started_at, models=models)


def _http_error_result(
    settings: Settings,
    *,
    base_url: str,
    started_at: float,
    exc: HTTPError,
) -> ModelDiscoveryResult:
    status: ModelDiscoveryStatus = 'unauthorized' if exc.code in {401, 403} else 'error'
    message = 'Credencial ausente ou invalida.' if status == 'unauthorized' else f'Provider respondeu HTTP {exc.code}.'
    return _safe_result(settings, base_url=base_url, status=status, started_at=started_at, message=message)


def list_answer_models(
    settings: Settings | None = None,
    *,
    timeout_seconds: float = 2.0,
    use_cache: bool = True,
) -> ModelDiscoveryResult:
    resolved = settings or get_settings()
    started_at = perf_counter()
    if resolved.answer_provider == 'extractive':
        return _not_applicable_result(resolved, started_at)

    base_url = _discovery_base_url(resolved)
    if base_url is None or not _is_http_base_url(base_url):
        return _invalid_base_url_result(resolved, base_url, started_at)

    if _default_openai_without_key(resolved):
        return _unauthorized_result(resolved, base_url, started_at)

    key = _cache_key(resolved, base_url)
    if use_cache:
        cached = _from_cache(key)
        if cached is not None:
            return cached

    result = _request_models_result(
        resolved,
        base_url=base_url,
        timeout_seconds=timeout_seconds,
        started_at=started_at,
    )
    if use_cache and result.status == 'ok':
        _save_cache(key, result)
    return result
