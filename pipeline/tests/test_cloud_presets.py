from pathlib import Path

import pytest

from escolio.app.config import Settings
from escolio.app.local_env import cloud_keys_configured, save_answer_api_key
from escolio.providers.cloud_presets import (
    CLOUD_PRESETS,
    is_chat_model,
    preset_for_base_url,
)


@pytest.fixture(autouse=True)
def _sem_chaves_no_ambiente(monkeypatch: pytest.MonkeyPatch) -> None:
    for preset in CLOUD_PRESETS.values():
        monkeypatch.delenv(preset.key_env, raising=False)
    monkeypatch.delenv('ESCOLIO_ANSWER_API_KEY', raising=False)


def _settings(**values: object) -> Settings:
    return Settings(_env_file=None, **values)


def test_chave_do_preset_vale_quando_a_url_e_dele(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv('ESCOLIO_OPENROUTER_API_KEY', 'sk-or-123')

    openrouter = _settings(answer_provider='openai-compatible', answer_base_url='https://openrouter.ai/api/v1/', answer_api_key='geral')
    outra_url = _settings(answer_provider='openai-compatible', answer_base_url='https://meu-servidor/v1', answer_api_key='geral')
    local = _settings(answer_provider='ollama', answer_base_url='https://openrouter.ai/api/v1')

    assert openrouter.answer_api_key == 'sk-or-123'
    assert outra_url.answer_api_key == 'geral'
    assert local.answer_api_key is None


def test_chave_salva_por_provedor_aparece_como_configurada(tmp_path: Path) -> None:
    settings = _settings(workspace_dir=tmp_path)

    path = save_answer_api_key('gsk-abc', settings=settings, preset='groq')

    assert 'ESCOLIO_GROQ_API_KEY=gsk-abc' in path.read_text(encoding='utf-8')
    assert cloud_keys_configured(settings=settings) == {'openai': False, 'openrouter': False, 'groq': True, 'gemini': False}

    save_answer_api_key('', settings=settings, preset='groq')
    assert cloud_keys_configured(settings=settings)['groq'] is False


def test_provedor_desconhecido_e_recusado(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match='desconhecido'):
        save_answer_api_key('x', settings=_settings(workspace_dir=tmp_path), preset='azure')


def test_url_do_preset_ignora_barra_final_e_caixa() -> None:
    assert preset_for_base_url('HTTPS://api.groq.com/openai/v1/') is CLOUD_PRESETS['groq']
    assert preset_for_base_url('http://localhost:11434/v1') is None


def test_modelos_que_nao_conversam_saem_da_lista() -> None:
    assert not is_chat_model('text-embedding-3-small')
    assert not is_chat_model('whisper-large-v3')
    assert not is_chat_model('openai/tts-1')
    assert is_chat_model('meta-llama/llama-3.3-70b-instruct')
