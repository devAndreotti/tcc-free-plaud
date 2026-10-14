import json
from types import SimpleNamespace

import pytest
from typer.testing import CliRunner

from escolio.benchmark.audio import evaluate_audio, speech_metrics
from escolio.ingest.audio_cli import app
from escolio.providers.audio_catalog import file_hash
from escolio.providers.audio_models import AudioError, TranscriptionResult
from escolio.tui import audio_actions as actions


def result_for(path):
    return TranscriptionResult(
        source_path=path,
        source_sha256="a" * 64,
        model_id="whisper-small",
        model_revision="b" * 40,
        language="pt",
        device="cpu",
        duration_seconds=2,
        elapsed_seconds=1,
        raw_text="humm, texto original",
        text="texto original",
        segments=[],
        artifact_path=path.with_suffix(".json"),
    )


def test_audio_loader_keeps_raw_text_and_structures_cleaned_text(tmp_path, monkeypatch):
    from escolio.ingest.loaders import load_document
    from escolio.notes.structurer import structure_document

    path = tmp_path / "meeting.wav"
    path.write_bytes(b"audio")
    result = result_for(path)
    monkeypatch.setattr(
        "escolio.app.audio_service.audio_runtime",
        lambda: SimpleNamespace(transcribe_result=lambda *args: result),
    )
    document = load_document(path)
    assert document.raw_text == result.raw_text
    assert document.cleaned_text == result.text
    assert document.transcription_path == result.artifact_path
    note = structure_document(document)
    assert note.raw_text == result.raw_text
    assert note.normalized_text == result.text


def test_evaluation_checks_hashes_languages_and_modes(tmp_path):
    path = tmp_path / "speech.wav"
    path.write_bytes(b"fixture")
    manifest = tmp_path / "manifest.json"
    sample = {
        "file": path.name,
        "config": "pt_br",
        "reference": "texto original",
        "sha256": file_hash(path),
    }
    manifest.write_text(
        json.dumps({"samples": [sample, {**sample, "config": "en_us"}]})
    )
    calls = []

    def transcribe(path, options):
        calls.append((options.vad, options.clean))
        return result_for(path)

    runtime = SimpleNamespace(
        store=SimpleNamespace(
            model=lambda _: SimpleNamespace(languages=["pt"], revision="b" * 40)
        ),
        transcribe_result=transcribe,
    )
    report = evaluate_audio(manifest, runtime, model_id="whisper-small")
    assert calls == [(False, False), (True, False), (True, True)]
    assert all(
        row["wer"] == 0 and row["real_time_factor"] == 0.5 for row in report["results"]
    )
    path.write_bytes(b"corrupt")
    with pytest.raises(AudioError, match="hash"):
        evaluate_audio(manifest, runtime, model_id="whisper-small")
    sample["file"] = "../outside.wav"
    manifest.write_text(json.dumps({"samples": [sample]}))
    with pytest.raises(AudioError, match="escapes"):
        evaluate_audio(manifest, runtime, model_id="whisper-small")


def test_speech_metrics_count_substitutions_deletions_insertions():
    assert speech_metrics("Olá, mundo!", "olá mundo") == {"wer": 0, "cer": 0}
    assert speech_metrics("a b c", "a d")["wer"] == pytest.approx(2 / 3)
    assert speech_metrics("", "a") == {"wer": 1, "cer": 1}


def test_doctor_audio_never_records_or_downloads(tmp_path, monkeypatch):
    from escolio.app import doctor_audio
    from escolio.app.config import Settings

    settings = Settings(results_dir=tmp_path, audio_device="cuda")
    monkeypatch.setattr(doctor_audio, "find_spec", lambda _: None)
    assert doctor_audio.audio_checks(settings)[0].code == "audio.dependencies"
    monkeypatch.setattr(doctor_audio, "find_spec", lambda _: True)
    monkeypatch.setattr(
        doctor_audio,
        "audio_runtime",
        lambda _: SimpleNamespace(store=SimpleNamespace(verify=lambda _: False)),
    )
    monkeypatch.setattr("ctranslate2.get_cuda_device_count", lambda: 0)
    checks = doctor_audio.audio_checks(settings)
    assert [c.status for c in checks] == ["warning", "warning"]
    monkeypatch.setattr(
        doctor_audio,
        "audio_runtime",
        lambda _: SimpleNamespace(store=SimpleNamespace(verify=lambda _: True)),
    )
    monkeypatch.setattr("ctranslate2.get_cuda_device_count", lambda: 1)
    assert all(c.status == "ok" for c in doctor_audio.audio_checks(settings))
    monkeypatch.setattr(
        doctor_audio,
        "audio_runtime",
        lambda _: (_ for _ in ()).throw(ValueError("bad catalog")),
    )
    assert doctor_audio.audio_checks(settings)[0].status == "error"


