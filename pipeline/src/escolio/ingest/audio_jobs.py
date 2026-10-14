"""One microphone session and one queued transcription per manager."""

from concurrent.futures import Future, ThreadPoolExecutor
from pathlib import Path
from threading import Event, Lock
from uuid import uuid4

from pydantic import BaseModel

from escolio.providers.audio_models import (
    AudioError,
    AudioOptions,
    TranscriptionResult,
)


class AudioJobSnapshot(BaseModel):
    job_id: str
    status: str
    source_path: Path
    samples_captured: int = 0
    error_code: str | None = None
    message: str | None = None
    result: TranscriptionResult | None = None


class AudioJobManager:
    def __init__(self, runtime):
        self.runtime = runtime
        self._lock = Lock()
        self._executor = ThreadPoolExecutor(
            max_workers=1, thread_name_prefix="audio-stt"
        )
        self._capture = None
        self._snapshot: AudioJobSnapshot | None = None
        self._future: Future | None = None
        self._cancel = Event()
        self._options = AudioOptions()

    def start(
        self, options: AudioOptions | None = None, *, device: int | str | None = None
    ) -> AudioJobSnapshot:
        from escolio.ingest.audio_capture import AudioCapture

        with self._lock:
            if self._snapshot and self._snapshot.status in (
                "recording",
                "queued",
                "transcribing",
            ):
                raise AudioError("AUDIO_JOB_BUSY", "An audio job is already active.")
            if self._future is not None and not self._future.done():
                raise AudioError(
                    "AUDIO_JOB_BUSY", "Previous transcription is still stopping."
                )
            self._options = options or AudioOptions()
            self.runtime.prepare(self._options)
            job_id = uuid4().hex
            path = self.runtime.root / "recordings" / f"{job_id}.wav"
            capture = AudioCapture(path, self.runtime.detector(), device=device)
            capture.start()
            self._capture = capture
            self._cancel = Event()
            self._future = None
            self._snapshot = AudioJobSnapshot(
                job_id=job_id, status="recording", source_path=path
            )
            return self._snapshot.model_copy(deep=True)

    def _checked(self, job_id: str) -> AudioJobSnapshot:
        if self._snapshot is None or job_id != self._snapshot.job_id:
            raise AudioError("AUDIO_JOB_UNKNOWN", "Unknown audio job.")
        return self._snapshot

    def get(self, job_id: str) -> AudioJobSnapshot:
        with self._lock:
            snapshot = self._checked(job_id)
            if self._capture:
                snapshot.samples_captured = self._capture.samples_written
                if self._capture.error:
                    self._capture.cancel()
                    snapshot.status = "failed"
                    snapshot.error_code = self._capture.error_code
                    snapshot.message = self._capture.error
            return snapshot.model_copy(deep=True)

    def stop(self, job_id: str) -> AudioJobSnapshot:
        with self._lock:
            snapshot = self._checked(job_id)
            if snapshot.status != "recording":
                if snapshot.status == "failed" and self._capture:
                    self._capture.cancel()
                return snapshot.model_copy(deep=True)
            try:
                path = self._capture.stop()
            except AudioError as exc:
                snapshot.status, snapshot.error_code, snapshot.message = (
                    "failed",
                    exc.code,
                    str(exc),
                )
            else:
                snapshot.status = "queued"
                self._future = self._executor.submit(self._transcribe, path)
            return snapshot.model_copy(deep=True)

    def _transcribe(self, path: Path) -> None:
        with self._lock:
            if self._cancel.is_set():
                return
            self._snapshot.status = "transcribing"
        try:
            result = self.runtime.transcribe_result(
                path, self._options, cancel=self._cancel
            )
        except Exception as exc:
            with self._lock:
                if not self._cancel.is_set():
                    self._snapshot.status = "failed"
                    self._snapshot.error_code = getattr(
                        exc, "code", "AUDIO_TRANSCRIPTION_FAILED"
                    )
                    self._snapshot.message = str(exc)
        else:
            with self._lock:
                if not self._cancel.is_set():
                    self._snapshot.result, self._snapshot.status = result, "completed"

    def cancel(self, job_id: str) -> AudioJobSnapshot:
        with self._lock:
            snapshot = self._checked(job_id)
            if snapshot.status in ("completed", "failed", "cancelled"):
                return snapshot.model_copy(deep=True)
            self._cancel.set()
            if self._capture:
                self._capture.cancel()
            if self._future:
                self._future.cancel()
            snapshot.status = "cancelled"
            return snapshot.model_copy(deep=True)

    def close(self) -> None:
        if self._snapshot:
            self.cancel(self._snapshot.job_id)
        self._executor.shutdown(wait=True, cancel_futures=True)
