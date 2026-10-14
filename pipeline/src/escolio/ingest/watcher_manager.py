from __future__ import annotations

from pathlib import Path
from threading import Lock

from escolio.ingest.models import IngestionResult
from escolio.ingest.watcher import VaultWatcher

_MAX_BUFFERED_EVENTS = 100


class WatcherManager:
    """Gerencia um único VaultWatcher ativo por processo e um buffer de eventos.

    O frontend consome eventos via polling (`poll_events`), que drena o buffer.
    """

    def __init__(self) -> None:
        self._lock = Lock()
        self._watcher: VaultWatcher | None = None
        self._events: list[IngestionResult] = []

    def _on_ingested(self, result: IngestionResult) -> None:
        with self._lock:
            self._events.append(result)
            if len(self._events) > _MAX_BUFFERED_EVENTS:
                self._events = self._events[-_MAX_BUFFERED_EVENTS:]

    def start(self, folder_path: Path | str) -> dict:
        path = Path(folder_path).expanduser()
        with self._lock:
            if self._watcher is not None:
                return {
                    "ok": False,
                    "active": True,
                    "directory": str(self._watcher.directory),
                }
            watcher = VaultWatcher(path, on_ingested=self._on_ingested)
            watcher.start()
            self._watcher = watcher
            return {"ok": True, "active": True, "directory": str(path)}

    def stop(self) -> dict:
        with self._lock:
            if self._watcher is None:
                return {"ok": True, "active": False}
            self._watcher.stop()
            self._watcher = None
            return {"ok": True, "active": False}

    def status(self) -> dict:
        with self._lock:
            if self._watcher is None:
                return {"active": False, "directory": None}
            return {"active": True, "directory": str(self._watcher.directory)}

    def poll_events(self) -> list[IngestionResult]:
        with self._lock:
            events = self._events
            self._events = []
            return events


watcher_manager = WatcherManager()
