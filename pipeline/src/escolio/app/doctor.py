import sqlite3
from collections.abc import Callable
from time import perf_counter

from escolio.app.config import Settings, get_settings
from escolio.app.doctor_audio import audio_checks
from escolio.app.doctor_corpus import safe_corpus_checks
from escolio.app.doctor_models import DoctorCheck, DoctorReport, DoctorStatus
from escolio.app.local_env import answer_api_key_is_configured
from escolio.providers import embed as embed_provider
from escolio.providers.model_discovery import list_answer_models
from escolio.storage.sqlite import init_sqlite
from escolio.storage.vector import LocalVectorStore

EMBEDDING_MODEL_CHECK = "settings.embedding_model"
EMBEDDING_DEVICE_CHECK = "settings.embedding_device"


def _elapsed_ms(started_at: float) -> int:
    return int((perf_counter() - started_at) * 1000)


def _status_for(checks: list[DoctorCheck]) -> DoctorStatus:
    if any(check.status == "error" for check in checks):
        return "error"
    if any(check.status == "warning" for check in checks):
        return "warning"
    return "ok"


def _run_check(code: str, func: Callable[[], DoctorCheck]) -> DoctorCheck:
    started_at = perf_counter()
    try:
        check = func()
    except Exception as exc:
        return DoctorCheck(
            code=code,
            status="error",
            message=f"Falha ao executar check: {type(exc).__name__}: {exc}",
            action="Verifique logs, caminhos e dependências locais.",
            latency_ms=_elapsed_ms(started_at),
        )
    check.latency_ms = _elapsed_ms(started_at)
    return check


def _embedding_model_check(settings: Settings) -> DoctorCheck:
    if settings.embedding_model == "fake-hash":
        return DoctorCheck(
            code=EMBEDDING_MODEL_CHECK,
            status="error",
            message="fake-hash é modelo de teste e não deve ser usado no app real.",
            action="Use chroma-default ou sentence-transformer:<modelo>.",
        )
    try:
        diagnostics = embed_provider.describe_embedding_config(
            settings.embedding_model,
            device=settings.embedding_device,
        )
    except ValueError as exc:
        return DoctorCheck(
            code=EMBEDDING_MODEL_CHECK,
            status="error",
            message=str(exc),
            action="Corrija embedding_model nas settings.",
        )
    return DoctorCheck(
        code=EMBEDDING_MODEL_CHECK,
        status="ok",
        message=f"Modelo de embedding válido: {diagnostics.model_name}.",
        details={"model_name": diagnostics.model_name},
    )


def _embedding_device_check(settings: Settings) -> DoctorCheck:
    if settings.embedding_model == "chroma-default":
        status: DoctorStatus = (
            "warning" if settings.embedding_device == "cuda" else "ok"
        )
        return DoctorCheck(
            code=EMBEDDING_DEVICE_CHECK,
            status=status,
            message="Device não se aplica ao chroma-default.",
            action="Use cpu/auto ou troque para sentence-transformer se quiser CUDA."
            if status == "warning"
            else None,
            details={
                "requested_device": settings.embedding_device,
                "device_applicable": False,
            },
        )
    if not settings.embedding_model.startswith("sentence-transformer:"):
        return DoctorCheck(
            code=EMBEDDING_DEVICE_CHECK,
            status="warning",
            message="Device não foi avaliado porque o modelo de embedding não é suportado.",
            action="Corrija embedding_model primeiro.",
            details={"requested_device": settings.embedding_device},
        )
    try:
        diagnostics = embed_provider.describe_embedding_config(
            settings.embedding_model,
            device=settings.embedding_device,
        )
    except ValueError as exc:
        return DoctorCheck(
            code=EMBEDDING_DEVICE_CHECK,
            status="error",
            message=str(exc),
            action="Instale PyTorch com CUDA ou selecione embedding_device=cpu/auto.",
            details={"requested_device": settings.embedding_device},
        )
    return DoctorCheck(
        code=EMBEDDING_DEVICE_CHECK,
        status="ok",
        message=diagnostics.message,
        details={
            "requested_device": diagnostics.requested_device,
            "resolved_device": diagnostics.resolved_device,
            "device_applicable": diagnostics.device_applicable,
        },
    )


def _sqlite_check(
    settings: Settings, connection: sqlite3.Connection | None
) -> DoctorCheck:
    owns_connection = connection is None
    resolved_connection = connection or init_sqlite(settings.sqlite_path)
    try:
        resolved_connection.execute("SELECT 1").fetchone()
        return DoctorCheck(
            code="sqlite",
            status="ok",
            message="SQLite acessível e schema inicializável.",
            details={"sqlite_path": str(settings.sqlite_path)},
        )
    finally:
        if owns_connection:
            resolved_connection.close()


