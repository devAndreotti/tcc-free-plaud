"""Local STT adapters. Each instance is owned by a serialized audio runtime."""

from pathlib import Path

from escolio.providers.audio_models import (
    AudioError,
    TranscriptSegment,
    TranscriptWord,
)
from escolio.providers.audio_native import prepare_native_libraries


def _gpu_failure(exc: Exception) -> bool:
    message = str(exc).lower()
    return any(
        token in message
        for token in ("cuda", "cudnn", "cublas", "out of memory", "insufficient memory")
    )


class WhisperEngine:
    def __init__(self, directory: Path, device: str):
        self.directory = directory
        self.requested_device = device
        self.device = device
        self.warnings: list[str] = []
        self.model = None
        # Preenchido apenas quando transcribe() roda com language="auto".
        # ponytail: guarda so o ultimo idioma detectado entre regioes de VAD,
        # nao um agregado - suficiente pro caso real de gravacao monolingue.
        self.detected_language: str | None = None

    def _load(self) -> None:
        import ctranslate2
        from faster_whisper import WhisperModel

        if self.device == "auto":
            self.device = "cuda" if ctranslate2.get_cuda_device_count() > 0 else "cpu"
            if self.device == "cpu":
                self.warnings.append("CUDA unavailable; using CPU.")
        if self.device == "cuda":
            try:
                prepare_native_libraries("cuda")
            except OSError as exc:
                raise RuntimeError(f"CUDA native libraries unavailable: {exc}") from exc
        self.model = WhisperModel(
            str(self.directory),
            device=self.device,
            compute_type="int8_float16" if self.device == "cuda" else "int8",
            local_files_only=True,
            num_workers=1,
        )

    def _decode(self, audio, language: str) -> list[TranscriptSegment]:
        if self.model is None:
            self._load()
        # faster-whisper detecta o idioma automaticamente quando language=None.
        lang_arg = None if language == "auto" else language
        segments, info = self.model.transcribe(
            audio,
            language=lang_arg,
            beam_size=5,
            word_timestamps=True,
            vad_filter=False,
            condition_on_previous_text=False,
        )
        if lang_arg is None:
            self.detected_language = info.language
        return [
            TranscriptSegment(
                start=max(0, segment.start),
                end=max(segment.start, segment.end),
                raw_text=segment.text,
                text=segment.text,
                no_speech_probability=segment.no_speech_prob,
                average_log_probability=segment.avg_logprob,
                words=[
                    TranscriptWord(
                        start=max(0, word.start),
                        end=max(word.start, word.end),
                        text=word.word,
                        probability=word.probability,
                    )
                    for word in (segment.words or [])
                ],
            )
            for segment in segments
        ]

    def transcribe(self, audio, language: str) -> list[TranscriptSegment]:
        try:
            return self._decode(audio, language)
        except RuntimeError as exc:
            if (
                self.requested_device != "auto"
                or self.device == "cpu"
                or not _gpu_failure(exc)
            ):
                raise
            self.model = None
            self.device = "cpu"
            self.warnings.append("CUDA inference failed; retried once on CPU.")
            return self._decode(audio, language)


class OnnxEngine:
    def __init__(self, directory: Path, engine: str, device: str):
        if device == "cuda":
            raise AudioError(
                "AUDIO_DEVICE_UNSUPPORTED",
                "ONNX speech adapters run on CPU in this release.",
            )
        self.directory = directory
        self.engine = engine
        self.device = "cpu"
        self.warnings: list[str] = []
        self.model = None
        self.language: str | None = None

    def _load(self, language: str) -> None:
        prepare_native_libraries("onnx")
        import sherpa_onnx

        path = self.directory
        if self.engine == "sensevoice":
            self.model = sherpa_onnx.OfflineRecognizer.from_sense_voice(
                model=str(path / "model.int8.onnx"),
                tokens=str(path / "tokens.txt"),
                language=language,
                use_itn=True,
                num_threads=2,
                provider="cpu",
            )
        else:
            self.model = sherpa_onnx.OfflineRecognizer.from_moonshine(
                preprocessor=str(path / "preprocess.onnx"),
                encoder=str(path / "encode.int8.onnx"),
                uncached_decoder=str(path / "uncached_decode.int8.onnx"),
                cached_decoder=str(path / "cached_decode.int8.onnx"),
                tokens=str(path / "tokens.txt"),
                num_threads=2,
                provider="cpu",
            )
        self.language = language

    def transcribe(self, audio, language: str) -> list[TranscriptSegment]:
        if self.model is None or self.language != language:
            self._load(language)
        stream = self.model.create_stream()
        stream.accept_waveform(16000, audio)
        self.model.decode_stream(stream)
        text = stream.result.text
        if not text.strip():
            return []
        return [
            TranscriptSegment(
                start=0,
                end=len(audio) / 16000,
                raw_text=text,
                text=text,
                timestamp_source="vad",
            )
        ]
