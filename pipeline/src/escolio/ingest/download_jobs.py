"""Background download job for voice models, mirroring IndexJobManager
(corpus/jobs.py): a daemon thread per job, state in an in-process dict,
one active download at a time. The UI polls by job_id instead of blocking
the PyWebView bridge on a multi-hundred-MB download.
"""

from __future__ import annotations

from dataclasses import dataclass
from threading import Lock, Thread
from uuid import uuid4

from pydantic import BaseModel

from escolio.corpus.cancellation import CancellationToken
from escolio.providers.audio_catalog import ModelStore
from escolio.providers.audio_models import AudioError

DownloadJobStatus = str


class DownloadJobSnapshot(BaseModel):
    job_id: str
    model_id: str
    status: DownloadJobStatus
    bytes_completed: int = 0
    bytes_total: int = 0
    error_code: str | None = None
    message: str | None = None


class _DownloadCancelled(Exception):
    """Raised from inside the progress callback to unwind ModelStore.download."""


@dataclass
class _JobState:
    snapshot: DownloadJobSnapshot
    cancel_token: CancellationToken
    thread: Thread | None = None


class DownloadJobManager:
    def __init__(self, store: ModelStore) -> None:
        self.store = store
        self._lock = Lock()
        self._jobs: dict[str, _JobState] = {}
        self._active_job_id: str | None = None

    def start(self, model_id: str) -> DownloadJobSnapshot:
        with self._lock:
            self.store.model(model_id)  # levanta AUDIO_MODEL_UNKNOWN se invalido
            if self._active_job_id is not None:
                active = self._jobs.get(self._active_job_id)
                if active and active.thread and active.thread.is_alive():
                    raise AudioError("AUDIO_DOWNLOAD_BUSY", "Ja existe um download de modelo em andamento.")
                self._active_job_id = None

            job_id = f"dl-{uuid4().hex[:12]}"
            snapshot = DownloadJobSnapshot(job_id=job_id, model_id=model_id, status="downloading")
            state = _JobState(snapshot=snapshot, cancel_token=CancellationToken())
            thread = Thread(target=self._run, args=(job_id, model_id), name=f"model-download-{job_id}", daemon=True)
            state.thread = thread
            self._jobs[job_id] = state
            self._active_job_id = job_id
            thread.start()
            return snapshot.model_copy(deep=True)

    def get(self, job_id: str) -> DownloadJobSnapshot:
        with self._lock:
            state = self._jobs.get(job_id)
            if state is None:
                raise KeyError(f"Job de download nao encontrado: {job_id}")
            return state.snapshot.model_copy(deep=True)

    def cancel(self, job_id: str) -> DownloadJobSnapshot:
        with self._lock:
            state = self._jobs.get(job_id)
            if state is None:
                raise KeyError(f"Job de download nao encontrado: {job_id}")
            state.cancel_token.cancel()
            return state.snapshot.model_copy(deep=True)

    def _update_progress(self, job_id: str, completed: int, total: int) -> None:
        with self._lock:
            state = self._jobs.get(job_id)
            if state is None:
                return
            state.snapshot.bytes_completed = completed
            state.snapshot.bytes_total = total

    def _run(self, job_id: str, model_id: str) -> None:
        state = self._jobs[job_id]

        def on_progress(_model_id: str, completed: int, total: int) -> None:
            self._update_progress(job_id, completed, total)
            if state.cancel_token.is_cancelled():
                # ponytail: cancelamento so entre arquivos do manifesto, nao no
                # meio de um hf_hub_download em andamento - upgrade exigiria
                # mudar a assinatura de ModelStore.download.
                raise _DownloadCancelled()

        try:
            self.store.download(model_id, progress=on_progress)
        except _DownloadCancelled:
            with self._lock:
                state.snapshot.status = "cancelled"
                state.snapshot.message = "Download cancelado."
        except AudioError as exc:
            with self._lock:
                state.snapshot.status = "failed"
                state.snapshot.error_code = exc.code
                state.snapshot.message = str(exc)
        except Exception as exc:
            with self._lock:
                state.snapshot.status = "failed"
                state.snapshot.error_code = exc.__class__.__name__
                state.snapshot.message = str(exc)
        else:
            with self._lock:
                state.snapshot.status = "verifying"
            ok = self.store.verify(model_id)
            with self._lock:
                if ok:
                    state.snapshot.status = "completed"
                    state.snapshot.message = "Modelo baixado e verificado."
                else:
                    state.snapshot.status = "failed"
                    state.snapshot.error_code = "AUDIO_HASH_MISMATCH"
                    state.snapshot.message = "Verificacao pos-download falhou."
        finally:
            with self._lock:
                if self._active_job_id == job_id:
                    self._active_job_id = None