def _chroma_check(
    settings: Settings, vector_store: LocalVectorStore | None
) -> DoctorCheck:
    resolved_vector_store = vector_store or LocalVectorStore(
        settings.vector_store_dir,
        collection_name=settings.vector_collection_name,
    )
    count = resolved_vector_store.count()
    return DoctorCheck(
        code="chroma",
        status="ok",
        message="Chroma acessível.",
        details={
            "vector_store_dir": str(settings.vector_store_dir),
            "collection_name": resolved_vector_store.collection_name,
            "vector_entries_count": count,
        },
    )


def _answer_provider_check(settings: Settings) -> DoctorCheck:
    if settings.answer_provider == "extractive":
        return DoctorCheck(
            code="answer_provider",
            status="ok",
            message="Provider extractive ativo; não usa LLM externa.",
            details={"answer_provider": settings.answer_provider},
        )
    if not settings.answer_model.strip():
        return DoctorCheck(
            code="answer_provider",
            status="warning",
            message="Provider generativo sem modelo configurado.",
            action="Configure answer_model nas settings.",
            details={"answer_provider": settings.answer_provider},
        )
    details = {
        "answer_provider": settings.answer_provider,
        "answer_model": settings.answer_model,
        "answer_base_url": settings.answer_base_url or "default",
    }
    discovery = list_answer_models(settings)
    if discovery.status == "not_applicable":
        return DoctorCheck(
            code="answer_provider",
            status="warning",
            message="Teste do provider generativo não se aplica.",
            details=details,
        )
    if discovery.status != "ok":
        return DoctorCheck(
            code="answer_provider",
            status="error",
            message=f"Provider generativo indisponível: {discovery.message or discovery.status}.",
            action="Inicie o provider ou confira base_url e API key nas settings.",
            details=details,
        )
    model = settings.answer_model.strip()
    installed = {item.id for item in discovery.models}
    if model not in installed and f"{model}:latest" not in installed:
        return DoctorCheck(
            code="answer_provider",
            status="warning",
            message=f"Modelo {model} não aparece na lista do provider.",
            action="Confira o nome do modelo ou baixe-o no provider.",
            details=details,
        )
    return DoctorCheck(
        code="answer_provider",
        status="ok",
        message=f"Provider generativo respondeu e listou o modelo: {settings.answer_provider}.",
        details=details,
    )


def _api_key_check(settings: Settings) -> DoctorCheck:
    configured = bool(settings.answer_api_key) or answer_api_key_is_configured(
        settings=settings
    )
    if settings.answer_provider in {"extractive", "ollama", "lmstudio"}:
        return DoctorCheck(
            code="api_key",
            status="ok",
            message=f"Provider {settings.answer_provider} não exige API key.",
            details={"configured": configured, "required": False},
        )
    if configured:
        return DoctorCheck(
            code="api_key",
            status="ok",
            message="API key configurada para provider remoto.",
            details={"configured": True, "required": True},
        )
    return DoctorCheck(
        code="api_key",
        status="warning",
        message="Provider remoto sem API key configurada.",
        action="Configure ESCOLIO_ANSWER_API_KEY no .env local.",
        details={"configured": False, "required": True},
    )


def run_doctor(
    *,
    settings: Settings | None = None,
    connection: sqlite3.Connection | None = None,
    vector_store: LocalVectorStore | None = None,
) -> DoctorReport:
    """Executa diagnostico estruturado sem inicializar modelos pesados."""
    started_at = perf_counter()
    resolved_settings = settings or get_settings()
    checks: list[DoctorCheck] = [
        _run_check(
            "settings.embedding_model",
            lambda: _embedding_model_check(resolved_settings),
        ),
        _run_check(
            "settings.embedding_device",
            lambda: _embedding_device_check(resolved_settings),
        ),
        _run_check("sqlite", lambda: _sqlite_check(resolved_settings, connection)),
        _run_check("chroma", lambda: _chroma_check(resolved_settings, vector_store)),
    ]
    checks.extend(safe_corpus_checks(resolved_settings, connection, vector_store))
    checks.extend(
        [
            _run_check(
                "answer_provider", lambda: _answer_provider_check(resolved_settings)
            ),
            _run_check("api_key", lambda: _api_key_check(resolved_settings)),
        ]
    )
    checks.extend(audio_checks(resolved_settings))
    ok_count = sum(check.status == "ok" for check in checks)
    warning_count = sum(check.status == "warning" for check in checks)
    error_count = sum(check.status == "error" for check in checks)
    return DoctorReport(
        status=_status_for(checks),
        checks=checks,
        latency_ms=_elapsed_ms(started_at),
        ok_count=ok_count,
        warning_count=warning_count,
        error_count=error_count,
    )
