"""Process-wide audio resources shared by CLI, TUI and desktop facade."""

from functools import lru_cache
from pathlib import Path

from free_plaud.app.config import Settings, get_settings
from free_plaud.providers.audio_models import AudioOptions


@lru_cache(maxsize=8)
def _runtime(root: Path):
    from free_plaud.providers.audio_runtime import AudioRuntime

    return AudioRuntime(root)


def audio_runtime(settings: Settings | None = None):
    settings = settings or get_settings()
    return _runtime((settings.results_dir / "audio").resolve())


@lru_cache(maxsize=8)
def _jobs(root: Path):
    from free_plaud.ingest.audio_jobs import AudioJobManager

    return AudioJobManager(_runtime(root))


def audio_jobs(settings: Settings | None = None):
    settings = settings or get_settings()
    return _jobs((settings.results_dir / "audio").resolve())


@lru_cache(maxsize=8)
def _download_jobs(root: Path):
    from free_plaud.ingest.download_jobs import DownloadJobManager

    return DownloadJobManager(_runtime(root).store)


def download_jobs(settings: Settings | None = None):
    settings = settings or get_settings()
    return _download_jobs((settings.results_dir / "audio").resolve())


def audio_options(settings: Settings | None = None) -> AudioOptions:
    settings = settings or get_settings()
    return AudioOptions(
        model_id=settings.audio_model,
        language=settings.audio_language,
        device=settings.audio_device,
    )
