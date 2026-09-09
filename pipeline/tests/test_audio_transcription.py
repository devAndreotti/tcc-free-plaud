from types import SimpleNamespace

import numpy as np
import pytest

from free_plaud.ingest.audio_cleaner import clean_segment
from free_plaud.providers.audio_engines import OnnxEngine, WhisperEngine
from free_plaud.providers.audio_models import (
    AudioError,
    AudioOptions,
    TranscriptSegment,
    TranscriptWord,
)
from free_plaud.providers.audio_runtime import AudioRuntime


def test_cleaner_preserves_raw_words_and_timestamps():
    segment = TranscriptSegment(
        start=12.34,
        end=15.67,
        raw_text="<|pt|> humm, tipo, é importante, né?",
        text="",
        words=[TranscriptWord(start=12.4, end=13, text="humm")],
    )
    cleaned = clean_segment(segment)
    assert cleaned.text == "tipo, é importante, né?"
    assert cleaned.raw_text == segment.raw_text
    assert cleaned.words == segment.words
    assert (cleaned.start, cleaned.end) == (12.34, 15.67)
    assert cleaned.cleaning == ["special_tokens", "isolated_hesitation"]


def test_no_blacklist_deletes_legitimate_speech():
    segment = TranscriptSegment(
        start=0,
        end=3,
        raw_text="Obrigado por assistir. Obrigado por assistir.",
        text="",
    )
    assert clean_segment(segment).text == segment.raw_text
    suspect = segment.model_copy(
        update={"no_speech_probability": 0.9, "average_log_probability": -1.4}
    )
    assert clean_segment(suspect).text == ""
    assert clean_segment(suspect).raw_text == segment.raw_text


def test_whisper_adapter_lazy_load_and_cpu_fallback(monkeypatch, tmp_path):
    calls = []

    class Model:
        def __init__(self, path, **kwargs):
            calls.append(kwargs)
            if kwargs["device"] == "cuda":
                raise RuntimeError("CUDA out of memory")

        def transcribe(self, audio, **kwargs):
            assert kwargs["vad_filter"] is False
            word = SimpleNamespace(start=0, end=0.5, word="Olá", probability=0.9)
            return iter(
                [
                    SimpleNamespace(
                        start=0,
                        end=1,
                        text="Olá",
                        words=[word],
                        no_speech_prob=0.01,
                        avg_logprob=-0.1,
                    )
                ]
            ), None

    monkeypatch.setattr("faster_whisper.WhisperModel", Model)
    monkeypatch.setattr("ctranslate2.get_cuda_device_count", lambda: 1)
    engine = WhisperEngine(tmp_path, "auto")
    assert calls == []
    assert engine.transcribe(np.ones(16000), "pt")[0].words[0].text == "Olá"
    engine.transcribe(np.ones(16000), "pt")
    assert len(calls) == 2
    assert engine.device == "cpu"
    assert engine.warnings
    assert calls[-1]["local_files_only"] is True
    with pytest.raises(RuntimeError):
        WhisperEngine(tmp_path, "cuda").transcribe(np.ones(16000), "pt")


@pytest.mark.parametrize(
    "kind,method", [("sensevoice", "from_sense_voice"), ("moonshine", "from_moonshine")]
)
def test_onnx_adapters_preserve_region_extent(monkeypatch, tmp_path, kind, method):
    class Stream:
        result = SimpleNamespace(text="hello")

        def accept_waveform(self, rate, samples):
            assert rate == 16000

    model = SimpleNamespace(create_stream=Stream, decode_stream=lambda stream: None)
    monkeypatch.setattr(
        "sherpa_onnx.OfflineRecognizer." + method, lambda **kwargs: model
    )
    engine = OnnxEngine(tmp_path, kind, "auto")
    result = engine.transcribe(np.ones(32000), "en")
    assert result[0].timestamp_source == "vad"
    assert result[0].end == 2
    assert result[0].words == []
    assert engine.transcribe(np.ones(16000), "en")[0].end == 1
    with pytest.raises(AudioError):
        OnnxEngine(tmp_path, kind, "cuda")


def test_runtime_maps_disjoint_regions_and_saves_provenance(tmp_path, monkeypatch):
    import json

    from free_plaud.providers.audio_models import SpeechRegion

    path = tmp_path / "original.wav"
    path.write_bytes(b"original bytes")
    runtime = AudioRuntime(tmp_path / "audio")
    segment = TranscriptSegment(
        start=0.1,
        end=0.5,
        raw_text="humm, certo",
        text="humm, certo",
        words=[TranscriptWord(start=0.2, end=0.4, text="certo")],
    )
    engine = SimpleNamespace(
        device="cpu", warnings=[], transcribe=lambda audio, language: [segment]
    )
    monkeypatch.setattr(runtime, "_engine", lambda opts: engine)
    monkeypatch.setattr(
        "free_plaud.ingest.audio_dsp.decode_audio", lambda path: np.ones(160000)
    )
    monkeypatch.setattr(
        runtime,
        "detector",
        lambda: SimpleNamespace(
            process=lambda *args, **kwargs: [
                SpeechRegion(start_sample=16000, end_sample=32000),
                SpeechRegion(start_sample=112000, end_sample=128000),
            ]
        ),
    )
    result = runtime.transcribe_result(path)
    assert [(s.start, s.end) for s in result.segments] == [(1.1, 1.5), (7.1, 7.5)]
    assert result.segments[1].words[0].start == 7.2
    assert result.text == "certo certo"
    assert result.raw_text == "humm, certo humm, certo"
    assert path.read_bytes() == b"original bytes"
    saved = json.loads(result.artifact_path.read_text(encoding="utf-8"))
    assert (
        saved["transcription"]["model_revision"]
        == runtime.store.model("whisper-small").revision
    )


def test_runtime_refuses_unsupported_models_and_languages_before_download(tmp_path):
    runtime = AudioRuntime(tmp_path)
    for options in [
        AudioOptions(model_id="moonshine-tiny-en"),
        AudioOptions(model_id="sensevoice-gguf-q8", language="en"),
    ]:
        with pytest.raises(AudioError):
            runtime._engine(options)
    with pytest.raises(AudioError):
        runtime.transcribe_result(tmp_path / "missing.wav")
