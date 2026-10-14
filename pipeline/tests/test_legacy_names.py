"""Compatibilidade com os nomes antigos (free-plaud): env, .env, SQLite e collection."""

from pathlib import Path

import chromadb
import pytest
from chromadb.config import Settings as ChromaSettings

from escolio.app import local_env
from escolio.app.config import Settings, get_settings
from escolio.app.legacy import (
    DEFAULT_CHROMA_COLLECTION,
    LEGACY_CHROMA_COLLECTION,
    resolve_legacy_sqlite_path,
)
from escolio.storage.vector import LocalVectorStore


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in (
        'ESCOLIO_RETRIEVAL_TOP_K',
        'FREE_PLAUD_RETRIEVAL_TOP_K',
        'ESCOLIO_ANSWER_API_KEY',
        'FREE_PLAUD_ANSWER_API_KEY',
    ):
        # setenv + delenv registra a restauracao: a variavel some ao fim de cada teste.
        monkeypatch.setenv(name, 'x')
        monkeypatch.delenv(name)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def workdir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.chdir(tmp_path)
    return tmp_path


def test_new_env_var_is_used(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv('ESCOLIO_RETRIEVAL_TOP_K', '11')
    assert Settings().retrieval_top_k == 11


def test_legacy_env_var_is_used_as_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv('FREE_PLAUD_RETRIEVAL_TOP_K', '12')
    assert Settings().retrieval_top_k == 12


def test_new_env_var_wins_over_legacy(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv('FREE_PLAUD_RETRIEVAL_TOP_K', '12')
    monkeypatch.setenv('ESCOLIO_RETRIEVAL_TOP_K', '13')
    assert Settings().retrieval_top_k == 13


def test_legacy_dotenv_is_used_as_fallback(workdir: Path) -> None:
    (workdir / 'pipeline').mkdir()
    (workdir / 'pipeline' / '.env').write_text('FREE_PLAUD_RETRIEVAL_TOP_K=14\n', encoding='utf-8')
    assert Settings().retrieval_top_k == 14


def test_new_dotenv_wins_over_legacy_dotenv(workdir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (workdir / 'pipeline').mkdir()
    (workdir / 'pipeline' / '.env').write_text(
        'FREE_PLAUD_RETRIEVAL_TOP_K=14\nESCOLIO_RETRIEVAL_TOP_K=15\n', encoding='utf-8'
    )
    assert Settings().retrieval_top_k == 15


def test_legacy_answer_key_in_dotenv_is_read(workdir: Path) -> None:
    (workdir / 'pipeline').mkdir()
    (workdir / 'pipeline' / '.env').write_text('FREE_PLAUD_ANSWER_API_KEY=sk-old\n', encoding='utf-8')
    settings = Settings(workspace_dir=workdir)
    assert settings.answer_api_key == 'sk-old'
    assert local_env.answer_api_key_is_configured(settings=settings) is True


def test_save_answer_key_migrates_legacy_dotenv_line(workdir: Path) -> None:
    env_file = workdir / 'pipeline' / '.env'
    env_file.parent.mkdir()
    env_file.write_text('OUTRA=1\nFREE_PLAUD_ANSWER_API_KEY=sk-old\n', encoding='utf-8')

    local_env.save_answer_api_key('sk-new', settings=Settings(workspace_dir=workdir))

    content = env_file.read_text(encoding='utf-8')
    assert 'ESCOLIO_ANSWER_API_KEY=sk-new' in content
    assert 'FREE_PLAUD_ANSWER_API_KEY' not in content
    assert 'OUTRA=1' in content
    assert Settings().answer_api_key == 'sk-new'


def test_legacy_sqlite_is_used_when_default_is_missing(tmp_path: Path) -> None:
    legacy = tmp_path / 'free_plaud.sqlite3'
    legacy.write_bytes(b'')
    assert resolve_legacy_sqlite_path(tmp_path / 'escolio.sqlite3') == legacy


def test_new_sqlite_wins_when_both_exist(tmp_path: Path) -> None:
    (tmp_path / 'free_plaud.sqlite3').write_bytes(b'')
    new = tmp_path / 'escolio.sqlite3'
    new.write_bytes(b'')
    assert resolve_legacy_sqlite_path(new) == new


def test_sqlite_without_any_file_keeps_new_name(tmp_path: Path) -> None:
    new = tmp_path / 'escolio.sqlite3'
    assert resolve_legacy_sqlite_path(new) == new


def test_explicit_sqlite_path_is_not_redirected(tmp_path: Path) -> None:
    (tmp_path / 'free_plaud.sqlite3').write_bytes(b'')
    explicit = tmp_path / 'custom.sqlite3'
    assert Settings(sqlite_path=explicit).sqlite_path == explicit


def test_vector_store_opens_legacy_collection_when_only_legacy_exists(tmp_path: Path) -> None:
    store_dir = tmp_path / 'vector_store'
    client = chromadb.PersistentClient(path=str(store_dir), settings=ChromaSettings(anonymized_telemetry=False))
    client.get_or_create_collection(name=LEGACY_CHROMA_COLLECTION)
    del client

    store = LocalVectorStore(store_dir, collection_name=DEFAULT_CHROMA_COLLECTION)

    assert store.collection_name == LEGACY_CHROMA_COLLECTION


def test_vector_store_uses_new_collection_on_fresh_store(tmp_path: Path) -> None:
    store = LocalVectorStore(tmp_path / 'vector_store', collection_name=DEFAULT_CHROMA_COLLECTION)
    assert store.collection_name == DEFAULT_CHROMA_COLLECTION


def test_vector_store_prefers_new_collection_when_both_exist(tmp_path: Path) -> None:
    store_dir = tmp_path / 'vector_store'
    client = chromadb.PersistentClient(path=str(store_dir), settings=ChromaSettings(anonymized_telemetry=False))
    client.get_or_create_collection(name=LEGACY_CHROMA_COLLECTION)
    client.get_or_create_collection(name=DEFAULT_CHROMA_COLLECTION)
    del client

    store = LocalVectorStore(store_dir, collection_name=DEFAULT_CHROMA_COLLECTION)

    assert store.collection_name == DEFAULT_CHROMA_COLLECTION
