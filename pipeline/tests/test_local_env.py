import os
from pathlib import Path

from escolio.app.config import Settings
from escolio.app.local_env import (
    ANSWER_API_KEY_ENV,
    answer_api_key_is_configured,
    local_env_path_for,
    save_answer_api_key,
)


def _settings(tmp_path: Path) -> Settings:
    return Settings(
        workspace_dir=tmp_path,
        data_dir=tmp_path / 'data',
        results_dir=tmp_path / 'data' / 'results',
        sqlite_path=tmp_path / 'data' / 'results' / 'escolio.sqlite3',
        vector_store_dir=tmp_path / 'data' / 'results' / 'vector_store',
    )


def test_save_answer_api_key_writes_pipeline_env_and_sets_runtime_env(tmp_path: Path, monkeypatch) -> None:
    settings = _settings(tmp_path)
    monkeypatch.delenv(ANSWER_API_KEY_ENV, raising=False)

    path = save_answer_api_key('sk-local-test', settings=settings)

    assert path == tmp_path / 'pipeline' / '.env'
    assert local_env_path_for(settings) == path
    assert path.read_text(encoding='utf-8').strip() == f'{ANSWER_API_KEY_ENV}=sk-local-test'
    assert os.environ[ANSWER_API_KEY_ENV] == 'sk-local-test'
    assert answer_api_key_is_configured(settings=settings) is True


def test_save_answer_api_key_blank_removes_secret(tmp_path: Path, monkeypatch) -> None:
    settings = _settings(tmp_path)
    monkeypatch.delenv(ANSWER_API_KEY_ENV, raising=False)

    path = save_answer_api_key('sk-local-test', settings=settings)
    save_answer_api_key('', settings=settings)

    assert ANSWER_API_KEY_ENV not in os.environ
    assert ANSWER_API_KEY_ENV not in path.read_text(encoding='utf-8')
    assert answer_api_key_is_configured(settings=settings) is False
