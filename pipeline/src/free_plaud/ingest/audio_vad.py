"""Stateful Silero ONNX inference and deterministic sample-based segmentation."""

from collections.abc import Callable
from pathlib import Path

import numpy as np
from pydantic import BaseModel, Field, model_validator

from free_plaud.providers.audio_models import SAMPLE_RATE, SpeechRegion

FRAME = 512


class VadOptions(BaseModel):
    threshold: float = Field(default=0.5, gt=0, lt=1)
    exit_threshold: float = Field(default=0.35, ge=0, lt=1)
    min_speech_ms: int = Field(default=250, ge=0)
    silence_ms: int = Field(default=300, gt=0)
    padding_ms: int = Field(default=100, ge=0)
    max_speech_seconds: float = Field(default=30, gt=0)

    @model_validator(mode="after")
    def thresholds(self) -> "VadOptions":
        if self.exit_threshold >= self.threshold:
            raise ValueError("Exit threshold must be below speech threshold.")
        return self


class SileroVad:
    def __init__(self, path: Path):
        import onnxruntime as ort

        options = ort.SessionOptions()
        options.inter_op_num_threads = 1
        options.intra_op_num_threads = 1
        self.session = ort.InferenceSession(
            str(path), sess_options=options, providers=["CPUExecutionProvider"]
        )
        self.reset()

    def reset(self) -> None:
        self.state = np.zeros((2, 1, 128), dtype=np.float32)
        self.context = np.zeros((1, 64), dtype=np.float32)

    def __call__(self, frame: np.ndarray) -> float:
        audio = np.concatenate((self.context, frame.reshape(1, FRAME)), axis=1)
        output, self.state = self.session.run(
            None,
            {
                "input": audio,
                "state": self.state,
                "sr": np.array(SAMPLE_RATE, dtype=np.int64),
            },
        )
        self.context = audio[:, -64:]
        return float(output[0][0])


class SpeechDetector:
    """Buffers incomplete inference frames without accumulating the recording."""

    def __init__(
        self,
        probability: Callable[[np.ndarray], float],
        options: VadOptions | None = None,
    ):
        self.probability = probability
        self.options = options or VadOptions()
        self.pending = np.empty(0, dtype=np.float32)
        self.position = 0
        self.start: int | None = None
        self.silence: int | None = None
        self.last_end = 0
        self.finished = False
        self.continuation = False

    def _finish(self, end: int, *, forced: bool = False) -> SpeechRegion | None:
        start = self.start
        continued = self.continuation
        self.continuation = False
        self.start = self.silence = None
        if start is None or end <= start:
            return None
        if (
            not forced
            and not continued
            and end - start < self.options.min_speech_ms * 16
        ):
            return None
        padded_start = max(self.last_end, start - self.options.padding_ms * 16)
        if not forced:
            end = min(end + self.options.padding_ms * 16, self.position)
        self.last_end = end
        return SpeechRegion(start_sample=padded_start, end_sample=end)

    def _frame(self, frame: np.ndarray, valid: int) -> SpeechRegion | None:
        current = self.position
        self.position += valid
        score = self.probability(frame)
        if score >= self.options.threshold:
            if self.start is None:
                self.start = current
            self.silence = None
        elif score < self.options.exit_threshold and self.start is not None:
            if self.silence is None:
                self.silence = current
            if self.position - self.silence >= self.options.silence_ms * 16:
                return self._finish(self.silence)
        if (
            self.start is not None
            and self.position
            - max(self.last_end, self.start - self.options.padding_ms * 16)
            >= self.options.max_speech_seconds * SAMPLE_RATE
        ):
            start = max(self.last_end, self.start - self.options.padding_ms * 16)
            end = start + int(self.options.max_speech_seconds * SAMPLE_RATE)
            region = self._finish(end, forced=True)
            self.start = end
            self.continuation = True
            return region
        return None

    def process(
        self, samples: np.ndarray, *, final: bool = False
    ) -> list[SpeechRegion]:
        if self.finished:
            raise ValueError("Detector already flushed.")
        self.pending = np.concatenate(
            (self.pending, np.asarray(samples, dtype=np.float32))
        )
        regions = []
        offset = 0
        while len(self.pending) - offset >= FRAME:
            region = self._frame(self.pending[offset : offset + FRAME], FRAME)
            if region is not None:
                regions.append(region)
            offset += FRAME
        self.pending = self.pending[offset:]
        if final:
            if len(self.pending):
                region = self._frame(
                    np.pad(self.pending, (0, FRAME - len(self.pending))),
                    len(self.pending),
                )
                if region is not None:
                    regions.append(region)
            region = self._finish(self.position)
            if region is not None:
                regions.append(region)
            self.pending = np.empty(0, dtype=np.float32)
            self.finished = True
        return regions
