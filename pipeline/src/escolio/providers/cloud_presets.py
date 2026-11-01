"""Provedores de nuvem no padrão OpenAI que a tela Fontes de IA oferece, cada um com a sua chave.

Todos usam o provider `openai-compatible`; o preset só fixa a URL e o nome da variável da chave
(`ESCOLIO_<PRESET>_API_KEY`). Sem dependência de config para poder ser importado por ela.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class CloudPreset:
    id: str
    label: str
    base_url: str

    @property
    def key_env(self) -> str:
        return f'ESCOLIO_{self.id.upper()}_API_KEY'

    @property
    def key_field(self) -> str:
        return f'{self.id}_api_key'


CLOUD_PRESETS: dict[str, CloudPreset] = {
    preset.id: preset
    for preset in (
        CloudPreset('openai', 'OpenAI', 'https://api.openai.com/v1'),
        CloudPreset('openrouter', 'OpenRouter', 'https://openrouter.ai/api/v1'),
        CloudPreset('groq', 'Groq', 'https://api.groq.com/openai/v1'),
        CloudPreset('gemini', 'Google Gemini', 'https://generativelanguage.googleapis.com/v1beta/openai'),
    )
}

# Modelos que a API lista mas não escrevem texto (vetores, áudio, imagem, moderação).
NON_CHAT_MARKERS = ('embed', 'whisper', 'tts', 'dall-e', 'moderation', 'transcribe', 'audio', 'image', 'realtime', 'rerank')


def preset_for_base_url(base_url: str | None) -> CloudPreset | None:
    normalized = (base_url or '').strip().rstrip('/').lower()
    return next((preset for preset in CLOUD_PRESETS.values() if preset.base_url.lower() == normalized), None)


def is_chat_model(model_id: str) -> bool:
    lowered = model_id.lower()
    return not any(marker in lowered for marker in NON_CHAT_MARKERS)
