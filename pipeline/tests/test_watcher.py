import time
from pathlib import Path

from free_plaud.ingest.models import IngestionResult
from free_plaud.ingest.watcher import VaultWatcher, discover_files


def test_discover_files_lists_only_files(tmp_path: Path) -> None:
    (tmp_path / "note.txt").write_text("conteudo", encoding="utf-8")
    (tmp_path / "subdir").mkdir()

    files = discover_files(tmp_path)

    assert [f.name for f in files] == ["note.txt"]


def test_discover_files_returns_empty_for_missing_directory(tmp_path: Path) -> None:
    missing = tmp_path / "missing"

    assert discover_files(missing) == []


def test_vault_watcher_ingests_new_file(tmp_path: Path) -> None:
    results: list[IngestionResult] = []
    watcher = VaultWatcher(tmp_path, on_ingested=results.append)

    with watcher:
        (tmp_path / "novo.txt").write_text("conteudo monitorado", encoding="utf-8")

        deadline = time.monotonic() + 5
        while not results and time.monotonic() < deadline:
            time.sleep(0.1)

    assert len(results) == 1
    assert results[0].status == "success"
    assert results[0].source_type == "txt"


def test_vault_watcher_start_creates_directory(tmp_path: Path) -> None:
    target = tmp_path / "vault_novo"
    watcher = VaultWatcher(target, on_ingested=lambda _result: None)

    try:
        watcher.start()
        assert target.exists()
    finally:
        watcher.stop()


def test_vault_watcher_start_is_idempotent(tmp_path: Path) -> None:
    watcher = VaultWatcher(tmp_path, on_ingested=lambda _result: None)

    try:
        watcher.start()
        watcher.start()
    finally:
        watcher.stop()
