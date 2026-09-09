"""Streaming resampling and decoding with no changes to the source file."""

from pathlib import Path

import numpy as np

from free_plaud.providers.audio_models import SAMPLE_RATE, AudioError


def mono_pcm(samples: np.ndarray) -> np.ndarray:
    data = np.asarray(samples)
    if data.ndim not in (1, 2) or (data.ndim == 2 and not data.shape[1]):
        raise AudioError("AUDIO_INVALID_PCM", "Expected mono or frame/channel PCM.")
    if np.issubdtype(data.dtype, np.integer):
        limits = np.iinfo(data.dtype)
        midpoint = (limits.max + 1) / 2 if limits.min == 0 else 0
        scale = midpoint if midpoint else -limits.min
        data = (data.astype(np.float32) - midpoint) / scale
    else:
        data = data.astype(np.float32)
    if data.ndim == 2:
        data = data.mean(axis=1)
    if not np.isfinite(data).all():
        raise AudioError("AUDIO_INVALID_PCM", "PCM contains non-finite samples.")
    return np.clip(data, -1, 1)


class AudioResampler:
    def __init__(self, input_rate: int):
        import soxr

        if input_rate <= 0:
            raise AudioError("AUDIO_INVALID_RATE", "Sample rate must be positive.")
        self._stream = soxr.ResampleStream(
            input_rate, SAMPLE_RATE, 1, dtype="float32", quality="HQ"
        )
        self._finished = False

    def process(self, samples: np.ndarray, *, final: bool = False) -> np.ndarray:
        if self._finished:
            raise AudioError("AUDIO_CLOSED", "Resampler already flushed.")
        data = mono_pcm(samples)
        self._finished = final
        return self._stream.resample_chunk(data, last=final)


def decode_audio(path: Path) -> np.ndarray:
    # PyAV bundles the codecs needed for WAV, MP3, M4A and OGG.
    try:
        from faster_whisper.audio import decode_audio as decode

        return mono_pcm(decode(str(path), sampling_rate=SAMPLE_RATE))
    except ImportError as exc:
        raise AudioError(
            "AUDIO_DEPENDENCY_MISSING", "Install the audio extra."
        ) from exc
    except (ValueError, OSError, RuntimeError) as exc:
        raise AudioError(
            "AUDIO_DECODE_FAILED", f"Cannot decode audio: {path.name}"
        ) from exc