def test_audio_facade_and_cli_use_shared_runtime(tmp_path, monkeypatch):
    from escolio.providers.audio_catalog import load_catalog

    path = tmp_path / "speech.wav"
    result = result_for(path)
    catalog = load_catalog()
    store = SimpleNamespace(
        catalog=catalog,
        verify=lambda _: True,
        download=lambda model, progress: tmp_path,
    )
    runtime = SimpleNamespace(store=store, transcribe_result=lambda *args: result)
    monkeypatch.setattr(actions, "audio_runtime", lambda _: runtime)
    assert actions.transcribe_audio(path) == result
    assert all(model["installed"] for model in actions.list_voice_models())
    assert actions.download_voice_model("whisper-small") == tmp_path
    assert actions.verify_voice_model("whisper-small")
    runner = CliRunner()
    assert runner.invoke(app, ["models"]).exit_code == 0
    assert runner.invoke(app, ["download", "whisper-small"]).exit_code == 0
    assert runner.invoke(app, ["verify", "whisper-small"]).exit_code == 0
    response = runner.invoke(app, ["transcribe", str(path)])
    assert response.exit_code == 0, response.output
    assert json.loads(response.output)["raw_text"] == result.raw_text
    store.verify = lambda _: False
    assert runner.invoke(app, ["verify", "whisper-small"]).exit_code == 1
    runtime.transcribe_result = lambda *args: (_ for _ in ()).throw(
        AudioError("FAILED", "missing model")
    )
    assert runner.invoke(app, ["transcribe", str(path)]).exit_code == 1


def test_capture_facade_delegates_lifecycle(monkeypatch):
    seen = []
    manager = SimpleNamespace(
        start=lambda *args, **kwargs: seen.append("start"),
        get=lambda job: seen.append(("get", job)),
        stop=lambda job: seen.append(("stop", job)),
        cancel=lambda job: seen.append(("cancel", job)),
    )
    monkeypatch.setattr(actions, "audio_jobs", lambda _: manager)
    actions.start_audio_capture()
    actions.get_audio_capture("one")
    actions.stop_audio_capture("one")
    actions.cancel_audio_capture("one")
    assert seen == ["start", ("get", "one"), ("stop", "one"), ("cancel", "one")]


def test_record_cli_progress_completion_and_start_failure(tmp_path, monkeypatch):
    from escolio.ingest import audio_cli
    from escolio.ingest.audio_jobs import AudioJobSnapshot

    snapshot = AudioJobSnapshot(
        job_id="one", status="recording", source_path=tmp_path / "a.wav"
    )
    monkeypatch.setattr(actions, "start_audio_capture", lambda **kwargs: snapshot)
    monkeypatch.setattr(actions, "get_audio_capture", lambda _: snapshot)
    monkeypatch.setattr(
        actions,
        "stop_audio_capture",
        lambda _: snapshot.model_copy(
            update={"status": "completed", "result": result_for(snapshot.source_path)}
        ),
    )
    times = iter([0, 0, 0, 0, 2])
    monkeypatch.setattr(audio_cli, "monotonic", lambda: next(times))
    monkeypatch.setattr(audio_cli, "sleep", lambda _: None)
    runner = CliRunner()
    response = runner.invoke(app, ["record", "--seconds", "1"])
    assert response.exit_code == 0, response.exception
    assert "Gravando" in response.output
    assert '"status": "completed"' in response.output
    monkeypatch.setattr(
        actions,
        "start_audio_capture",
        lambda **kwargs: (_ for _ in ()).throw(AudioError("DEVICE", "No microphone")),
    )
    response = runner.invoke(app, ["record"])
    assert response.exit_code == 1
    assert "No microphone" in response.output


def test_record_cli_interrupt_cancels_capture(tmp_path, monkeypatch):
    from escolio.ingest.audio_jobs import AudioJobSnapshot

    snapshot = AudioJobSnapshot(
        job_id="one", status="recording", source_path=tmp_path / "a.wav"
    )
    cancelled = []
    monkeypatch.setattr(actions, "start_audio_capture", lambda **kwargs: snapshot)
    monkeypatch.setattr(
        actions,
        "get_audio_capture",
        lambda _: (_ for _ in ()).throw(KeyboardInterrupt()),
    )
    monkeypatch.setattr(actions, "cancel_audio_capture", cancelled.append)
    response = CliRunner().invoke(app, ["record"])
    assert response.exit_code == 130
    assert cancelled == ["one"]
