from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from threading import Lock, Thread
from uuid import uuid4

from pydantic import BaseModel, Field

from escolio.corpus.cancellation import CancellationToken
from escolio.corpus.models import CorpusIndexBatchResult, CorpusIndexProgress
from escolio.corpus.runtime import CorpusRuntime

IndexJobStatus = str

# Uma escrita no corpus por vez: o job de pasta e a fila de arquivos soltos compartilham esta trava.
corpus_write_lock = Lock()


class IndexJobAlreadyRunningError(RuntimeError):
    """Raised when the process already has an active indexing job."""


class IndexJobFileError(BaseModel):
    source_path: str
    message: str
    error_code: str | None = None


class IndexJobSnapshot(BaseModel):
    job_id: str
    status: IndexJobStatus
    source_path: str
    started_at: str
    finished_at: str | None = None
    progress: CorpusIndexProgress | None = None
    result: CorpusIndexBatchResult | None = None
    error_code: str | None = None
    message: str | None = None
    last_errors: list[IndexJobFileError] = Field(default_factory=list)
    cancel_requested: bool = False
    files_per_second: float = 0.0
    chunks_per_second: float = 0.0
    eta_seconds: int | None = None


IndexJobRunner = Callable[..., CorpusIndexBatchResult]


@dataclass
class _JobState:
    snapshot: IndexJobSnapshot
    cancel_token: CancellationToken
    thread: Thread | None = None


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _failed_file_errors(result: CorpusIndexBatchResult | None) -> list[IndexJobFileError]:
    if result is None:
        return []
    errors = []
    for item in result.results:
        if item.status == 'failed':
            errors.append(
                IndexJobFileError(
                    source_path=item.source_path,
                    message=item.message or item.error_code or 'Falha sem detalhe.',
                    error_code=item.error_code,
                )
            )
    return errors[-100:]


def _chunks_indexed(result: CorpusIndexBatchResult | None) -> int:
    if result is None:
        return 0
    return sum(item.chunks_indexed for item in result.results)


def _eta_seconds(progress: CorpusIndexProgress | None) -> int | None:
    if progress is None or progress.total_found <= 0 or progress.processed_count <= 0:
        return None
    remaining = max(progress.total_found - progress.processed_count, 0)
    if remaining == 0 or progress.elapsed_ms <= 0:
        return 0
    per_file_ms = progress.elapsed_ms / progress.processed_count
    return int((remaining * per_file_ms) / 1000)


def _default_runner(
    path: Path,
    *,
    progress: Callable[[CorpusIndexProgress], None],
    cancel_token: CancellationToken,
    runtime: CorpusRuntime | None,
    rebuild: bool = False,
) -> CorpusIndexBatchResult:
    from escolio.tui.actions import index_corpus_folder

    # O runtime antigo mantem as settings da vault em que o job comecou, mesmo apos a troca.
    settings = runtime.settings_snapshot() if runtime is not None else None
    return index_corpus_folder(path, rebuild=rebuild, settings=settings, runtime=runtime, progress=progress, cancel_token=cancel_token)


class IndexJobManager:
    def __init__(self, *, runner: IndexJobRunner | None = None) -> None:
        self._runner = runner or _default_runner
        self._lock = Lock()
        self._jobs: dict[str, _JobState] = {}
        self._active_job_id: str | None = None

    def start(self, folder_path: Path | str, *, rebuild: bool = False, runtime: CorpusRuntime | None = None) -> IndexJobSnapshot:
        path = Path(folder_path).expanduser()
        with self._lock:
            if self._active_job_id is not None:
                active = self._jobs.get(self._active_job_id)
                if active and active.thread and active.thread.is_alive():
                    raise IndexJobAlreadyRunningError(f'Ja existe job ativo: {self._active_job_id}')
                self._active_job_id = None

            job_id = f'idx-{uuid4().hex[:12]}'
            snapshot = IndexJobSnapshot(
                job_id=job_id,
                status='running',
                source_path=str(path),
                started_at=_now(),
                message='Indexação iniciada.',
            )
            state = _JobState(snapshot=snapshot, cancel_token=CancellationToken())
            thread = Thread(target=self._run, args=(job_id, path, rebuild, runtime), name=f'index-job-{job_id}', daemon=True)
            state.thread = thread
            self._jobs[job_id] = state
            self._active_job_id = job_id
            thread.start()
            return snapshot.model_copy(deep=True)

    def get(self, job_id: str) -> IndexJobSnapshot:
        with self._lock:
            state = self._jobs.get(job_id)
            if state is None:
                raise KeyError(f'Job nao encontrado: {job_id}')
            return state.snapshot.model_copy(deep=True)

    def cancel(self, job_id: str) -> IndexJobSnapshot:
        with self._lock:
            state = self._jobs.get(job_id)
            if state is None:
                raise KeyError(f'Job nao encontrado: {job_id}')
            state.cancel_token.cancel()
            state.snapshot.cancel_requested = True
            state.snapshot.message = 'Cancelamento solicitado.'
            return state.snapshot.model_copy(deep=True)

    def _update_progress(self, job_id: str, progress: CorpusIndexProgress) -> None:
        with self._lock:
            state = self._jobs.get(job_id)
            if state is None:
                return
            state.snapshot.progress = progress
            state.snapshot.eta_seconds = _eta_seconds(progress)
            if progress.message:
                state.snapshot.message = progress.message

    def _run(self, job_id: str, path: Path, rebuild: bool, runtime: CorpusRuntime | None) -> None:
        result: CorpusIndexBatchResult | None = None
        started_at = datetime.now(UTC)
        try:
            with corpus_write_lock:
                result = self._runner(
                    path,
                    progress=lambda event: self._update_progress(job_id, event),
                    cancel_token=self._jobs[job_id].cancel_token,
                    runtime=runtime,
                    rebuild=rebuild,
                )
            status = result.status
            message = 'Indexação finalizada.'
            error_code = None
        except Exception as exc:
            status = 'failed'
            message = str(exc)
            error_code = exc.__class__.__name__
        finished_at = datetime.now(UTC)
        elapsed_seconds = max((finished_at - started_at).total_seconds(), 0.001)

        with self._lock:
            state = self._jobs.get(job_id)
            if state is None:
                return
            state.snapshot.status = status
            state.snapshot.finished_at = finished_at.isoformat()
            state.snapshot.result = result
            state.snapshot.error_code = error_code
            state.snapshot.message = message
            state.snapshot.last_errors = _failed_file_errors(result)
            total_files = result.total_found if result else 0
            total_chunks = _chunks_indexed(result)
            state.snapshot.files_per_second = round(total_files / elapsed_seconds, 2) if total_files else 0.0
            state.snapshot.chunks_per_second = round(total_chunks / elapsed_seconds, 2) if total_chunks else 0.0
            state.snapshot.eta_seconds = 0
            if self._active_job_id == job_id:
                self._active_job_id = None

    def is_busy(self) -> bool:
        with self._lock:
            active = self._jobs.get(self._active_job_id) if self._active_job_id else None
            return bool(active and active.thread and active.thread.is_alive())


index_job_manager = IndexJobManager()


def start_index_job(folder_path: Path | str, *, rebuild: bool = False, runtime: CorpusRuntime | None = None) -> IndexJobSnapshot:
    return index_job_manager.start(folder_path, rebuild=rebuild, runtime=runtime)


def get_index_job(job_id: str) -> IndexJobSnapshot:
    return index_job_manager.get(job_id)


def cancel_index_job(job_id: str) -> IndexJobSnapshot:
    return index_job_manager.cancel(job_id)
