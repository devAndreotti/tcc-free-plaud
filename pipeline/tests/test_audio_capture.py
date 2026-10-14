import wave
from threading import Event
from types import SimpleNamespace

import numpy as np
import pytest

from escolio.ingest.audio_capture import AudioCapture
from escolio.ingest.audio_jobs import AudioJobManager
from escolio.ingest.audio_vad import SpeechDetector
from escolio.providers.audio_models import AudioError


@pytest.fixture
def microphone(monkeypatch):
    streams = []

    class Stream:
        def __init__(self, **kwargs):
            self.callback = kwargs["callback"]
            self.closed = False
            streams.append(self)

        def start(self):
            self.callback(
                np.ones((48000, 1), dtype="float32") * 0.5, 48000, None, False
            )

        def stop(self):
            pass

        def close(self):
            self.closed = True

    monkeypatch.setattr(
        "sounddevice.query_devices",
        lambda *args, **kwargs: {"default_samplerate": 48000},
    )
    monkeypatch.setattr("sounddevice.check_input_settings", lambda **kwargs: None)
    monkeypatch.setattr("sounddevice.InputStream", Stream)
    return streams


def capture(path, **kwargs):
    return AudioCapture(path, SpeechDetector(lambda audio: 0.9), **kwargs)


def test_capture_stops_flushes_and_closes_device(tmp_path, microphone):
    recording = capture(tmp_path / "recording.wav")
    recording.start()
    path = recording.stop()
    with wave.open(str(path)) as reader:
        assert reader.getnframes() == 16000
        assert reader.getframerate() == 16000
        assert reader.getnchannels() == 1
    assert recording.samples_written == 16000
    assert recording.regions[-1].end_sample == 16000
    assert microphone[0].closed
    with pytest.raises(AudioError):
        recording.start()


def test_cancel_and_failures_close_stream(tmp_path, microphone, monkeypatch):
    recording = capture(tmp_path / "cancel.wav")
    recording.start()
    recording.cancel()
    assert not recording._thread.is_alive()
    assert microphone[0].closed
    broken = capture(tmp_path / "broken.wav")
    monkeypatch.setattr(
        "sounddevice.query_devices",
        lambda *args, **kwargs: (_ for _ in ()).throw(OSError("No device")),
    )
    with pytest.raises(AudioError) as caught:
        broken.start()
    assert caught.value.code == "AUDIO_DEVICE_UNAVAILABLE"


def test_overflow_is_explicit_and_never_drops_silently(tmp_path):
    recording = capture(tmp_path / "overflow.wav", queue_size=1)
    block = np.ones((100, 1), dtype="float32")
    recording._callback(block, 100, None, False)
    recording._callback(block, 100, None, False)
    assert recording.error_code == "AUDIO_CAPTURE_OVERFLOW"
    with pytest.raises(AudioError):
        recording.stop()
    recording = capture(tmp_path / "status.wav")
    recording._callback(block, 100, None, "input overflow")
    assert recording.error_code == "AUDIO_CAPTURE_OVERFLOW"


def test_capture_never_overwrites_and_reports_write_failure(
    tmp_path, microphone, monkeypatch
):
    path = tmp_path / "source.wav"
    path.write_bytes(b"original")
    with pytest.raises(AudioError):
        capture(path).start()
    assert path.read_bytes() == b"original"
    recording = capture(tmp_path / "disk-full.wav")
    monkeypatch.setattr(
        recording, "_append", lambda *args: (_ for _ in ()).throw(OSError("Disk full"))
    )
    recording.start()
    with pytest.raises(AudioError):
        recording.stop()
    assert recording.error_code == "AUDIO_CAPTURE_FAILED"
    assert microphone[-1].closed
    with pytest.raises(AudioError):
        capture(tmp_path / "not-started.wav").stop()


def test_job_queue_transcribes_only_after_stop(tmp_path, microphone):
    calls = []
    completed = Event()

    def transcribe(path, options, cancel):
        calls.append(path)
        completed.set()

    runtime = SimpleNamespace(
        root=tmp_path,
        store=SimpleNamespace(require=lambda model: tmp_path),
        prepare=lambda options: None,
        detector=lambda: SpeechDetector(lambda audio: 0.9),
        transcribe_result=transcribe,
    )
    manager = AudioJobManager(runtime)
    try:
        job = manager.start()
        assert calls == []
        assert manager.get(job.job_id).status == "recording"
        with pytest.raises(AudioError):
            manager.start()
        manager.stop(job.job_id)
        manager._future.result(timeout=5)
        assert completed.is_set()
        assert manager.get(job.job_id).status == "completed"
        with pytest.raises(AudioError):
            manager.get("missing")
        new = manager.start()
        assert manager.cancel(new.job_id).status == "cancelled"
        assert len(calls) == 1
    finally:
        manager.close()
