"""Offline catalogue and atomic, verified Hugging Face downloads."""

import hashlib
import json
import shutil
from collections.abc import Callable
from importlib.resources import files
from pathlib import Path, PurePosixPath
from typing import Literal

from filelock import FileLock
from pydantic import BaseModel, Field, field_validator, model_validator

from free_plaud.providers.audio_models import AudioError


class ModelFile(BaseModel):
    path: str
    size: int = Field(gt=0)
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")

    @field_validator("path")
    @classmethod
    def safe_path(cls, value: str) -> str:
        path = PurePosixPath(value)
        if (
            not value
            or path.is_absolute()
            or any(p in ("..", ".") for p in value.split("/"))
            or "\\" in value
            or ":" in value
        ):
            raise ValueError("Model file must be a safe relative path.")
        return value


class VoiceModel(BaseModel):
    id: str = Field(pattern=r"^[a-z0-9][a-z0-9-]*$")
    engine: Literal[
        "silero", "faster-whisper", "sensevoice", "moonshine", "catalog-only"
    ]
    format: Literal["onnx", "ctranslate2", "gguf"]
    repo_id: str
    revision: str = Field(pattern=r"^[a-f0-9]{40}$")
    languages: list[str]
    license: str
    files: list[ModelFile] = Field(min_length=1)

    @model_validator(mode="after")
    def unique_files(self) -> "VoiceModel":
        names = [f.path for f in self.files]
        if len(set(names)) != len(names):
            raise ValueError("Duplicate model files.")
        return self


def load_catalog() -> dict[str, VoiceModel]:
    payload = json.loads(
        files("free_plaud.providers")
        .joinpath("models_catalog.json")
        .read_text(encoding="utf-8")
    )
    models = [VoiceModel.model_validate(item) for item in payload["models"]]
    result = {model.id: model for model in models}
    if len(result) != len(models):
        raise ValueError("Duplicate model IDs.")
    return result


def file_hash(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


class ModelStore:
    def __init__(self, root: Path, catalog: dict[str, VoiceModel] | None = None):
        self.root = Path(root).resolve()
        self.catalog = load_catalog() if catalog is None else catalog

    def model(self, model_id: str) -> VoiceModel:
        if model_id not in self.catalog:
            raise AudioError("AUDIO_MODEL_UNKNOWN", f"Unknown voice model: {model_id}")
        return self.catalog[model_id]

    def directory(self, model_id: str) -> Path:
        model = self.model(model_id)
        return self.root / model.id / model.revision

    def _valid(self, directory: Path, model: VoiceModel) -> bool:
        for item in model.files:
            path = directory / item.path
            if not path.resolve().is_relative_to(self.root):
                return False
            if (
                not path.is_file()
                or path.stat().st_size != item.size
                or file_hash(path) != item.sha256
            ):
                return False
        return True

    def verify(self, model_id: str) -> bool:
        return self._valid(self.directory(model_id), self.model(model_id))

    def require(self, model_id: str) -> Path:
        if not self.verify(model_id):
            raise AudioError(
                "AUDIO_MODEL_NOT_READY",
                f"Model {model_id} missing or corrupt; download/verify it explicitly.",
            )
        return self.directory(model_id)

    def download(
        self, model_id: str, progress: Callable[[str, int, int], None] | None = None
    ) -> Path:
        from huggingface_hub import hf_hub_download

        model = self.model(model_id)
        target = self.directory(model_id)
        target.parent.mkdir(parents=True, exist_ok=True)
        with FileLock(str(target.parent / ".download.lock")):
            if self.verify(model_id):
                return target
            staging = target.parent / (model.revision + ".partial")
            staging.mkdir(exist_ok=True)
            total = sum(item.size for item in model.files)
            completed = 0
            for item in model.files:
                cached = Path(
                    hf_hub_download(
                        repo_id=model.repo_id,
                        revision=model.revision,
                        filename=item.path,
                        cache_dir=self.root / ".hf-cache",
                        token=False,
                    )
                )
                if (
                    cached.stat().st_size != item.size
                    or file_hash(cached) != item.sha256
                ):
                    raise AudioError(
                        "AUDIO_HASH_MISMATCH", f"Hash verification failed: {item.path}"
                    )
                destination = staging / item.path
                if not destination.resolve().is_relative_to(self.root):
                    raise AudioError(
                        "AUDIO_UNSAFE_PATH", "Model destination escapes storage root."
                    )
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(cached, destination)
                completed += item.size
                if progress:
                    progress(model_id, completed, total)
            if not self._valid(staging, model):
                raise AudioError(
                    "AUDIO_HASH_MISMATCH", "Staged model did not pass verification."
                )
            # Keep a corrupt prior installation for inspection; never delete user files.
            if target.exists():
                from uuid import uuid4

                target.rename(
                    target.with_name(target.name + ".invalid-" + uuid4().hex[:8])
                )
            staging.rename(target)
        return target
