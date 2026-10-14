import json
from collections.abc import Callable
from dataclasses import dataclass
from time import perf_counter
from typing import Literal
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from pydantic import BaseModel

from escolio.app.config import Settings, get_settings
from escolio.providers.answer import (
    INVALID_BASE_URL_ERROR,
    _default_base_url,
    _is_http_base_url,
)
from escolio.providers.model_discovery import _strip_v1_path, list_answer_models

RuntimeStatus = Literal['ready', 'no_model', 'offline', 'unauthorized', 'not_applicable', 'error']
ONLY_OLLAMA_ERROR = 'ensure_model suporta apenas provider ollama por enquanto.'


@dataclass(frozen=True)
class ModelCatalogEntry:
    """Preset curado que mapeia uma escolha amigável para um pull concreto."""

    catalog_id: str
    label: str
    pull_name: str
    parameter_size: str
    quantization: str
    context_tokens: int
    min_vram_gb: float
    profile: str


# Seed com os dois Gemmas de referência. As tags são as de distribuição
# (Ollama registry); o quant fica no sufixo da tag e define o tamanho do download.
MODEL_CATALOG: tuple[ModelCatalogEntry, ...] = (
    ModelCatalogEntry(
        catalog_id='gemma-inteligente',
        label='Gemma 3n E4B — inteligente',
        pull_name='gemma3n:e4b',
        parameter_size='E4B',
        quantization='Q4_K_M',
        context_tokens=32_000,
        min_vram_gb=6.0,
        profile='inteligente',
    ),
    ModelCatalogEntry(
        catalog_id='gemma-veloz',
        label='Gemma 2B — veloz',
        pull_name='gemma2:2b-instruct-q4_K_M',
        parameter_size='2B',
        quantization='Q4_K_M',
        context_tokens=128_000,
        min_vram_gb=4.0,
        profile='veloz',
    ),
)


def catalog_entry(catalog_id: str) -> ModelCatalogEntry | None:
    return next((entry for entry in MODEL_CATALOG if entry.catalog_id == catalog_id), None)


class RuntimeStatusReport(BaseModel):
    provider: str
    base_url: str | None
    status: RuntimeStatus
    installed_models: list[str]
    message: str | None = None


class PullProgress(BaseModel):
    status: str
    completed: int | None = None
    total: int | None = None


class EnsureModelResult(BaseModel):
    model: str
    ok: bool
    final_status: str
    latency_ms: int
    error: str | None = None


def _model_matches(wanted: str, installed: str) -> bool:
    if wanted == installed:
        return True
    return installed.split(':', 1)[0] == wanted or installed == f'{wanted}:latest'


def detect_runtime(settings: Settings | None = None) -> RuntimeStatusReport:
    """Diagnostica se o runtime do provider está pronto para responder.

    Reaproveita a descoberta de modelos: ``ready`` quando o servidor responde e
    o modelo configurado está instalado, ``no_model`` quando o servidor está de
    pé mas o modelo falta, e os demais estados refletem a falha de descoberta.
    """
    resolved = settings or get_settings()
    discovery = list_answer_models(resolved, use_cache=False)
    installed = [model.id for model in discovery.models]

    non_ok: dict[str, RuntimeStatus] = {
        'not_applicable': 'not_applicable',
        'offline': 'offline',
        'unauthorized': 'unauthorized',
        'error': 'error',
    }
    if discovery.status in non_ok:
        return RuntimeStatusReport(
            provider=resolved.answer_provider,
            base_url=discovery.base_url,
            status=non_ok[discovery.status],
            installed_models=installed,
            message=discovery.message,
        )

    has_model = any(_model_matches(resolved.answer_model, name) for name in installed)
    return RuntimeStatusReport(
        provider=resolved.answer_provider,
        base_url=discovery.base_url,
        status='ready' if has_model else 'no_model',
        installed_models=installed,
        message=None if has_model else f'Modelo {resolved.answer_model} nao esta instalado.',
    )


