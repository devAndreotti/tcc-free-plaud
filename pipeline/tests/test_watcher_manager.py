from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from escolio.ingest.models import IngestionResult
from escolio.ingest.watcher_manager import WatcherManager


def make_result(status: str = "success") -> IngestionResult:
    return IngestionResult(
        ingestion_id="ing-1",
        correlation_id="corr-1",
        source_path=Path("nota.md"),
        status=status,
    )


def make_fake_watcher(directory: Path) -> MagicMock:
    watcher = MagicMock()
    watcher.directory = directory
    return watcher


def test_status_inactive_by_default() -> None:
    manager = WatcherManager()
    assert manager.status() == {"active": False, "directory": None}


def test_poll_events_empty_by_default() -> None:
    manager = WatcherManager()
    assert manager.poll_events() == []


def test_start_activates_watcher(tmp_path: Path) -> None:
    manager = WatcherManager()
    fake_watcher = make_fake_watcher(tmp_path)
    with patch(
        "escolio.ingest.watcher_manager.VaultWatcher", return_value=fake_watcher
    ):
        result = manager.start(tmp_path)

    assert result == {"ok": True, "active": True, "directory": str(tmp_path)}
    fake_watcher.start.assert_called_once()
    assert manager.status() == {"active": True, "directory": str(tmp_path)}


def test_start_twice_returns_already_active(tmp_path: Path) -> None:
    manager = WatcherManager()
    fake_watcher = make_fake_watcher(tmp_path)
    with patch(
        "escolio.ingest.watcher_manager.VaultWatcher", return_value=fake_watcher
    ):
        manager.start(tmp_path)
        second = manager.start(tmp_path)

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
        manager.start(tmp_path)
        result = manager.stop()

    fake_watcher.stop.assert_called_once()
    assert result == {"ok": True, "active": False}
    assert manager.status() == {"active": False, "directory": None}


def test_on_ingested_buffers_and_drains_events(tmp_path: Path) -> None:
    manager = WatcherManager()
    manager._on_ingested(make_result())
    manager._on_ingested(make_result())

    drained = manager.poll_events()
    assert len(drained) == 2
    assert manager.poll_events() == []


def test_on_ingested_caps_buffer_size(tmp_path: Path) -> None:
    manager = WatcherManager()
    for _ in range(150):
        manager._on_ingested(make_result())

    assert len(manager.poll_events()) == 100
