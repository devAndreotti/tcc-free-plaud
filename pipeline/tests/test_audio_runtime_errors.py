from threading import Event
from types import SimpleNamespace

import numpy as np
import pytest

from free_plaud.providers.audio_models import AudioError, AudioOptions
from free_plaud.providers.audio_runtime import AudioRuntime


@pytest.fixture
def runtime(tmp_path, monkeypatch):
    source = tmp_path / "audio.wav"
    source.write_bytes(b"original")
    runtime = AudioRuntime(tmp_path / "results")
    engine = SimpleNamespace(device="cpu", warnings=[], transcribe=lambda *args: [])
    monkeypatch.setattr(runtime, "_engine", lambda _: engine)
    monkeypatch.setattr(
        "free_plaud.ingest.audio_dsp.decode_audio", lambda _: np.zeros(16000)
    )
    return runtime, source, engine


def test_silence_records_no_inference_device(runtime, monkeypatch):
    instance, source, engine = runtime
    monkeypatch.setattr(
        instance, "detector", lambda: SimpleNamespace(process=lambda *a, **kw: [])
    )
    engine.transcribe = lambda *args: pytest.fail("Silent audio must not invoke STT")
    result = instance.transcribe_result(source)
    assert result.device == "none"
    assert result.segments == [] and result.text == ""
    assert result.warnings == ["No speech detected."]


def test_empty_and_cancelled_audio_do_not_publish(runtime, monkeypatch):
    instance, source, _ = runtime
    cancel = Event()
    cancel.set()
    with pytest.raises(AudioError, match="cancelled"):
        instance.transcribe_result(source, AudioOptions(vad=False), cancel=cancel)
    monkeypatch.setattr(
        "free_plaud.ingest.audio_dsp.decode_audio", lambda _: np.zeros(0)
    )
    with pytest.raises(AudioError, match="no samples"):
        instance.transcribe_result(source)
    assert not (instance.root / "transcripts").exists()


def test_changed_source_does_not_publish(runtime):
    instance, source, engine = runtime

    def transcribe(*args):
        source.write_bytes(b"replaced")
        return []

    engine.transcribe = transcribe
    with pytest.raises(AudioError, match="changed"):
        instance.transcribe_result(source, AudioOptions(vad=False))
    assert not (instance.root / "transcripts").exists()


def test_model_prepare_reuses_engine_without_native_loading(tmp_path, monkeypatch):
    instance = AudioRuntime(tmp_path)
    monkeypatch.setattr(instance.store, "require", lambda _: tmp_path)
    options = AudioOptions(device="cpu")
    instance.prepare(options)
    assert instance._engine(options) is instance._engine(options)
    assert instance._engine(options).model is None


def test_missing_cuda_dll_allows_single_cpu_retry(tmp_path, monkeypatch):
    from free_plaud.providers import audio_engines

    monkeypatch.setattr("ctranslate2.get_cuda_device_count", lambda: 1)
    monkeypatch.setattr(
        audio_engines,
        "prepare_native_libraries",
        lambda _: (_ for _ in ()).throw(OSError("missing DLL")),
    )
    model = SimpleNamespace(transcribe=lambda *args, **kw: ([], None))
    calls = []

    def load(*args, **kwargs):
        calls.append(kwargs)
        return model

    monkeypatch.setattr("faster_whisper.WhisperModel", load)
    engine = audio_engines.WhisperEngine(tmp_path, "auto")
    assert engine.transcribe(np.zeros(16000), "pt") == []
    assert engine.device == "cpu" and len(engine.warnings) == 1
    assert len(calls) == 1 and calls[0]["compute_type"] == "int8"
