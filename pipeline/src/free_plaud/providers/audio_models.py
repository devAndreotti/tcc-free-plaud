"""Portable audio contracts. Importing these types never loads a native runtime."""

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

SAMPLE_RATE = 16_000


class AudioError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(message)


class TimeSpan(BaseModel):
    model_config = ConfigDict(frozen=True, allow_inf_nan=False)
    start: float = Field(ge=0)
    end: float = Field(ge=0)

    @model_validator(mode="after")
    def ordered(self) -> "TimeSpan":
        if self.end < self.start:
            raise ValueError("end must not precede start")
        return self


class TranscriptWord(TimeSpan):
    text: str
    probability: float | None = None


class TranscriptSegment(TimeSpan):
    raw_text: str
    text: str
    timestamp_source: Literal["model", "vad"] = "model"
    words: list[TranscriptWord] = Field(default_factory=list)
    no_speech_probability: float | None = None
    average_log_probability: float | None = None
    cleaning: list[str] = Field(default_factory=list)


class TranscriptionResult(BaseModel):
    source_path: Path
    source_sha256: str
    model_id: str
    model_revision: str
    language: str
    device: str
    duration_seconds: float
    raw_text: str
    text: str
    segments: list[TranscriptSegment] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    elapsed_seconds: float = 0
    artifact_path: Path | None = None


class AudioOptions(BaseModel):
    model_config = ConfigDict(frozen=True)
    model_id: str = "whisper-small"
    language: str = "pt"
    device: Literal["auto", "cpu", "cuda"] = "auto"
    vad: bool = True
    clean: bool = True


class SpeechRegion(BaseModel):
    """Half-open sample interval on the original 16 kHz timeline."""

    model_config = ConfigDict(frozen=True)
    start_sample: int = Field(ge=0)
    end_sample: int = Field(gt=0)

    @model_validator(mode="after")
    def ordered(self) -> "SpeechRegion":
        if self.end_sample <= self.start_sample:
            raise ValueError("Empty speech region")
        return self
