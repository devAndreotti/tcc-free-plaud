"""Shared local audio service with serialized native inference and provenance."""

import json
from pathlib import Path
from threading import Lock
from time import perf_counter
from uuid import uuid4

from free_plaud.providers.audio_catalog import ModelStore, file_hash
from free_plaud.providers.audio_models import (
    SAMPLE_RATE,
    AudioError,
    AudioOptions,
    SpeechRegion,
    TranscriptionResult,
)


class AudioRuntime:
    def __init__(self, root: Path):
        self.root = Path(root)
        self.store = ModelStore(self.root / "models")
        self._engines: dict[tuple[str, str, str], object] = {}
        self._lock = Lock()

    def detector(self):
        from free_plaud.ingest.audio_vad import SileroVad, SpeechDetector

        directory = self.store.require("silero-vad")
        return SpeechDetector(SileroVad(directory / "onnx/model.onnx"))

    def prepare(self, options: AudioOptions) -> None:
        """Validate language, device and provisioned weights before recording."""
        with self._lock:
            self._engine(options)

    def _engine(self, options: AudioOptions):
        from free_plaud.providers.audio_engines import OnnxEngine, WhisperEngine

        model = self.store.model(options.model_id)
        if model.engine not in ("faster-whisper", "sensevoice", "moonshine"):
            raise AudioError(
                "AUDIO_ENGINE_UNSUPPORTED",
                "This model is catalogued but is not an executable STT engine.",
            )
        if options.language == "auto":
            # Deteccao automatica so existe de verdade via faster-whisper
            # (language=None); outros engines exigem idioma explicito.
            if model.engine != "faster-whisper":
                raise AudioError(
                    "AUDIO_LANGUAGE_UNSUPPORTED",
                    f"{model.id} does not support automatic language detection.",
                )
        elif options.language not in model.languages:
            raise AudioError(
                "AUDIO_LANGUAGE_UNSUPPORTED",
                f"{model.id} does not support {options.language}.",
            )
        key = (model.id, model.revision, options.device)
        if key not in self._engines:
            directory = self.store.require(model.id)
            self._engines[key] = (
                WhisperEngine(directory, options.device)
                if model.engine == "faster-whisper"
                else OnnxEngine(directory, model.engine, options.device)
            )
        return self._engines[key]

    def transcribe_result(
        self,
        source_path: str | Path,
        options: AudioOptions | None = None,
        *,
        cancel=None,
    ) -> TranscriptionResult:
        from free_plaud.ingest.audio_cleaner import clean_segment
        from free_plaud.ingest.audio_dsp import decode_audio

        options = options or AudioOptions()
        source = Path(source_path).resolve()
        if not source.is_file():
            raise AudioError("INPUT_NOT_FOUND", f"Audio file not found: {source.name}")
        started = perf_counter()
        with self._lock:
            engine = self._engine(options)
            source_hash = file_hash(source)
            audio = decode_audio(source)
            if not len(audio):
                raise AudioError("EMPTY_CONTENT", "Audio contains no samples.")
            if options.vad:
                detector = self.detector()
                regions = detector.process(audio, final=True)
            else:
                regions = [
                    SpeechRegion(
                        start_sample=start, end_sample=min(start + 480000, len(audio))
                    )
                    for start in range(0, len(audio), 480000)
                ]
            segments = []
            for region in regions:
                if cancel is not None and cancel.is_set():
                    raise AudioError(
                        "AUDIO_CANCELLED", "Audio transcription cancelled."
                    )
                origin = region.start_sample / SAMPLE_RATE
                length = (region.end_sample - region.start_sample) / SAMPLE_RATE
                for segment in engine.transcribe(
                    audio[region.start_sample : region.end_sample], options.language
                ):
                    words = [
                        word.model_copy(
                            update={
                                "start": origin + min(word.start, length),
                                "end": origin + min(word.end, length),
                            }
                        )
                        for word in segment.words
                    ]
                    mapped = segment.model_copy(
                        update={
                            "start": origin + min(segment.start, length),
                            "end": origin + min(segment.end, length),
                            "words": words,
                        }
                    )
                    segments.append(clean_segment(mapped) if options.clean else mapped)
            if cancel is not None and cancel.is_set():
                raise AudioError("AUDIO_CANCELLED", "Audio transcription cancelled.")
            if source_hash != file_hash(source):
                raise AudioError(
                    "AUDIO_SOURCE_CHANGED", "Audio changed during transcription."
                )
            detected_language = getattr(engine, "detected_language", None)
            result = TranscriptionResult(
                source_path=source,
                source_sha256=source_hash,
                model_id=options.model_id,
                model_revision=self.store.model(options.model_id).revision,
                language=detected_language if options.language == "auto" and detected_language else options.language,
                device=engine.device if regions else "none",
                duration_seconds=len(audio) / SAMPLE_RATE,
                raw_text=" ".join(s.raw_text.strip() for s in segments).strip(),
                text=" ".join(s.text.strip() for s in segments if s.text.strip()),
                segments=segments,
                warnings=list(engine.warnings),
                elapsed_seconds=perf_counter() - started,
            )
            if not regions:
                result.warnings.append("No speech detected.")
            self._persist(result, options)
            return result

    def _persist(self, result: TranscriptionResult, options: AudioOptions) -> None:
        directory = self.root / "transcripts"
        directory.mkdir(parents=True, exist_ok=True)
        result.artifact_path = (
            directory / f"{result.source_sha256[:16]}-{uuid4().hex}.json"
        )
        temporary = result.artifact_path.with_suffix(".partial")
        payload = {
            "schema_version": 1,
            "options": options.model_dump(),
            "transcription": result.model_dump(mode="json"),
        }
        temporary.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        temporary.replace(result.artifact_path)

    def transcribe(self, source_path: str) -> str:
        return self.transcribe_result(source_path).text
