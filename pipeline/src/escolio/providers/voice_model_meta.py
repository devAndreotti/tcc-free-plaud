"""Curated UI metadata for voice models, kept separate from the hash-verified
catalog (`VoiceModel` in `audio_catalog.py`). Mirrors `ModelCatalogEntry` /
`MODEL_CATALOG` in `providers/provisioning.py`: descriptive text and UI hints
don't belong in a schema whose only job is byte-for-byte download integrity.
"""

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class VoiceModelUiMeta:
    model_id: str
    label: str
    description: str
    speed_tier: Literal["rapido", "medio", "lento"]
    quality_tier: Literal["basica", "boa", "alta"]
    recommended: bool = False
    # True apenas para engines que suportam deteccao automatica de idioma de
    # verdade (hoje so faster-whisper, via language=None). Ver providers/audio_engines.py.
    supports_auto_language: bool = False
    # False para componentes internos (ex.: VAD) que aparecem na aba Voz para
    # poder ser baixados, mas nunca devem ser oferecidos como modelo de transcricao.
    selectable: bool = True


VOICE_MODEL_UI_META: tuple[VoiceModelUiMeta, ...] = (
    VoiceModelUiMeta(
        model_id="whisper-small",
        label="Whisper Small",
        description="Multilíngue, boa precisão geral.",
        speed_tier="medio",
        quality_tier="alta",
        recommended=True,
        supports_auto_language=True,
    ),
    VoiceModelUiMeta(
        model_id="moonshine-tiny-en",
        label="Moonshine Tiny",
        description="Só inglês, muito rápido e leve.",
        speed_tier="rapido",
        quality_tier="basica",
    ),
    VoiceModelUiMeta(
        model_id="sensevoice-small",
        label="SenseVoice Small",
        description="Multilíngue (zh/en/ja/ko/yue), boa precisão.",
        speed_tier="medio",
        quality_tier="boa",
    ),
    VoiceModelUiMeta(
        model_id="sensevoice-gguf-q8",
        label="SenseVoice GGUF Q8",
        description="Variante quantizada; menor, com precisão um pouco menor.",
        speed_tier="rapido",
        quality_tier="boa",
    ),
    VoiceModelUiMeta(
        model_id="silero-vad",
        label="Detector de fala (VAD)",
        description="Componente interno usado para detectar trechos com fala antes de transcrever; necessário para gravar áudio, não é um modelo de transcrição.",
        speed_tier="rapido",
        quality_tier="alta",
        selectable=False,
    ),
)

_BY_ID = {meta.model_id: meta for meta in VOICE_MODEL_UI_META}


def ui_meta_for(model_id: str) -> VoiceModelUiMeta | None:
    return _BY_ID.get(model_id)
