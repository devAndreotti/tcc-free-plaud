import sqlite3
from collections.abc import Callable
from time import perf_counter

from free_plaud.app.config import Settings, get_settings
from free_plaud.app.doctor_models import DoctorCheck, DoctorReport, DoctorStatus
from free_plaud.app.local_env import answer_api_key_is_configured
from free_plaud.corpus.service import get_corpus_status
from free_plaud.providers import embed as embed_provider
from free_plaud.storage.sqlite import init_sqlite
from free_plaud.storage.vector import LocalVectorStore


def _elapsed_ms(started_at: float) -> int:
    return int((perf_counter() - started_at) * 1000)


def _status_for(checks: list[DoctorCheck]) -> DoctorStatus:
    if any(check.status == 'error' for check in checks):
        return 'error'
    if any(check.status == 'warning' for check in checks):
        return 'warning'
    return 'ok'


def _run_check(code: str, func: Callable[[], DoctorCheck]) -> DoctorCheck:
    started_at = perf_counter()
    try:
        check = func()
    except Exception as exc:
        return DoctorCheck(
            code=code,
            status='error',
            message=f'Falha ao executar check: {type(exc).__name__}: {exc}',
            action='Verifique logs, caminhos e dependencias locais.',
            latency_ms=_elapsed_ms(started_at),
        )
    check.latency_ms = _elapsed_ms(started_at)
    return check


def _embedding_model_check(settings: Settings) -> DoctorCheck:
    if settings.embedding_model == 'fake-hash':
        return DoctorCheck(
            code='settings.embedding_model',
            status='error',
            message='fake-hash e modelo de teste e nao deve ser usado no app real.',
            action='Use chroma-default ou sentence-transformer:<modelo>.',
        )
    try:
        diagnostics = embed_provider.describe_embedding_config(
            settings.embedding_model,
            device=settings.embedding_device,
        )
    except ValueError as exc:
        return DoctorCheck(
            code='settings.embedding_model',
            status='error',
            message=str(exc),
            action='Corrija embedding_model nas settings.',
        )
    return DoctorCheck(
        code='settings.embedding_model',
        status='ok',
        message=f'Modelo de embedding valido: {diagnostics.model_name}.',
        details={'model_name': diagnostics.model_name},
    )


def _embedding_device_check(settings: Settings) -> DoctorCheck:
    if settings.embedding_model == 'chroma-default':
        status: DoctorStatus = 'warning' if settings.embedding_device == 'cuda' else 'ok'
        return DoctorCheck(
            code='settings.embedding_device',
            status=status,
            message='Device nao se aplica ao chroma-default.',
            action='Use cpu/auto ou troque para sentence-transformer se quiser CUDA.' if status == 'warning' else None,
            details={'requested_device': settings.embedding_device, 'device_applicable': False},
        )
    if not settings.embedding_model.startswith('sentence-transformer:'):
        return DoctorCheck(
            code='settings.embedding_device',
            status='warning',
            message='Device nao foi avaliado porque o modelo de embedding nao e suportado.',
            action='Corrija embedding_model primeiro.',
            details={'requested_device': settings.embedding_device},
        )
    try:
        diagnostics = embed_provider.describe_embedding_config(
            settings.embedding_model,
            device=settings.embedding_device,
        )
    except ValueError as exc:
        return DoctorCheck(
            code='settings.embedding_device',
            status='error',
            message=str(exc),
            action='Instale PyTorch com CUDA ou selecione embedding_device=cpu/auto.',
            details={'requested_device': settings.embedding_device},
        )
    return DoctorCheck(
        code='settings.embedding_device',
        status='ok',
        message=diagnostics.message,
        details={
            'requested_device': diagnostics.requested_device,
            'resolved_device': diagnostics.resolved_device,
            'device_applicable': diagnostics.device_applicable,
        },
    )


def _sqlite_check(settings: Settings, connection: sqlite3.Connection | None) -> DoctorCheck:
    owns_connection = connection is None
    resolved_connection = connection or init_sqlite(settings.sqlite_path)
    try:
        resolved_connection.execute('SELECT 1').fetchone()
        return DoctorCheck(
            code='sqlite',
            status='ok',
            message='SQLite acessivel e schema inicializavel.',
            details={'sqlite_path': str(settings.sqlite_path)},
        )
    finally:
        if owns_connection:
            resolved_connection.close()


def _chroma_check(settings: Settings, vector_store: LocalVectorStore | None) -> DoctorCheck:
    resolved_vector_store = vector_store or LocalVectorStore(
        settings.vector_store_dir,
        collection_name=settings.vector_collection_name,
    )
    count = resolved_vector_store.count()
    return DoctorCheck(
        code='chroma',
        status='ok',
        message='Chroma acessivel.',
        details={
            'vector_store_dir': str(settings.vector_store_dir),
            'collection_name': resolved_vector_store.collection_name,
            'vector_entries_count': count,
        },
    )


