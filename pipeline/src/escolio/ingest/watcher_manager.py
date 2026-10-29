from __future__ import annotations

from pathlib import Path
from threading import Lock

from escolio.corpus.dropped import DroppedFileIndexer
from escolio.ingest.watcher import VaultWatcher


class WatcherManager:
    """Gerencia um único VaultWatcher ativo por processo.

    Os resultados (indexed/unchanged/failed/removed) saem pela fila do `DroppedFileIndexer`
    recebido em `start`, o mesmo que a UI já consulta via `pollDroppedFiles`.
    """

    def __init__(self) -> None:
        self._lock = Lock()
        self._watcher: VaultWatcher | None = None

    def start(self, folder_path: Path | str, indexer: DroppedFileIndexer) -> dict:
        path = Path(folder_path).expanduser()
        with self._lock:
            if self._watcher is not None:
                return {
                    "ok": False,
                    "active": True,
                    "directory": str(self._watcher.directory),
                }
            watcher = VaultWatcher(path, indexer=indexer)
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


watcher_manager = WatcherManager()
