from __future__ import annotations

from pathlib import Path
from threading import Event
from time import monotonic, sleep

import pytest

from free_plaud.corpus.jobs import IndexJobAlreadyRunningError, IndexJobManager
from free_plaud.corpus.models import CorpusIndexBatchResult, CorpusIndexProgress, CorpusIndexResult


def _wait_until(predicate, *, timeout: float = 1.0) -> None:  # noqa: ANN001
    deadline = monotonic() + timeout
    while monotonic() < deadline:
        if predicate():
            return
        sleep(0.01)
    raise AssertionError('condition not reached before timeout')


def _batch_result(path: Path, *, status: str = 'success') -> CorpusIndexBatchResult:
    result_status = 'failed' if status == 'failed' else 'success'
    return CorpusIndexBatchResult(
        source_path=str(path),
        recursive=True,
        status=status,  # type: ignore[arg-type]
        total_found=1,
        indexed_count=1 if status == 'success' else 0,
        failed_count=1 if status == 'failed' else 0,
        skipped_count=0,
        results=[
            CorpusIndexResult(
                source_path=str(path / 'nota.md'),
                status=result_status,
                chunks_indexed=2 if result_status == 'success' else 0,
                message='Falha simulada.' if result_status == 'failed' else None,
            )
        ],
    )


def test_index_job_returns_job_id_and_progress(tmp_path: Path) -> None:
    started = Event()
    release = Event()

    def runner(path, *, progress, cancel_token, runtime, rebuild=False):  # noqa: ANN001, ANN202, ARG001, FBT002
        progress(CorpusIndexProgress(phase='discovering', current_path=str(path), total_found=3, processed_count=1))
        started.set()
        release.wait(timeout=1)
        return _batch_result(path)

    manager = IndexJobManager(runner=runner)

    snapshot = manager.start(tmp_path)
    assert snapshot.job_id
    assert snapshot.status == 'running'

    assert started.wait(timeout=1)
    running = manager.get(snapshot.job_id)
    assert running.progress is not None
    assert running.progress.total_found == 3
    assert running.progress.processed_count == 1

    release.set()
    _wait_until(lambda: manager.get(snapshot.job_id).status == 'success')
    finished = manager.get(snapshot.job_id)
    assert finished.result is not None
    assert finished.result.indexed_count == 1
    assert finished.files_per_second >= 0
    assert finished.chunks_per_second >= 0


def test_index_job_cancel_sets_token_and_returns_cancelled_snapshot(tmp_path: Path) -> None:
    started = Event()

    def runner(path, *, progress, cancel_token, runtime, rebuild=False):  # noqa: ANN001, ANN202, ARG001, FBT002
        started.set()
        _wait_until(cancel_token.is_cancelled)
        progress(CorpusIndexProgress(phase='cancelled', current_path=str(path), total_found=1, processed_count=0))
        return _batch_result(path, status='cancelled')

    manager = IndexJobManager(runner=runner)
    snapshot = manager.start(tmp_path)
    assert started.wait(timeout=1)

    cancelling = manager.cancel(snapshot.job_id)
    assert cancelling.cancel_requested is True

    _wait_until(lambda: manager.get(snapshot.job_id).status == 'cancelled')
    cancelled = manager.get(snapshot.job_id)
    assert cancelled.cancel_requested is True
    assert cancelled.progress is not None
    assert cancelled.progress.phase == 'cancelled'


def test_second_index_job_while_active_fails_clearly(tmp_path: Path) -> None:
    started = Event()
    release = Event()

    def runner(path, *, progress, cancel_token, runtime, rebuild=False):  # noqa: ANN001, ANN202, ARG001, FBT002
        started.set()
        release.wait(timeout=1)
        return _batch_result(path)

    manager = IndexJobManager(runner=runner)
    first = manager.start(tmp_path)
    assert started.wait(timeout=1)

    with pytest.raises(IndexJobAlreadyRunningError, match='job ativo'):
        manager.start(tmp_path / 'other')

    release.set()
    _wait_until(lambda: manager.get(first.job_id).status == 'success')


def test_failed_job_keeps_last_file_errors(tmp_path: Path) -> None:
    manager = IndexJobManager(runner=lambda path, **_: _batch_result(path, status='failed'))
    snapshot = manager.start(tmp_path)

    _wait_until(lambda: manager.get(snapshot.job_id).status == 'failed')
    failed = manager.get(snapshot.job_id)

    assert failed.last_errors
    assert failed.last_errors[0].source_path.endswith('nota.md')
    assert failed.last_errors[0].message == 'Falha simulada.'
