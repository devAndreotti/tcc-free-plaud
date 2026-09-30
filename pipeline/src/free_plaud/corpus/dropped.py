"""Fila de arquivos soltos na UI: indexa um a um no corpus e guarda o resultado para polling."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from queue import Queue
from threading import Lock, Thread

from pydantic import BaseModel

from free_plaud.corpus.jobs import corpus_write_lock
from free_plaud.corpus.models import CorpusIndexBatchResult
from free_plaud.corpus.runtime import CorpusRuntime
from free_plaud.ingest.validators import SUPPORTED_EXTENSIONS

DroppedFileRunner = Callable[[Path], CorpusIndexBatchResult]

_MAX_STAGED = 200


class DroppedFileEvent(BaseModel):
    name: str
    source_path: str
    status: str  # indexed | unchanged | failed
    chunks: int = 0
    error_code: str | None = None
    message: str | None = None


class EnqueueResult(BaseModel):
    queued: list[str] = []
    missing: list[str] = []


def _default_runner(runtime: CorpusRuntime | None) -> DroppedFileRunner:
    def run(path: Path) -> CorpusIndexBatchResult:
        from free_plaud.corpus.service import index_corpus_path

        vector_store = runtime.get_vector_store() if runtime is not None else None
        embedder = runtime.get_embedder() if runtime is not None else None
        return index_corpus_path(path, vector_store=vector_store, embedder=embedder)

    return run


def _event_from_result(path: Path, result: CorpusIndexBatchResult) -> DroppedFileEvent:
    item = result.results[0] if result.results else None
    if item is not None and item.status == 'success':
        return DroppedFileEvent(name=path.name, source_path=str(path), status='indexed', chunks=item.chunks_indexed)
    if item is not None and item.status == 'unchanged':
        return DroppedFileEvent(name=path.name, source_path=str(path), status='unchanged')
    return DroppedFileEvent(
        name=path.name,
        source_path=str(path),
        status='failed',
        error_code=item.error_code if item else None,
        message=(item.message if item else None) or 'Falha ao indexar.',
    )


class DroppedFileIndexer:
    """Recebe caminhos do handler de drop (Python) e os indexa quando a UI pede pelo nome.

    O pywebview só entrega o caminho completo ao Python; a UI sabe onde o arquivo caiu.
    Por isso o drop só guarda o caminho (`stage`) e a área de soltar confirma (`enqueue`).
    """

    def __init__(self, runner: DroppedFileRunner | None = None, runtime: CorpusRuntime | None = None) -> None:
        self._runner = runner or _default_runner(runtime)
        self._lock = Lock()
        self._staged: dict[str, Path] = {}
        self._events: list[DroppedFileEvent] = []
        self._queue: Queue[Path] = Queue()
        self._worker: Thread | None = None

    def stage(self, paths: list[str]) -> None:
        with self._lock:
            for raw in paths:
                path = Path(raw)
                self._staged[path.name] = path
            while len(self._staged) > _MAX_STAGED:
                self._staged.pop(next(iter(self._staged)))

    def enqueue(self, names: list[str]) -> EnqueueResult:
        result = EnqueueResult()
        with self._lock:
            for name in names:
                path = self._staged.pop(name, None)
                if path is None:
                    result.missing.append(name)
                    continue
                result.queued.append(name)
                if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
                    self._events.append(
                        DroppedFileEvent(
                            name=name,
                            source_path=str(path),
                            status='failed',
                            error_code='UNSUPPORTED_EXTENSION',
                            message=f'Formato {path.suffix or "sem extensão"} não é indexado.',
                        )
                    )
                    continue
                self._queue.put(path)
            if self._worker is None or not self._worker.is_alive():
                self._worker = Thread(target=self._drain, name='dropped-file-indexer', daemon=True)
                self._worker.start()
        return result

    def poll_events(self) -> list[DroppedFileEvent]:
        with self._lock:
            events, self._events = self._events, []
            return events

    def join(self) -> None:
        """Espera a fila esvaziar (usado em testes)."""
        self._queue.join()

    def _drain(self) -> None:
        while True:
            path = self._queue.get()
            try:
                with corpus_write_lock:
                    event = _event_from_result(path, self._runner(path))
            except Exception as exc:  # o worker não pode morrer por um arquivo ruim
                event = DroppedFileEvent(
                    name=path.name,
                    source_path=str(path),
                    status='failed',
                    error_code=exc.__class__.__name__,
                    message=str(exc),
                )
            with self._lock:
                self._events.append(event)
            self._queue.task_done()
