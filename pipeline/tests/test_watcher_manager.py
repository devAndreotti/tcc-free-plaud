from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from escolio.ingest.watcher_manager import WatcherManager


def make_fake_watcher(directory: Path) -> MagicMock:
    watcher = MagicMock()
    watcher.directory = directory
    return watcher


def test_status_inactive_by_default() -> None:
    manager = WatcherManager()
    assert manager.status() == {"active": False, "directory": None}


def test_start_activates_watcher_with_shared_indexer(tmp_path: Path) -> None:
    manager = WatcherManager()
    indexer = MagicMock()
    fake_watcher = make_fake_watcher(tmp_path)
    with patch(
        "escolio.ingest.watcher_manager.VaultWatcher", return_value=fake_watcher
    ) as watcher_cls:
        result = manager.start(tmp_path, indexer)

    assert result == {"ok": True, "active": True, "directory": str(tmp_path)}
    assert watcher_cls.call_args.kwargs["indexer"] is indexer
    fake_watcher.start.assert_called_once()
    assert manager.status() == {"active": True, "directory": str(tmp_path)}


def test_start_twice_returns_already_active(tmp_path: Path) -> None:
    manager = WatcherManager()
    fake_watcher = make_fake_watcher(tmp_path)
    with patch(
        "escolio.ingest.watcher_manager.VaultWatcher", return_value=fake_watcher
    ):
        manager.start(tmp_path, MagicMock())
        second = manager.start(tmp_path, MagicMock())

    assert second == {"ok": False, "active": True, "directory": str(tmp_path)}
    fake_watcher.start.assert_called_once()


def test_stop_without_active_watcher_is_noop() -> None:
    manager = WatcherManager()
    assert manager.stop() == {"ok": True, "active": False}


def test_stop_after_start_deactivates(tmp_path: Path) -> None:
    manager = WatcherManager()
    fake_watcher = make_fake_watcher(tmp_path)
    with patch(
        "escolio.ingest.watcher_manager.VaultWatcher", return_value=fake_watcher
    ):
        manager.start(tmp_path, MagicMock())
        result = manager.stop()

    fake_watcher.stop.assert_called_once()
    assert result == {"ok": True, "active": False}
    assert manager.status() == {"active": False, "directory": None}
