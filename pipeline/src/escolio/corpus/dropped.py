"""Fila de arquivos soltos na UI: indexa um a um no corpus e guarda o resultado para polling."""

from __future__ import annotations

from collections import deque
from collections.abc import Callable, Iterable
from pathlib import Path
from queue import Queue
from threading import Lock, Thread

from pydantic import BaseModel

from escolio.corpus.jobs import corpus_write_lock
from escolio.corpus.models import CorpusIndexBatchResult
from escolio.corpus.runtime import CorpusRuntime
from escolio.ingest.validators import SUPPORTED_EXTENSIONS
from escolio.notes.service import delete_notes_by_source_path

DroppedFileRunner = Callable[[Path], CorpusIndexBatchResult]
# (caminho, é pasta) -> notas removidas
DroppedFileRemover = Callable[[Path, bool], int]

_MAX_STAGED = 200


class DroppedFileEvent(BaseModel):
    name: str
    source_path: str
    status: str  # indexed | unchanged | failed | removed
    chunks: int = 0
    error_code: str | None = None
    message: str | None = None


class EnqueueResult(BaseModel):
    queued: list[str] = []
    missing: list[str] = []


def _default_runner(runtime: CorpusRuntime | None) -> DroppedFileRunner:
    def run(path: Path) -> CorpusIndexBatchResult:
        from escolio.corpus.service import index_corpus_path

        vector_store = runtime.get_vector_store() if runtime is not None else None
        embedder = runtime.get_embedder() if runtime is not None else None
        return index_corpus_path(path, vector_store=vector_store, embedder=embedder)

    return run


def _default_remover(runtime: CorpusRuntime | None) -> DroppedFileRemover:
    def remove(path: Path, folder: bool) -> int:
        vector_store = runtime.get_vector_store() if runtime is not None else None
        return delete_notes_by_source_path(path, folder=folder, vector_store=vector_store)

    return remove


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

    def __init__(
        self,
        runner: DroppedFileRunner | None = None,
        runtime: CorpusRuntime | None = None,
        remover: DroppedFileRemover | None = None,
    ) -> None:
        self._runner = runner or _default_runner(runtime)
        self._remover = remover or _default_remover(runtime)
        self._lock = Lock()
        self._staged: dict[str, deque[Path]] = {}
        self._staged_order: deque[str] = deque()  # um nome por caminho staged, do mais antigo ao mais novo
        self._events: list[DroppedFileEvent] = []
        self._queue: Queue[Path] = Queue()
        self._worker: Thread | None = None

    def stage(self, paths: list[str]) -> None:
        with self._lock:
            for raw in paths:
                path = Path(raw)
                self._staged.setdefault(path.name, deque()).append(path)
                self._staged_order.append(path.name)
            while len(self._staged_order) > _MAX_STAGED:
                self._pop_staged(self._staged_order.popleft())

    def _pop_staged(self, name: str) -> Path | None:
        queue = self._staged.get(name)
        if not queue:
            return None
        path = queue.popleft()
        if not queue:
            del self._staged[name]
        return path

    def enqueue(self, names: list[str]) -> EnqueueResult:
        result = EnqueueResult()
        with self._lock:
            for name in names:
                path = self._pop_staged(name)
                if path is None:
                    result.missing.append(name)
                    continue
                self._staged_order.remove(name)
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
            self._ensure_worker()
        return result

    def enqueue_paths(self, paths: Iterable[Path]) -> None:
        """Enfileira caminhos já conhecidos (watcher de pasta), sem passar pelo staging.

        Extensões fora de SUPPORTED_EXTENSIONS são ignoradas em silêncio.
        """
        with self._lock:
            for path in paths:
                if path.suffix.lower() in SUPPORTED_EXTENSIONS:
                    self._queue.put(path)
            self._ensure_worker()

    def remove_paths(self, path: Path, *, folder: bool = False) -> int:
        """Remove do corpus as notas do arquivo (ou de tudo sob a pasta) e registra `removed`."""
        with corpus_write_lock:
            removed = self._remover(path, folder)
        if removed:
            with self._lock:
                self._events.append(DroppedFileEvent(name=path.name, source_path=str(path), status='removed'))
        return removed

    def _ensure_worker(self) -> None:
        if self._worker is None or not self._worker.is_alive():
            self._worker = Thread(target=self._drain, name='dropped-file-indexer', daemon=True)
            self._worker.start()

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
