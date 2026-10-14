import json
from pathlib import Path

import pytest

from escolio.app.config import Settings, user_settings_path_for
from escolio.app.settings_presets import (
    SettingPreset,
    apply_settings_preset,
    list_settings_presets,
    preview_settings_preset,
)


def _settings(tmp_path: Path) -> Settings:
    return Settings(
        workspace_dir=tmp_path,
        data_dir=tmp_path / 'data',
        notes_dir=tmp_path / 'data' / 'corpus' / 'notes',
        datasets_dir=tmp_path / 'data' / 'datasets',
        results_dir=tmp_path / 'data' / 'results',
        sqlite_path=tmp_path / 'data' / 'results' / 'escolio.sqlite3',
        vector_store_dir=tmp_path / 'data' / 'results' / 'vector_store',
        embedding_model='fake-hash',
        embedding_device='auto',
        retrieval_top_k=9,
        default_ask_strategy='lexical',
    )


def test_settings_presets_list_v1_without_secrets() -> None:
    presets = {preset.key: preset for preset in list_settings_presets()}

    assert {'cpu_rapido', 'gpu_qualidade', 'vault_grande', 'tcc_reprodutivel'} <= set(presets)
    assert presets['cpu_rapido'].values['embedding_model'] == 'chroma-default'
    assert all('answer_api_key' not in preset.values for preset in presets.values())


def test_preview_settings_preset_does_not_write_user_settings(tmp_path: Path) -> None:
    settings = _settings(tmp_path)

    preview = preview_settings_preset('cpu_rapido', settings=settings)

    assert preview.preset.key == 'cpu_rapido'
    assert preview.values['retrieval_top_k'] == 4
    assert preview.changes['embedding_model'].before == 'fake-hash'
    assert preview.changes['embedding_model'].after == 'chroma-default'
    assert not user_settings_path_for(settings).exists()


def test_unknown_settings_preset_raises_value_error(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match='Preset desconhecido'):
        preview_settings_preset('nao_existe', settings=_settings(tmp_path))


def test_apply_cpu_rapido_persists_one_validated_payload(tmp_path: Path) -> None:
    settings = _settings(tmp_path)

    result = apply_settings_preset('cpu_rapido', settings=settings)
    payload = json.loads(user_settings_path_for(settings).read_text(encoding='utf-8'))

    assert result.preset.key == 'cpu_rapido'
    assert result.settings.embedding_model == 'chroma-default'
    assert payload == {
        'default_ask_strategy': 'hybrid',
        'default_chunk_overlap': 120,
        'default_chunk_size': 800,
        'embedding_device': 'cpu',
        'embedding_model': 'chroma-default',
        'retrieval_top_k': 4,
    }


def test_invalid_preset_fails_before_writing(tmp_path: Path, monkeypatch) -> None:
    settings = _settings(tmp_path)
    broken = SettingPreset(
        key='broken',
        label='Broken',
        description='Preset invalido para teste.',
        values={'answer_api_key': 'secret'},
    )
    monkeypatch.setattr('escolio.app.settings_presets.SETTING_PRESETS', (broken,))

    with pytest.raises(ValueError, match='answer_api_key'):
        apply_settings_preset('broken', settings=settings)

    assert not user_settings_path_for(settings).exists()
