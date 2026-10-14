"""Audio facade consumed equally by presentation layers."""

from pathlib import Path

from escolio.app.audio_service import (
    audio_jobs,
    audio_options,
    audio_runtime,
    download_jobs,
)
from escolio.app.config import Settings
from escolio.providers.audio_models import AudioOptions, TranscriptionResult
from escolio.providers.voice_model_meta import ui_meta_for


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
    from escolio.corpus.service import index_corpus_file

    if result.artifact_path is None or not result.text.strip():
        raise ValueError("A saved, nonempty transcription is required for indexing.")
    target = result.artifact_path.with_suffix(".txt")
    target.write_text(result.text, encoding="utf-8")
    return index_corpus_file(target, settings=settings)


def list_voice_models(*, settings: Settings | None = None) -> list[dict]:
    store = audio_runtime(settings).store
    result = []
    for model in store.catalog.values():
        meta = ui_meta_for(model.id)
        result.append(
            {
                **model.model_dump(),
                "installed": store.verify(model.id),
                "size_bytes": sum(item.size for item in model.files),
                "label": meta.label if meta else model.id,
                "description": meta.description if meta else "",
                "speed_tier": meta.speed_tier if meta else None,
                "quality_tier": meta.quality_tier if meta else None,
                "recommended": meta.recommended if meta else False,
                "supports_auto_language": meta.supports_auto_language if meta else False,
                "selectable": meta.selectable if meta else True,
            }
        )
    return result


def download_voice_model(
    model_id: str, *, settings: Settings | None = None, progress=None
) -> Path:
    return audio_runtime(settings).store.download(model_id, progress)


def verify_voice_model(model_id: str, *, settings: Settings | None = None) -> bool:
    return audio_runtime(settings).store.verify(model_id)


def start_voice_model_download(model_id: str, *, settings: Settings | None = None):
    return download_jobs(settings).start(model_id)


def get_voice_model_download(job_id: str, *, settings: Settings | None = None):
    return download_jobs(settings).get(job_id)


def cancel_voice_model_download(job_id: str, *, settings: Settings | None = None):
    return download_jobs(settings).cancel(job_id)


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
