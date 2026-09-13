import hashlib

import pytest

import free_plaud.providers.audio_catalog as free_plaud_audio_catalog
from free_plaud.providers.audio_catalog import (
    ModelFile,
    ModelStore,
    VoiceModel,
    load_catalog,
)
from free_plaud.providers.audio_models import AudioError


@pytest.fixture
def store(tmp_path):
    data = b"verified model data"
    model = VoiceModel(
        id="sample",
        engine="moonshine",
        format="onnx",
        repo_id="test/model",
        revision="a" * 40,
        languages=["en"],
        license="MIT",
        files=[
            ModelFile(
                path="nested/model.onnx",
                size=len(data),
                sha256=hashlib.sha256(data).hexdigest(),
            )
        ],
    )
    return ModelStore(tmp_path / "models", {"sample": model})


def test_packaged_catalog_contains_reproducible_formats():
    catalog = load_catalog()
    assert {"onnx", "gguf", "ctranslate2"} == {m.format for m in catalog.values()}
    assert "pt" in catalog["whisper-small"].languages
    assert "pt" not in catalog["moonshine-tiny-en"].languages
    assert catalog["sensevoice-gguf-q8"].engine == "catalog-only"


def test_offline_missing_and_unknown_model(store):
    assert not store.verify("sample")
    with pytest.raises(AudioError) as caught:
        store.require("sample")
    assert caught.value.code == "AUDIO_MODEL_NOT_READY"
    with pytest.raises(AudioError):
        store.model("unknown")


def test_download_publish_hash_and_cached_use(store, monkeypatch, tmp_path):
    cached = tmp_path / "download"
    cached.write_bytes(b"verified model data")
    calls = []

    def download(**kwargs):
        calls.append(kwargs)
        return str(cached)

    monkeypatch.setattr("huggingface_hub.hf_hub_download", download)
    progress = []
    directory = store.download("sample", lambda *args: progress.append(args))
    assert store.require("sample") == directory
    assert progress[-1] == ("sample", 19, 19)
    assert calls[0]["revision"] == "a" * 40
    assert calls[0]["token"] is False
    assert calls[0]["cache_dir"].is_relative_to(store.root)
    store.download("sample")
    assert len(calls) == 1
    (directory / "nested/model.onnx").write_bytes(b"x" * 19)
    assert not store.verify("sample")
    store.download("sample")
    assert store.verify("sample")
    assert list(directory.parent.glob("*.invalid-*"))


def test_corrupt_or_interrupted_download_never_publishes(store, monkeypatch, tmp_path):
    cached = tmp_path / "download"
    cached.write_bytes(b"wrong")
    monkeypatch.setattr("huggingface_hub.hf_hub_download", lambda **kwargs: str(cached))
    with pytest.raises(AudioError) as caught:
        store.download("sample")
    assert caught.value.code == "AUDIO_HASH_MISMATCH"
    assert not store.verify("sample")

    def broken(**kwargs):
        raise OSError("connection interrupted")

    monkeypatch.setattr("huggingface_hub.hf_hub_download", broken)
    with pytest.raises(OSError):
        store.download("sample")
    assert not store.directory("sample").exists()


@pytest.mark.parametrize(
    "path", ["../model", "/model", "C:/model", "a\\model", "./model", "a/../model"]
)
def test_paths_cannot_escape_model_cache(path):
    with pytest.raises(ValueError):
        ModelFile(path=path, size=1, sha256="a" * 64)


def test_verify_caches_hash_by_mtime_and_size(store, monkeypatch, tmp_path):
    cached = tmp_path / "download"
    cached.write_bytes(b"verified model data")
    monkeypatch.setattr("huggingface_hub.hf_hub_download", lambda **kwargs: str(cached))
    store.download("sample")

    calls = []
    real_file_hash = free_plaud_audio_catalog.file_hash
    monkeypatch.setattr(
        free_plaud_audio_catalog,
        "file_hash",
        lambda path: (calls.append(path), real_file_hash(path))[1],
    )

    assert store.verify("sample") is True
    assert len(calls) == 1
    assert store.verify("sample") is True
    assert len(calls) == 1, "segunda chamada nao deveria recalcular o hash (mtime/size inalterados)"

    directory = store.directory("sample")
    (directory / "nested/model.onnx").write_bytes(b"x" * len(b"verified model data"))
    assert store.verify("sample") is False
    assert len(calls) == 2, "arquivo mudou (mtime novo) - deve recalcular o hash"


def test_duplicate_catalog_file_rejected(store):
    item = store.model("sample").model_dump()
    item["files"] *= 2
    with pytest.raises(ValueError):
        VoiceModel.model_validate(item)
