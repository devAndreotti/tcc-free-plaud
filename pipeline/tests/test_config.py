import json
from pathlib import Path

import pytest

from escolio.app.config import (
    Settings,
    get_settings,
    reset_user_settings,
    save_user_settings,
    user_settings_path_for,
)


def test_settings_have_consistent_defaults() -> None:
    settings = Settings()
    assert settings.default_chunk_size > settings.default_chunk_overlap
    assert settings.retrieval_top_k >= 1


def test_settings_reject_invalid_chunk_window() -> None:
    with pytest.raises(ValueError, match='default_chunk_overlap deve ser menor que default_chunk_size'):
        Settings(default_chunk_size=100, default_chunk_overlap=100)


def test_settings_keep_runtime_data_inside_workspace(monkeypatch) -> None:
    # Sem isso, um free_plaud.sqlite3 legado no disco do dev ativa o fallback de legacy.py.
    monkeypatch.setattr('escolio.app.config.resolve_legacy_sqlite_path', lambda path: path)
    settings = Settings()

    assert settings.data_dir == settings.workspace_dir / 'data'
    assert settings.notes_dir == settings.workspace_dir / 'data' / 'corpus' / 'notes'
    assert settings.datasets_dir == settings.workspace_dir / 'data' / 'datasets'
    assert settings.results_dir == settings.workspace_dir / 'data' / 'results'
    assert settings.sqlite_path == settings.workspace_dir / 'data' / 'results' / 'escolio.sqlite3'
    assert settings.vector_store_dir == settings.workspace_dir / 'data' / 'results' / 'vector_store'


def test_user_settings_json_overrides_defaults_after_cache_clear(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv('ESCOLIO_RETRIEVAL_TOP_K', raising=False)
    monkeypatch.setenv('ESCOLIO_WORKSPACE_DIR', str(tmp_path))
    monkeypatch.setenv('ESCOLIO_RESULTS_DIR', str(tmp_path / 'data' / 'results'))
    get_settings.cache_clear()
    path = tmp_path / 'data' / 'results' / 'user_settings.json'
    path.parent.mkdir(parents=True)
    path.write_text(
        json.dumps(
            {
                'embedding_device': 'auto',
                'retrieval_top_k': 9,
                'default_ask_strategy': 'lexical',
                'default_corpus_path': str(tmp_path / 'vault'),
                'corpus_recursive_default': False,
            }
        ),
        encoding='utf-8',
    )

    settings = get_settings()

    assert settings.embedding_device == 'auto'
    assert settings.retrieval_top_k == 9
    assert settings.default_ask_strategy == 'lexical'
    assert settings.default_corpus_path == tmp_path / 'vault'
    assert settings.corpus_recursive_default is False


def test_env_keeps_priority_over_user_settings_json(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv('ESCOLIO_WORKSPACE_DIR', str(tmp_path))
    monkeypatch.setenv('ESCOLIO_RESULTS_DIR', str(tmp_path / 'data' / 'results'))
    monkeypatch.setenv('ESCOLIO_RETRIEVAL_TOP_K', '13')
    path = tmp_path / 'data' / 'results' / 'user_settings.json'
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({'retrieval_top_k': 3}), encoding='utf-8')
    get_settings.cache_clear()

    assert get_settings().retrieval_top_k == 13


def test_save_and_reset_user_settings_round_trip(tmp_path: Path) -> None:
    settings = Settings(
        workspace_dir=tmp_path,
        data_dir=tmp_path / 'data',
        notes_dir=tmp_path / 'data' / 'corpus' / 'notes',
        datasets_dir=tmp_path / 'data' / 'datasets',
        results_dir=tmp_path / 'data' / 'results',
        sqlite_path=tmp_path / 'data' / 'results' / 'escolio.sqlite3',
        vector_store_dir=tmp_path / 'data' / 'results' / 'vector_store',
    )

    updated = save_user_settings(
        {
            'embedding_device': 'cuda',
            'default_chunk_size': 900,
            'corpus_index_workers': 2,
        },
        settings=settings,
    )
    path = user_settings_path_for(settings)

    assert updated.embedding_device == 'cuda'
    assert updated.default_chunk_size == 900
    assert json.loads(path.read_text(encoding='utf-8')) == {
        'corpus_index_workers': 2,
        'default_chunk_size': 900,
        'embedding_device': 'cuda',
    }

    reset_user_settings(settings=settings)

    assert not path.exists()


def test_save_user_settings_rejects_invalid_chunk_window_before_writing(tmp_path: Path) -> None:
    settings = Settings(
        workspace_dir=tmp_path,
        data_dir=tmp_path / 'data',
        notes_dir=tmp_path / 'data' / 'corpus' / 'notes',
        datasets_dir=tmp_path / 'data' / 'datasets',
        results_dir=tmp_path / 'data' / 'results',
        sqlite_path=tmp_path / 'data' / 'results' / 'escolio.sqlite3',
        vector_store_dir=tmp_path / 'data' / 'results' / 'vector_store',
    )

    with pytest.raises(ValueError, match='default_chunk_overlap deve ser menor que default_chunk_size'):
        save_user_settings({'default_chunk_size': 100, 'default_chunk_overlap': 100}, settings=settings)

    assert not user_settings_path_for(settings).exists()


def test_save_user_settings_returns_effective_env_override(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv('ESCOLIO_RESULTS_DIR', str(tmp_path / 'data' / 'results'))
    monkeypatch.setenv('ESCOLIO_EMBEDDING_DEVICE', 'cpu')
    get_settings.cache_clear()

    updated = save_user_settings({'embedding_device': 'cuda'})
    path = tmp_path / 'data' / 'results' / 'user_settings.json'

    assert json.loads(path.read_text(encoding='utf-8')) == {'embedding_device': 'cuda'}
    assert updated.embedding_device == 'cpu'

    get_settings.cache_clear()


def test_answer_api_key_is_env_only_not_user_settings(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv('ESCOLIO_RESULTS_DIR', str(tmp_path / 'data' / 'results'))
    monkeypatch.setenv('ESCOLIO_ANSWER_API_KEY', 'secret-key')
    get_settings.cache_clear()

    settings = get_settings()

    assert settings.answer_api_key == 'secret-key'
    assert 'answer_api_key' not in save_user_settings({'answer_provider': 'ollama'}).model_dump(mode='json')
    payload = json.loads((tmp_path / 'data' / 'results' / 'user_settings.json').read_text(encoding='utf-8'))
    assert 'answer_api_key' not in payload

    get_settings.cache_clear()


def test_sanitize_ui_sentinels_cleans_enum_strings():
    from escolio.app.config import Settings
    s = Settings(answer_model="Select.NULL", default_corpus_path="Select.BLANK")
    assert s.answer_model == ""
    assert s.default_corpus_path is None