def _fts_status_to_check(status: str, count: int) -> DoctorCheck:
    if status == 'ready':
        return DoctorCheck(
            code='fts',
            status='ok',
            message='FTS5 pronto.',
            details={'fts_status': status, 'fts_chunks_count': count},
        )
    if status == 'unavailable':
        return DoctorCheck(
            code='fts',
            status='error',
            message='FTS5 indisponivel no SQLite atual.',
            action='Verifique build do SQLite/Python usado pelo ambiente.',
            details={'fts_status': status, 'fts_chunks_count': count},
        )
    return DoctorCheck(
        code='fts',
        status='warning',
        message=f'Indice lexical FTS esta {status}.',
        action='Reindexe ou reconstrua o corpus para sincronizar FTS.',
        details={'fts_status': status, 'fts_chunks_count': count},
    )


def _corpus_checks(
    settings: Settings,
    connection: sqlite3.Connection | None,
    vector_store: LocalVectorStore | None,
) -> list[DoctorCheck]:
    status = get_corpus_status(settings=settings, connection=connection, vector_store=vector_store)
    if status.status == 'clean':
        corpus_status: DoctorStatus = 'ok'
        message = 'Corpus consistente entre SQLite e Chroma.'
        action = None
    elif status.status == 'empty':
        corpus_status = 'warning'
        message = 'Corpus vazio.'
        action = 'Indexe uma pasta ou arquivo antes de perguntar.'
    elif status.status == 'sqlite_only':
        corpus_status = 'warning'
        message = 'Corpus existe no SQLite, mas faltam vetores no Chroma.'
        action = 'Reindexe ou rode rebuild do corpus.'
    else:
        corpus_status = 'error'
        message = 'Corpus inconsistente entre SQLite e Chroma.'
        action = 'Reindexe ou rode rebuild do corpus.'

    status_payload = status.model_dump()
    return [
        _fts_status_to_check(status.fts_status, status.fts_chunks_count),
        DoctorCheck(
            code='corpus',
            status=corpus_status,
            message=message,
            action=action,
            details=status_payload,
        ),
    ]


def _answer_provider_check(settings: Settings) -> DoctorCheck:
    if settings.answer_provider == 'extractive':
        return DoctorCheck(
            code='answer_provider',
            status='ok',
            message='Provider extractive ativo; nao usa LLM externa.',
            details={'answer_provider': settings.answer_provider},
        )
    if not settings.answer_model.strip():
        return DoctorCheck(
            code='answer_provider',
            status='warning',
            message='Provider generativo sem modelo configurado.',
            action='Configure answer_model nas settings.',
            details={'answer_provider': settings.answer_provider},
        )
    return DoctorCheck(
        code='answer_provider',
        status='ok',
        message=f'Provider generativo configurado: {settings.answer_provider}.',
        details={
            'answer_provider': settings.answer_provider,
            'answer_model': settings.answer_model,
            'answer_base_url': settings.answer_base_url or 'default',
        },
    )


def _api_key_check(settings: Settings) -> DoctorCheck:
    configured = bool(settings.answer_api_key) or answer_api_key_is_configured(settings=settings)
    if settings.answer_provider in {'extractive', 'ollama', 'lmstudio'}:
        return DoctorCheck(
            code='api_key',
            status='ok',
            message=f'Provider {settings.answer_provider} nao exige API key.',
            details={'configured': configured, 'required': False},
        )
    if configured:
        return DoctorCheck(
            code='api_key',
            status='ok',
            message='API key configurada para provider remoto.',
            details={'configured': True, 'required': True},
        )
    return DoctorCheck(
        code='api_key',
        status='warning',
        message='Provider remoto sem API key configurada.',
        action='Configure FREE_PLAUD_ANSWER_API_KEY no .env local.',
        details={'configured': False, 'required': True},
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
        _run_check('settings.embedding_model', lambda: _embedding_model_check(resolved_settings)),
        _run_check('settings.embedding_device', lambda: _embedding_device_check(resolved_settings)),
        _run_check('sqlite', lambda: _sqlite_check(resolved_settings, connection)),
        _run_check('chroma', lambda: _chroma_check(resolved_settings, vector_store)),
    ]
    checks.extend(_corpus_checks(resolved_settings, connection, vector_store))
    checks.extend(
        [
            _run_check('answer_provider', lambda: _answer_provider_check(resolved_settings)),
            _run_check('api_key', lambda: _api_key_check(resolved_settings)),
        ]
    )
    ok_count = sum(check.status == 'ok' for check in checks)
    warning_count = sum(check.status == 'warning' for check in checks)
    error_count = sum(check.status == 'error' for check in checks)
    return DoctorReport(
        status=_status_for(checks),
        checks=checks,
        latency_ms=_elapsed_ms(started_at),
        ok_count=ok_count,
        warning_count=warning_count,
        error_count=error_count,
    )
