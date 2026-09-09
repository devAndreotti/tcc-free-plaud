"""Headless audio entrypoints. Business logic remains in the shared facade."""

import json
from pathlib import Path
from time import monotonic, sleep

import typer

from free_plaud.providers.audio_models import AudioError, AudioOptions
from free_plaud.tui import audio_actions as actions

app = typer.Typer(help="Captura e transcricao local de audio.", no_args_is_help=True)


def _show(value) -> None:
    payload = value.model_dump(mode="json") if hasattr(value, "model_dump") else value
    typer.echo(json.dumps(payload, ensure_ascii=False, indent=2))


@app.command("models")
def models() -> None:
    _show(actions.list_voice_models())


@app.command("download")
def download(model_id: str) -> None:
    def progress(name, done, total):
        typer.echo(f"{name}: {done}/{total} bytes verificados", err=True)

    try:
        typer.echo(str(actions.download_voice_model(model_id, progress=progress)))
    except (AudioError, OSError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1) from exc


@app.command("verify")
def verify(model_id: str) -> None:
    try:
        valid = actions.verify_voice_model(model_id)
    except (ValueError, OSError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1) from exc
    _show({"model_id": model_id, "verified": valid})
    if not valid:
        raise typer.Exit(1)


@app.command("transcribe")
def transcribe(
    path: Path,
    model: str = "whisper-small",
    language: str = "pt",
    device: str = "auto",
    vad: bool = True,
    clean: bool = True,
) -> None:
    try:
        _show(
            actions.transcribe_audio(
                path,
                options=AudioOptions(
                    model_id=model,
                    language=language,
                    device=device,
                    vad=vad,
                    clean=clean,
                ),
            )
        )
    except (ValueError, OSError, ImportError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1) from exc


@app.command("record")
def record(
    seconds: float = typer.Option(10, min=0.1, max=3600),
    model: str = "whisper-small",
    language: str = "pt",
    device: str = "auto",
    microphone: int | None = None,
    index: bool = False,
) -> None:
    job = None
    try:
        options = AudioOptions(model_id=model, language=language, device=device)
        job = actions.start_audio_capture(options=options, device=microphone)
        end = monotonic() + seconds
        next_progress = 0.0
        while monotonic() < end:
            job = actions.get_audio_capture(job.job_id)
            if job.status == "failed":
                break
            if monotonic() >= next_progress:
                typer.echo(f"Gravando: {job.samples_captured / 16000:.1f}s", err=True)
                next_progress = monotonic() + 1
            sleep(0.1)
        job = actions.stop_audio_capture(job.job_id)
        while job.status in ("queued", "transcribing"):
            sleep(0.1)
            job = actions.get_audio_capture(job.job_id)
        _show(job)
        if job.status != "completed":
            raise typer.Exit(1)
        if index:
            from free_plaud.tui.audio_actions import index_audio_result

            # Index the immutable cleaned text snapshot, avoiding another STT pass.
            _show(index_audio_result(job.result))
    except KeyboardInterrupt:
        if job is not None:
            actions.cancel_audio_capture(job.job_id)
        raise typer.Exit(130) from None
    except (ValueError, OSError, ImportError) as exc:
        if job is not None:
            actions.cancel_audio_capture(job.job_id)
        typer.echo(str(exc), err=True)
        raise typer.Exit(1) from exc


@app.command("evaluate")
def evaluate(manifest: Path, model: str = "whisper-small", device: str = "cpu") -> None:
    from free_plaud.app.audio_service import audio_runtime
    from free_plaud.benchmark.audio import evaluate_audio

    _show(evaluate_audio(manifest, audio_runtime(), model_id=model, device=device))
