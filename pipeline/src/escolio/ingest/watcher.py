import logging
import time
from dataclasses import dataclass
from pathlib import Path
from threading import Event, Lock, Thread
from typing import Self

from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

from escolio.app.config import get_settings
from escolio.corpus.discovery import _is_ignored_dir, discover_corpus_files
from escolio.corpus.dropped import DroppedFileIndexer

logger = logging.getLogger("escolio.ingest")

DEFAULT_DEBOUNCE_SECONDS = 1.5
_INDEX = "index"
_REMOVE = "remove"


def discover_files(directory: Path) -> list[Path]:
    """Descobre arquivos em um diretório sem recursão profunda.

    Este helper serve como ponto inicial para um futuro monitor de pasta.
    """
    if not directory.exists():
        return []
    return [path for path in sorted(directory.iterdir()) if path.is_file()]


@dataclass
class _Pending:
    deadline: float
    action: str  # index | remove
    is_dir: bool


class _WatchHandler(FileSystemEventHandler):
    """Traduz eventos do watchdog em ações de indexação ou remoção."""

    def __init__(self, watcher: "VaultWatcher") -> None:
        self._watcher = watcher

    def on_created(self, event: FileSystemEvent) -> None:
        self._watcher._schedule(event.src_path, _INDEX, event.is_directory)

    def on_modified(self, event: FileSystemEvent) -> None:
        if not event.is_directory:
            self._watcher._schedule(event.src_path, _INDEX, False)

    def on_moved(self, event: FileSystemEvent) -> None:
        self._watcher._schedule(event.src_path, _REMOVE, event.is_directory)
        self._watcher._schedule(event.dest_path, _INDEX, event.is_directory)

    def on_deleted(self, event: FileSystemEvent) -> None:
        self._watcher._schedule(event.src_path, _REMOVE, event.is_directory)


class VaultWatcher:
    """Mantém o corpus em dia com uma pasta: criar/editar indexa, apagar/renomear remove.

    Eventos do mesmo caminho são juntados e só processados após o debounce. Tudo passa pelo
    `DroppedFileIndexer` recebido, que é a única fila de escrita do app.
    """

    def __init__(
        self,
        directory: Path,
        *,
        indexer: DroppedFileIndexer,
        recursive: bool | None = None,
        debounce_seconds: float = DEFAULT_DEBOUNCE_SECONDS,
    ) -> None:
        self.directory = Path(directory)
        self.recursive = get_settings().corpus_recursive_default if recursive is None else recursive
        self._indexer = indexer
        self._debounce = debounce_seconds
        self._observer = Observer()
        self._pending: dict[str, _Pending] = {}
        self._pending_lock = Lock()
        self._stop_event = Event()
        self._worker: Thread | None = None
        self._running = False

    def start(self) -> None:
        if self._running:
            return
        self.directory.mkdir(parents=True, exist_ok=True)
        self._stop_event.clear()
        self._worker = Thread(target=self._process_loop, name="vault-watcher", daemon=True)
        self._worker.start()
        self._observer.schedule(_WatchHandler(self), str(self.directory), recursive=self.recursive)
        self._observer.start()
        self._running = True

    def stop(self) -> None:
        if not self._running:
            return
        self._observer.stop()
        self._observer.join(timeout=5)
        self._stop_event.set()
        if self._worker is not None:
            self._worker.join(timeout=5)
        self._running = False

    def __enter__(self) -> Self:
        self.start()
        return self

    def __exit__(self, *_exc_info: object) -> None:
        self.stop()

    def _schedule(self, raw_path: str, action: str, is_dir: bool) -> None:
        with self._pending_lock:
            self._pending[raw_path] = _Pending(time.monotonic() + self._debounce, action, is_dir)

    def _process_loop(self) -> None:
        while not self._stop_event.wait(0.05):
            self._flush_due(time.monotonic())

    def _flush_due(self, now: float) -> None:
        with self._pending_lock:
            due = [(raw, pending) for raw, pending in self._pending.items() if pending.deadline <= now]
            for raw, _ in due:
                del self._pending[raw]
        for raw, pending in due:
            try:
                self._apply(Path(raw), pending)
            except Exception:  # um arquivo ruim não pode derrubar o monitor
                logger.exception("watcher.apply_failed path=%s", raw)

    def _apply(self, path: Path, pending: _Pending) -> None:
        if pending.action == _REMOVE:
            self._indexer.remove_paths(path, folder=pending.is_dir)
            return
        if self._is_ignored(path):
            return
        if pending.is_dir:
            if path.is_dir():
                self._indexer.enqueue_paths(discover_corpus_files(path, recursive=self.recursive).files)
            return
        if path.is_file():
            self._indexer.enqueue_paths([path])

    def _is_ignored(self, path: Path) -> bool:
        try:
            relative = path.relative_to(self.directory)
        except ValueError:
            return True
        return any(
            _is_ignored_dir(self.directory.joinpath(*relative.parts[:depth]))
            for depth in range(1, len(relative.parts) + 1)
        )
