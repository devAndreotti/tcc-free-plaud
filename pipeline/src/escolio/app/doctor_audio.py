"""Audio diagnostics without downloads, recording or model inference."""

from importlib.util import find_spec

from escolio.app.audio_service import audio_runtime
from escolio.app.doctor_models import DoctorCheck


def audio_checks(settings) -> list[DoctorCheck]:
    missing = [
        name
        for name in (
            "sounddevice",
            "soxr",
            "onnxruntime",
            "faster_whisper",
            "sherpa_onnx",
        )
        if find_spec(name) is None
    ]
    if missing:
        return [
            DoctorCheck(
                code="audio.dependencies",
                status="warning",
                message="Faltam dependências opcionais de áudio: " + ", ".join(missing),
                action="uv sync --extra audio",
            )
        ]
    try:
        store = audio_runtime(settings).store
        ready = {
            model: store.verify(model) for model in ("silero-vad", settings.audio_model)
        }
        import ctranslate2

        devices = ctranslate2.get_cuda_device_count()
        return [
            DoctorCheck(
                code="audio.models",
                status="ok" if all(ready.values()) else "warning",
                message="Integridade dos modelos de áudio verificada.",
                details=ready,
                action=None
                if all(ready.values())
                else "Use ingest audio download MODEL.",
            ),
            DoctorCheck(
                code="audio.device",
                status="warning"
                if settings.audio_device == "cuda" and not devices
                else "ok",
                message="Dispositivo do CTranslate2 disponível; falta um teste de inferência.",
                details={"cuda_devices": devices, "requested": settings.audio_device},
            ),
        ]
    except Exception as exc:
        return [
            DoctorCheck(
                code="audio.runtime",
                status="error",
                message=f"Falha no diagnóstico de áudio: {exc}",
            )
        ]
