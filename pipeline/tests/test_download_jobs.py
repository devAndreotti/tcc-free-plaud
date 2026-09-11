from __future__ import annotations

from pathlib import Path
from threading import Event
from time import monotonic, sleep

import pytest

from free_plaud.ingest.download_jobs import DownloadJobManager
from free_plaud.providers.audio_catalog import ModelFile, ModelStore, VoiceModel
from free_plaud.providers.audio_models import AudioError


def _wait_until(predicate, *, timeout: float = 1.0) -> None:
    deadline = monotonic() + timeout
    while monotonic() < deadline:
        if predicate():
            return
        sleep(0.01)
    raise AssertionError('condition not reached before timeout')


def _fake_model(model_id: str = 'fake-model') -> VoiceModel:
    return VoiceModel(
        id=model_id,
        engine='faster-whisper',
        format='ctranslate2',
        repo_id='org/fake-model',
        revision='a' * 40,
        languages=['pt', 'en'],
        license='MIT',
        files=[ModelFile(path='config.json', size=1000, sha256='b' * 64)],
    )


def _store(tmp_path: Path) -> ModelStore:
    model = _fake_model()
    return ModelStore(tmp_path / 'models', catalog={model.id: model})


def test_download_job_reports_progress_and_completes(tmp_path: Path) -> None:
    store = _store(tmp_path)
    started = Event()
    release = Event()

    def fake_download(model_id, *, progress=None):
        started.set()
        release.wait(timeout=1)
        if progress:
            progress(model_id, 500, 1000)
        return store.directory(model_id)

    store.download = fake_download  # type: ignore[method-assign]
    store.verify = lambda model_id: True  # type: ignore[method-assign]

    manager = DownloadJobManager(store)
    snapshot = manager.start('fake-model')
    assert snapshot.job_id
    assert snapshot.status == 'downloading'
    assert started.wait(timeout=1)

    release.set()
    _wait_until(lambda: manager.get(snapshot.job_id).status == 'completed')
    finished = manager.get(snapshot.job_id)
    assert finished.bytes_completed == 500
    assert finished.bytes_total == 1000


def test_download_job_failed_verification_after_download(tmp_path: Path) -> None:
    store = _store(tmp_path)
    store.download = lambda model_id, *, progress=None: store.directory(model_id)  # type: ignore[method-assign]
    store.verify = lambda model_id: False  # type: ignore[method-assign]

    manager = DownloadJobManager(store)
    snapshot = manager.start('fake-model')

    _wait_until(lambda: manager.get(snapshot.job_id).status == 'failed')
    failed = manager.get(snapshot.job_id)
    assert failed.error_code == 'AUDIO_HASH_MISMATCH'


def test_download_job_cancel_stops_between_files(tmp_path: Path) -> None:
    store = _store(tmp_path)
    started = Event()

    def fake_download(model_id, *, progress=None):
        started.set()
        # A checagem de cancelamento roda dentro do callback progress()
        # (injetado pela manager) - chamar repetidamente simula o
        # ModelStore.download real, que chama progress() entre arquivos.
        for _ in range(100):
            if progress:
                progress(model_id, 0, 1000)
            sleep(0.01)
        return store.directory(model_id)

    store.download = fake_download  # type: ignore[method-assign]
    store.verify = lambda model_id: True  # type: ignore[method-assign]

    manager = DownloadJobManager(store)
    snapshot = manager.start('fake-model')
    assert started.wait(timeout=1)

    manager.cancel(snapshot.job_id)
    _wait_until(lambda: manager.get(snapshot.job_id).status == 'cancelled')


def test_download_job_reports_audio_error_from_store(tmp_path: Path) -> None:
    store = _store(tmp_path)

    def fake_download(model_id, *, progress=None):
        raise AudioError('AUDIO_UNSAFE_PATH', 'Model destination escapes storage root.')

    store.download = fake_download  # type: ignore[method-assign]

    manager = DownloadJobManager(store)
    snapshot = manager.start('fake-model')

    _wait_until(lambda: manager.get(snapshot.job_id).status == 'failed')
    failed = manager.get(snapshot.job_id)
    assert failed.error_code == 'AUDIO_UNSAFE_PATH'


def test_second_download_while_active_fails_clearly(tmp_path: Path) -> None:
    store = _store(tmp_path)
    started = Event()
    release = Event()

    def fake_download(model_id, *, progress=None):
        started.set()
        release.wait(timeout=1)
        return store.directory(model_id)

    store.download = fake_download  # type: ignore[method-assign]
    store.verify = lambda model_id: True  # type: ignore[method-assign]

    manager = DownloadJobManager(store)
    manager.start('fake-model')
    assert started.wait(timeout=1)

    with pytest.raises(AudioError, match='Ja existe um download'):
        manager.start('fake-model')

    release.set()


def test_download_job_get_and_cancel_reject_unknown_job(tmp_path: Path) -> None:
    manager = DownloadJobManager(_store(tmp_path))

    with pytest.raises(KeyError):
        manager.get('nao-existe')
    with pytest.raises(KeyError):
        manager.cancel('nao-existe')


def test_download_job_start_rejects_unknown_model(tmp_path: Path) -> None:
    manager = DownloadJobManager(_store(tmp_path))

    with pytest.raises(AudioError):
        manager.start('modelo-inexistente')
