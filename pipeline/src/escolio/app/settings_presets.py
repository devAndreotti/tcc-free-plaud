from typing import Any

from pydantic import BaseModel, Field

from escolio.app.config import (
    USER_SETTING_FIELDS,
    Settings,
    get_settings,
    save_user_settings,
)


class SettingPreset(BaseModel):
    key: str
    label: str
    description: str
    values: dict[str, Any] = Field(default_factory=dict)


class SettingPresetChange(BaseModel):
    before: Any
    after: Any


class SettingPresetPreview(BaseModel):
    preset: SettingPreset
    values: dict[str, Any]
    changes: dict[str, SettingPresetChange]


class SettingPresetApplyResult(SettingPresetPreview):
    settings: Settings = Field(exclude=True)


SETTING_PRESETS: tuple[SettingPreset, ...] = (
    SettingPreset(
        key='cpu_rapido',
        label='CPU rápido',
        description='Notebook sem GPU dedicada; usa o modelo de busca semântica Chroma e busca hybrid.',
        values={
            'embedding_model': 'chroma-default',
            'embedding_device': 'cpu',
            'retrieval_top_k': 4,
            'default_ask_strategy': 'hybrid',
            'default_chunk_size': 800,
            'default_chunk_overlap': 120,
        },
    ),
    SettingPreset(
        key='gpu_qualidade',
        label='GPU qualidade',
        description='GPU NVIDIA com PyTorch CUDA instalado; usa Sentence Transformers multilíngue.',
        values={
            'embedding_model': 'sentence-transformer:sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2',
            'embedding_device': 'cuda',
            'retrieval_top_k': 5,
        },
    ),
    SettingPreset(
        key='vault_grande',
        label='Vault grande',
        description='Obsidian grande; prioriza micro-lotes e progresso parcial perguntável.',
        values={
            'corpus_commit_mode': 'microbatch',
            'corpus_embedding_batch_size': 64,
            'corpus_index_workers': 2,
            'corpus_recursive_default': True,
        },
    ),
    SettingPreset(
        key='tcc_reprodutivel',
        label='TCC reprodutível',
        description='Benchmark e resultados comparáveis com provider extractive.',
        values={
            'default_ask_strategy': 'hybrid',
            'retrieval_top_k': 5,
            'default_chunk_size': 800,
            'default_chunk_overlap': 120,
            'answer_provider': 'extractive',
        },
    ),
)


def list_settings_presets() -> tuple[SettingPreset, ...]:
    return SETTING_PRESETS


def get_settings_preset(key: str) -> SettingPreset:
    for preset in SETTING_PRESETS:
        if preset.key == key:
            return preset
    raise ValueError(f'Preset desconhecido: {key}')


def _json_value(value: Any) -> Any:
    if hasattr(value, 'as_posix'):
        return str(value)
    return value


def _validated_values(preset: SettingPreset, settings: Settings) -> dict[str, Any]:
    values = dict(preset.values)
    invalid = sorted(key for key in values if key not in USER_SETTING_FIELDS)
    if invalid:
        raise ValueError(f'Preset {preset.key} contem setting nao editavel: {", ".join(invalid)}')

    validation_data = settings.model_dump()
    validation_data.update(values)
    Settings(**validation_data)
    return values


def preview_settings_preset(key: str, *, settings: Settings | None = None) -> SettingPresetPreview:
    resolved = settings or get_settings()
    preset = get_settings_preset(key)
    values = _validated_values(preset, resolved)
    changes: dict[str, SettingPresetChange] = {}
    for field, after in values.items():
        before = _json_value(getattr(resolved, field))
        if before != after:
            changes[field] = SettingPresetChange(before=before, after=after)
    return SettingPresetPreview(preset=preset, values=values, changes=changes)


def apply_settings_preset(
    key: str, *, settings: Settings | None = None, exclude: tuple[str, ...] = ()
) -> SettingPresetApplyResult:
    resolved = settings or get_settings()
    preview = preview_settings_preset(key, settings=resolved)
    values = {field: value for field, value in preview.values.items() if field not in exclude}
    changes = {field: change for field, change in preview.changes.items() if field not in exclude}
    updated = save_user_settings(values, settings=resolved if settings is not None else None)
    return SettingPresetApplyResult(
        preset=preview.preset,
        values=values,
        changes=changes,
        settings=updated,
    )