def runtime_hint(report: RuntimeStatusReport) -> str:
    """Mensagem acionável em pt-br para o estado do runtime do provider.

    Converte o `status` técnico do `detect_runtime` em uma orientação que o
    usuário consegue agir, para a UI mostrar isso no lugar de erros crus de
    socket (ex.: WinError 10061).
    """
    if report.status == 'ready':
        return 'Runtime pronto: servidor no ar e modelo instalado.'
    if report.status == 'offline':
        if report.provider == 'ollama':
            return (
                'Servidor do provider offline. Inicie o Ollama '
                '(rode "ollama serve" ou abra o app do Ollama) e teste de novo.'
            )
        base_url = report.base_url or '(base_url nao configurada)'
        return f'Servidor do provider {report.provider} offline em {base_url}. Verifique se ele esta no ar.'
    if report.status == 'no_model':
        installed = ', '.join(report.installed_models) if report.installed_models else 'nenhum'
        if report.provider == 'ollama':
            return (
                f'Modelo configurado nao esta instalado. Instalados: {installed}. '
                'Baixe com "provider pull <modelo>" ou aponte answer_model para um destes.'
            )
        return (
            f'Modelo configurado nao esta disponivel no provider {report.provider}. Instalados: {installed}. '
            'Ajuste answer_model para um destes ou verifique a credencial do provider remoto.'
        )
    if report.status == 'unauthorized':
        return 'Provider remoto exige API key valida para listar e usar modelos.'
    if report.status == 'not_applicable':
        return 'Provider extractive nao usa modelo generativo (respostas extrativas).'
    return report.message or 'Nao foi possivel diagnosticar o runtime.'


def _pull_base_url(settings: Settings) -> str:
    return _strip_v1_path(_default_base_url('ollama', settings.answer_base_url))


def ensure_model(
    model_name: str,
    settings: Settings | None = None,
    *,
    on_progress: Callable[[PullProgress], None] | None = None,
    timeout_seconds: float = 600.0,
) -> EnsureModelResult:
    """Garante que um modelo esteja disponível localmente via Ollama ``/api/pull``.

    Faz streaming do progresso de download (status/completed/total) chamando
    ``on_progress`` a cada evento. O pull do Ollama é idempotente: se o modelo
    já existe, retorna rápido sem rebaixar nada.
    """
    resolved = settings or get_settings()
    started_at = perf_counter()

    def _elapsed() -> int:
        return int((perf_counter() - started_at) * 1000)

    if resolved.answer_provider != 'ollama':
        return EnsureModelResult(model=model_name, ok=False, final_status='', latency_ms=0, error=ONLY_OLLAMA_ERROR)

    base_url = _pull_base_url(resolved)
    if not _is_http_base_url(base_url):
        return EnsureModelResult(model=model_name, ok=False, final_status='', latency_ms=0, error=INVALID_BASE_URL_ERROR)

    request = Request(
        f'{base_url}/api/pull',
        data=json.dumps({'name': model_name, 'stream': True}).encode('utf-8'),
        headers={'Content-Type': 'application/json'},
        method='POST',
    )

    last_status = ''
    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            for raw_line in response:
                line = raw_line.decode('utf-8').strip()
                if not line:
                    continue
                event = json.loads(line)
                if event.get('error'):
                    return EnsureModelResult(
                        model=model_name, ok=False, final_status='error', latency_ms=_elapsed(), error=str(event['error'])
                    )
                progress = PullProgress(status=str(event.get('status', '')), completed=event.get('completed'), total=event.get('total'))
                last_status = progress.status
                if on_progress is not None:
                    on_progress(progress)
    except HTTPError as exc:
        return EnsureModelResult(model=model_name, ok=False, final_status='', latency_ms=_elapsed(), error=f'Ollama respondeu HTTP {exc.code}.')
    except (URLError, TimeoutError) as exc:
        reason = getattr(exc, 'reason', 'timeout')
        return EnsureModelResult(model=model_name, ok=False, final_status='', latency_ms=_elapsed(), error=f'Ollama indisponivel: {reason}.')
    except (json.JSONDecodeError, UnicodeDecodeError):
        return EnsureModelResult(model=model_name, ok=False, final_status=last_status, latency_ms=_elapsed(), error='Ollama retornou stream invalido.')

    ok = last_status == 'success'
    return EnsureModelResult(
        model=model_name,
        ok=ok,
        final_status=last_status,
        latency_ms=_elapsed(),
        error=None if ok else 'Pull terminou sem status de sucesso.',
    )
