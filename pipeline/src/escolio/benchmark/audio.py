"""Reproducible speech evaluation against fixed local fixtures, never cloud STT."""

import json
import re
from pathlib import Path

from escolio.providers.audio_catalog import file_hash
from escolio.providers.audio_models import AudioError, AudioOptions


def edit_distance(reference, hypothesis) -> int:
    previous = list(range(len(hypothesis) + 1))
    for i, expected in enumerate(reference, 1):
        current = [i]
        for j, actual in enumerate(hypothesis, 1):
            current.append(
                min(
                    current[-1] + 1,
                    previous[j] + 1,
                    previous[j - 1] + (expected != actual),
                )
            )
        previous = current
    return previous[-1]


def normalized_text(value: str) -> str:
    return " ".join(re.sub(r"[^\w\s]", " ", value.casefold()).split())


def speech_metrics(reference: str, hypothesis: str) -> dict[str, float]:
    expected, actual = normalized_text(reference), normalized_text(hypothesis)
    words, characters = expected.split(), expected.replace(" ", "")
    return {
        "wer": edit_distance(words, actual.split()) / max(1, len(words)),
        "cer": edit_distance(characters, actual.replace(" ", ""))
        / max(1, len(characters)),
    }


def evaluate_audio(
    manifest_path: Path, runtime, *, model_id: str, device: str = "cpu"
) -> dict:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    entries = []
    supported = runtime.store.model(model_id).languages
    for sample in manifest["samples"]:
        language = sample["config"].split("_")[0]
        if language not in supported:
            continue
        path = (manifest_path.parent / sample["file"]).resolve()
        if not path.is_relative_to(manifest_path.parent.resolve()):
            raise AudioError(
                "AUDIO_UNSAFE_PATH", "Fixture path escapes manifest directory."
            )
        if file_hash(path) != sample["sha256"]:
            raise AudioError("AUDIO_HASH_MISMATCH", "Audio fixture hash mismatch.")
        for mode, vad, clean in [
            ("original", False, False),
            ("vad", True, False),
            ("cleaned", True, True),
        ]:
            result = runtime.transcribe_result(
                path,
                AudioOptions(
                    model_id=model_id,
                    language=language,
                    device=device,
                    vad=vad,
                    clean=clean,
                ),
            )
            entries.append(
                {
                    "file": sample["file"],
                    "mode": mode,
                    "device": result.device,
                    "text": result.text,
                    "reference": sample["reference"],
                    **speech_metrics(sample["reference"], result.text),
                    "elapsed_seconds": result.elapsed_seconds,
                    "real_time_factor": result.elapsed_seconds
                    / max(result.duration_seconds, 0.001),
                    "duration_seconds": result.duration_seconds,
                    "warnings": result.warnings,
                }
            )
    return {
        "schema_version": 1,
        "model_id": model_id,
        "revision": runtime.store.model(model_id).revision,
        "manifest_sha256": file_hash(manifest_path),
        "results": entries,
    }
