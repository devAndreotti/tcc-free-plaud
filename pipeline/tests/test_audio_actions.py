from __future__ import annotations

from pathlib import Path

from free_plaud.app.config import Settings
from free_plaud.tui.audio_actions import list_voice_models


def _settings(tmp_path: Path) -> Settings:
    return Settings(results_dir=tmp_path)


def test_list_voice_models_includes_vad_as_non_selectable(tmp_path: Path) -> None:
    models = list_voice_models(settings=_settings(tmp_path))
    by_id = {model['id']: model for model in models}

    assert 'whisper-small' in by_id
    assert by_id['whisper-small']['selectable'] is True
    assert 'silero-vad' in by_id
    assert by_id['silero-vad']['selectable'] is False
    assert by_id['silero-vad']['label'] == 'Detector de fala (VAD)'


def test_list_voice_models_includes_ui_metadata(tmp_path: Path) -> None:
    models = list_voice_models(settings=_settings(tmp_path))
    whisper = next(model for model in models if model['id'] == 'whisper-small')

    assert whisper['label'] == 'Whisper Small'
    assert whisper['description']
    assert whisper['speed_tier'] in ('rapido', 'medio', 'lento')
    assert whisper['quality_tier'] in ('basica', 'boa', 'alta')
    assert whisper['recommended'] is True
    assert whisper['supports_auto_language'] is True
    assert whisper['size_bytes'] == sum(item['size'] for item in whisper['files'])
    assert whisper['installed'] is False


def test_list_voice_models_defaults_metadata_for_unknown_id(tmp_path: Path, monkeypatch) -> None:
    # Um modelo no catalogo sem entrada em VOICE_MODEL_UI_META nao deve quebrar
    # a listagem - so cai nos defaults (label=id, tiers=None, recommended=False).
    monkeypatch.setattr('free_plaud.tui.audio_actions.ui_meta_for', lambda model_id: None)

    models = list_voice_models(settings=_settings(tmp_path))
    whisper = next(model for model in models if model['id'] == 'whisper-small')

    assert whisper['label'] == 'whisper-small'
    assert whisper['description'] == ''
    assert whisper['speed_tier'] is None
    assert whisper['recommended'] is False
    assert whisper['supports_auto_language'] is False


def test_list_voice_models_marks_installed_when_verified(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(
        'free_plaud.providers.audio_catalog.ModelStore.verify',
        lambda self, model_id: model_id == 'whisper-small',
    )

    models = list_voice_models(settings=_settings(tmp_path))
    by_id = {model['id']: model for model in models}

    assert by_id['whisper-small']['installed'] is True
    assert by_id['moonshine-tiny-en']['installed'] is False
