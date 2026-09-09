"""Audio facade consumed equally by presentation layers."""

from pathlib import Path

from free_plaud.app.audio_service import audio_jobs, audio_options, audio_runtime
from free_plaud.app.config import Settings
from free_plaud.providers.audio_models import AudioOptions, TranscriptionResult


def transcribe_audio(
    path: Path | str,
    *,
    options: AudioOptions | None = None,
    settings: Settings | None = None,
) -> TranscriptionResult:
    return audio_runtime(settings).transcribe_result(
        path, options or audio_options(settings)
    )


def index_audio_result(
    result: TranscriptionResult, *, settings: Settings | None = None
):
    from free_plaud.corpus.service import index_corpus_file

    if result.artifact_path is None or not result.text.strip():
        raise ValueError("A saved, nonempty transcription is required for indexing.")
    target = result.artifact_path.with_suffix(".txt")
    target.write_text(result.text, encoding="utf-8")
    return index_corpus_file(target, settings=settings)


def list_voice_models(*, settings: Settings | None = None) -> list[dict]:
    store = audio_runtime(settings).store
    return [
        dict(**model.model_dump(), installed=store.verify(model.id))
        for model in store.catalog.values()
    ]


def download_voice_model(
    model_id: str, *, settings: Settings | None = None, progress=None
) -> Path:
    return audio_runtime(settings).store.download(model_id, progress)


def verify_voice_model(model_id: str, *, settings: Settings | None = None) -> bool:
    return audio_runtime(settings).store.verify(model_id)


def start_audio_capture(
    *,
    options: AudioOptions | None = None,
    device=None,
    settings: Settings | None = None,
):
    return audio_jobs(settings).start(options or audio_options(settings), device=device)


def get_audio_capture(job_id: str, *, settings: Settings | None = None):
    return audio_jobs(settings).get(job_id)


def stop_audio_capture(job_id: str, *, settings: Settings | None = None):
    return audio_jobs(settings).stop(job_id)


def cancel_audio_capture(job_id: str, *, settings: Settings | None = None):
    return audio_jobs(settings).cancel(job_id)
