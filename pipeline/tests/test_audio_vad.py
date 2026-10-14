from itertools import pairwise

import numpy as np
import pytest

from escolio.ingest.audio_dsp import AudioResampler, mono_pcm
from escolio.ingest.audio_vad import FRAME, SpeechDetector, VadOptions
from escolio.providers.audio_models import AudioError


def energy(frame):
    return 0.9 if np.max(np.abs(frame)) > 0.1 else 0.01


def speech_signal():
    return np.concatenate(
        (
            np.zeros(16000),
            np.ones(16000),
            np.zeros(16000),
            np.ones(8000),
            np.zeros(8000),
        )
    ).astype("float32")


def test_vad_keeps_original_timeline_and_no_duplicate_regions():
    regions = SpeechDetector(energy).process(speech_signal(), final=True)
    assert len(regions) == 2
    assert 14000 <= regions[0].start_sample <= 16000
    assert 32000 <= regions[0].end_sample <= 34200
    assert regions[1].start_sample >= 46000
    assert regions[0].end_sample < regions[1].start_sample


@pytest.mark.parametrize("size", [1, 123, 512, 999, 32000])
def test_fragmentation_does_not_change_regions(size):
    audio = speech_signal()
    expected = SpeechDetector(energy).process(audio, final=True)
    detector = SpeechDetector(energy)
    actual = []
    for i in range(0, len(audio), size):
        actual.extend(detector.process(audio[i : i + size]))
    actual.extend(detector.process(np.zeros(0, dtype="float32"), final=True))
    assert actual == expected


def test_silence_and_short_noise_do_not_become_speech():
    assert SpeechDetector(energy).process(np.zeros(10000), final=True) == []
    assert (
        SpeechDetector(energy).process(
            np.concatenate((np.ones(512), np.zeros(16000))), final=True
        )
        == []
    )


def test_partial_last_frame_and_long_speech_are_flushed():
    audio = np.ones(16000 * 65 + 123, dtype="float32")
    regions = SpeechDetector(energy).process(audio, final=True)
    assert len(regions) == 3
    assert regions[0].start_sample == 0
    assert regions[-1].end_sample == len(audio)
    assert all(a.end_sample == b.start_sample for a, b in pairwise(regions))
    assert all(r.end_sample - r.start_sample <= 480000 for r in regions)


@pytest.mark.parametrize("length", [480000, 480123, 960001])
def test_forced_cut_preserves_short_continuation(length):
    regions = SpeechDetector(energy).process(np.ones(length), final=True)
    assert sum(r.end_sample - r.start_sample for r in regions) == length
    assert all(r.end_sample - r.start_sample <= 480000 for r in regions)


def test_detector_cannot_be_reused_after_flush():
    detector = SpeechDetector(energy)
    detector.process(np.ones(512), final=True)
    with pytest.raises(ValueError, match="flushed"):
        detector.process(np.ones(512))
    with pytest.raises(ValueError):
        VadOptions(threshold=0.3, exit_threshold=0.4)


@pytest.mark.parametrize("rate", [44100, 48000, 16000])
def test_resampler_retains_duration_and_stream_equivalence(rate):
    t = np.arange(rate * 2, dtype="float32") / rate
    source = np.sin(2 * np.pi * 440 * t)
    expected = AudioResampler(rate).process(source, final=True)
    stream = AudioResampler(rate)
    parts = [stream.process(source[i : i + 713]) for i in range(0, len(source), 713)]
    parts.append(stream.process(np.zeros(0), final=True))
    actual = np.concatenate(parts)
    assert len(actual) == 32000
    np.testing.assert_allclose(actual, expected, atol=1e-6)
    with pytest.raises(AudioError, match="flushed"):
        stream.process(source)


def test_pcm_downmix_scaling_and_invalid_input():
    np.testing.assert_allclose(
        mono_pcm(np.array([[32767, -32768]], dtype="int16")), [-1 / 65536]
    )
    np.testing.assert_allclose(
        mono_pcm(np.array([0, 128, 255], dtype="uint8")), [-1, 0, 127 / 128]
    )
    np.testing.assert_allclose(mono_pcm(np.array([[-2, 2]], dtype="float32")), [0])
    for invalid in [np.array([np.nan]), np.zeros((2, 3, 4)), np.zeros((1, 0))]:
        with pytest.raises(AudioError):
            mono_pcm(invalid)
    with pytest.raises(AudioError):
        AudioResampler(0)


def test_silero_recurrent_context_without_model_download(monkeypatch, tmp_path):
    from escolio.ingest.audio_vad import SileroVad

    seen = []

    class Session:
        def __init__(self, *args, **kwargs):
            assert kwargs["providers"] == ["CPUExecutionProvider"]

        def run(self, outputs, inputs):
            seen.append(inputs)
            return np.array([[0.8]]), inputs["state"] + 1

    monkeypatch.setattr("onnxruntime.InferenceSession", Session)
    detector = SileroVad(tmp_path / "model.onnx")
    assert detector(np.ones(FRAME, dtype="float32")) == 0.8
    detector(np.zeros(FRAME, dtype="float32"))
    assert seen[0]["input"].shape == (1, 576)
    assert np.all(seen[1]["input"][:, :64] == 1)
    assert np.all(seen[1]["state"] == 1)
    detector.reset()
    assert np.count_nonzero(detector.state) == 0
