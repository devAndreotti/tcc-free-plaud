from collections.abc import Callable
from pathlib import Path
from threading import Lock
from typing import Self
from uuid import uuid4

from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

from escolio.ingest.models import IngestionResult
from escolio.ingest.service import ingest_file


def discover_files(directory: Path) -> list[Path]:
    """Descobre arquivos em um diretório sem recursão profunda.

    Este helper serve como ponto inicial para um futuro monitor de pasta.
    """
    if not directory.exists():
        return []
    return [path for path in sorted(directory.iterdir()) if path.is_file()]


IngestionCallback = Callable[[IngestionResult], None]


class _IngestHandler(FileSystemEventHandler):
    """Dispara ingestão para arquivos criados/movidos no diretório monitorado."""

    def __init__(self, on_ingested: IngestionCallback, correlation_id: str) -> None:
        self._on_ingested = on_ingested
        self._correlation_id = correlation_id
        self._lock = Lock()

    def _handle_path(self, raw_path: str) -> None:
        path = Path(raw_path)
        if not path.is_file():
            return
        with self._lock:
            result = ingest_file(path, correlation_id=self._correlation_id)
        self._on_ingested(result)

    def on_created(self, event: FileSystemEvent) -> None:
        if not event.is_directory:
            self._handle_path(event.src_path)

    def on_moved(self, event: FileSystemEvent) -> None:
        if not event.is_directory:
            self._handle_path(event.dest_path)


class VaultWatcher:
    """Daemon de monitoramento contínuo de filesystem para auto-ingestão.

    Usa watchdog (inotify/ReadDirectoryChangesW) quando disponível; cai em
    polling automaticamente em filesystems sem suporte nativo.
    """

    def __init__(self, directory: Path, on_ingested: IngestionCallback) -> None:
        self.directory = Path(directory)
        self._on_ingested = on_ingested
        self._correlation_id = f"watch-{uuid4().hex[:12]}"
        self._observer = Observer()
        self._running = False

    def start(self) -> None:
        if self._running:
            return
        self.directory.mkdir(parents=True, exist_ok=True)
        handler = _IngestHandler(self._on_ingested, self._correlation_id)
        self._observer.schedule(handler, str(self.directory), recursive=False)
        self._observer.start()
        self._running = True

    def stop(self) -> None:
        if not self._running:
            return
        self._observer.stop()
        self._observer.join(timeout=5)
        self._running = False

    def __enter__(self) -> Self:
        self.start()
        return self

    def __exit__(self, *_exc_info: object) -> None:
        self.stop()
