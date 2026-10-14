import sqlite3
from time import perf_counter

from escolio.app.config import Settings
from escolio.app.doctor_models import DoctorCheck, DoctorStatus
from escolio.corpus.service import get_corpus_status
from escolio.storage.vector import LocalVectorStore


def _elapsed_ms(started_at: float) -> int:
    return int((perf_counter() - started_at) * 1000)


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
            message='FTS5 indisponível no SQLite atual.',
            action='Verifique build do SQLite/Python usado pelo ambiente.',
            details={'fts_status': status, 'fts_chunks_count': count},
        )
    return DoctorCheck(
        code='fts',
        status='warning',
        message=f'Índice lexical FTS está {status}.',
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

    return [
        _fts_status_to_check(status.fts_status, status.fts_chunks_count),
        DoctorCheck(
            code='corpus',
            status=corpus_status,
            message=message,
            action=action,
            details=status.model_dump(),
        ),
    ]


def safe_corpus_checks(
    settings: Settings,
    connection: sqlite3.Connection | None,
    vector_store: LocalVectorStore | None,
) -> list[DoctorCheck]:
    started_at = perf_counter()
    try:
        checks = _corpus_checks(settings, connection, vector_store)
    except Exception as exc:
        latency_ms = _elapsed_ms(started_at)
        message = f'Falha ao diagnosticar corpus: {type(exc).__name__}: {exc}'
        return [
            DoctorCheck(
                code='fts',
                status='error',
                message=message,
                action='Verifique SQLite, Chroma e caminhos do runtime.',
                latency_ms=latency_ms,
            ),
            DoctorCheck(
                code='corpus',
                status='error',
                message=message,
                action='Verifique SQLite, Chroma e caminhos do runtime.',
                latency_ms=latency_ms,
            ),
        ]
    latency_ms = _elapsed_ms(started_at)
    for check in checks:
        check.latency_ms = latency_ms
    return checks
