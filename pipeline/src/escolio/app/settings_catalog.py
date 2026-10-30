from pathlib import Path
from typing import Any

from annotated_types import Ge, Le
from pydantic import ValidationError

from escolio.app.config import Settings, base_settings, get_settings, save_user_settings
from escolio.app.local_env import (
    answer_api_key_is_configured,
    local_env_path_for,
    save_answer_api_key,
)
from escolio.app.settings_specs import (
    SETTING_SPECS,
    SettingSpec,
)
from escolio.ingest.audio_capture import list_input_devices
from escolio.providers import embed as embed_provider
from escolio.providers.answer import is_http_base_url
from escolio.providers.audio_catalog import load_catalog
from escolio.providers.voice_model_meta import ui_meta_for


def get_setting_spec(key: str) -> SettingSpec:
    for spec in SETTING_SPECS:
        if spec.key == key:
            return spec
    raise KeyError(f'Setting desconhecida: {key}')


def _numeric_bounds(key: str) -> tuple[float | None, float | None]:
    """Limites ge/le ja declarados no proprio Settings (config.py) - unica
    fonte de verdade, evita duplicar/desalinhar os ranges no catalogo."""
    field = Settings.model_fields.get(key)
    if field is None:
        return None, None
    minimum = next((m.ge for m in field.metadata if isinstance(m, Ge)), None)
    maximum = next((m.le for m in field.metadata if isinstance(m, Le)), None)
    return minimum, maximum


def _setting_value(settings: Settings, spec: SettingSpec) -> Any:
    if spec.key == 'answer_api_key':
        return ''
    value = getattr(settings, spec.key)
    if isinstance(value, Path):
        return str(value)
    return value


def _display_value(settings: Settings, spec: SettingSpec) -> str:
    if spec.key == 'answer_api_key':
        return 'configurada' if answer_api_key_is_configured(settings=settings) else 'ausente'
    value = _setting_value(settings, spec)
    return 'vazio' if value is None or value == '' else str(value)


def _input_device_names() -> list[str] | None:
    try:
        return list_input_devices()
    except Exception:
        return None


def _options_for(spec: SettingSpec, settings: Settings) -> list[dict[str, Any]]:
    if spec.key != 'audio_input_device':
        return [option.model_dump(exclude_none=True) for option in spec.options]
    options: list[dict[str, Any]] = [{'value': '', 'label': 'Padrão do sistema'}]
    names = _input_device_names()
    if names is None:
        return options
    options += [{'value': name, 'label': name} for name in names]
    saved = settings.audio_input_device
    if saved and saved not in names:
        options.append({'value': saved, 'label': f'{saved} (não encontrado)'})
    return options


def _warning_for(settings: Settings, spec: SettingSpec) -> str | None:
    if spec.key == 'audio_input_device' and settings.audio_input_device:
        names = _input_device_names()
        if names is not None and settings.audio_input_device not in names:
            return f'Microfone "{settings.audio_input_device}" não está conectado; a gravação vai falhar até reconectar ou escolher outro.'
    if spec.key == 'embedding_model' and settings.embedding_model == 'fake-hash':
        return 'fake-hash é modelo de teste; use chroma-default ou sentence-transformer real.'
    if spec.key == 'embedding_model':
        global_model = base_settings().embedding_model
        if global_model != settings.embedding_model:
            return f'O modelo de busca semântica global ({global_model}) é ignorado: a vault ativa usa {settings.embedding_model}.'
    if spec.key == 'embedding_device' and settings.embedding_model == 'chroma-default':
        return 'Device não se aplica ao chroma-default.'
    if spec.key == 'embedding_device' and settings.embedding_device == 'cuda' and settings.embedding_model.startswith('sentence-transformer:') and not embed_provider._cuda_available():
        return 'CUDA indisponível nesta máquina; use cpu/auto ou instale PyTorch com CUDA.'
    if spec.key == 'default_corpus_path' and settings.default_corpus_path is not None and not settings.default_corpus_path.is_dir():
        return f'Pasta não encontrada: {settings.default_corpus_path}'
    if spec.key == 'audio_language':
        model = load_catalog().get(settings.audio_model)
        if model is not None and '*' not in model.languages:
            language = settings.audio_language
            if language == 'auto':
                meta = ui_meta_for(settings.audio_model)
                if not (meta and meta.supports_auto_language):
                    return f'"{settings.audio_model}" não suporta detecção automática de idioma.'
            elif language not in model.languages:
                return f'"{settings.audio_model}" não suporta o idioma "{language}".'
    return None


def settings_catalog_payload(settings: Settings | None = None) -> list[dict[str, Any]]:
    resolved = settings or get_settings()
    rows: list[dict[str, Any]] = []
    for index, spec in enumerate(SETTING_SPECS, start=1):
        minimum, maximum = _numeric_bounds(spec.key) if spec.value_type in {'int', 'float'} else (None, None)
        rows.append(
            {
                'index': index,
                'key': spec.key,
                'label': spec.label,
                'description': spec.description,
                'group': spec.group,
                'value_type': spec.value_type,
                'layer': spec.layer,
                'storage': spec.storage,
                'value': _setting_value(resolved, spec),
                'display_value': _display_value(resolved, spec),
                'options': _options_for(spec, resolved),
                'recommended': spec.recommended,
                'secret': spec.secret,
                'placeholder': spec.placeholder,
                'warning': _warning_for(resolved, spec),
                'local_env_path': str(local_env_path_for(resolved)) if spec.storage == 'local_env' else None,
                'min': minimum,
                'max': maximum,
            }
        )
    return rows


def parse_catalog_value(spec: SettingSpec, value: Any) -> Any:
    if value is None or (isinstance(value, str) and value.strip() == ''):
        return None
    if spec.key == 'answer_base_url' and not is_http_base_url(str(value).strip()):
        raise ValueError('URL do provedor de resposta precisa começar com http:// ou https://')
    if spec.value_type in {'string', 'path', 'secret'}:
        return str(value).strip()
    if spec.value_type == 'int':
        return int(value)
    if spec.value_type == 'float':
        return float(value)
    if spec.value_type == 'bool':
        if isinstance(value, bool):
            return value
        lowered = str(value).strip().lower()
        if lowered in {'true', 'sim', 'yes', '1', 'on'}:
            return True
        if lowered in {'false', 'nao', 'não', 'no', '0', 'off'}:
            return False
        raise ValueError(f'Valor booleano inválido para {spec.key}: {value}')
    if spec.value_type == 'enum':
        cleaned = str(value).strip()
        allowed = {option.value for option in spec.options}
        if cleaned not in allowed:
            raise ValueError(f'Valor inválido para {spec.key}: {cleaned}. Opções: {", ".join(sorted(allowed))}')
        return cleaned
    return value


def save_catalog_setting(key: str, value: Any, *, settings: Settings | None = None) -> None:
    spec = get_setting_spec(key)
    parsed = parse_catalog_value(spec, value)
    if spec.storage == 'local_env':
        if spec.key != 'answer_api_key':
            raise ValueError(f'Setting local_env sem handler: {spec.key}')
        save_answer_api_key('' if parsed is None else str(parsed), settings=settings)
        return
    save_user_settings({spec.key: parsed}, settings=settings)


def save_catalog_settings(values: dict[str, Any], *, settings: Settings | None = None) -> Settings:
    """Salva varias settings do catalogo numa unica leitura+escrita de
    user_settings.json, em vez de uma chamada de save_user_settings por
    chave. Isso existe porque N chamadas paralelas de save_catalog_setting
    (uma por linha editavel do modal) fazem N ciclos concorrentes de
    ler->mesclar->escrever no MESMO arquivo, sem lock e com escrita nao
    atomica (Path.write_text trunca antes de escrever) - a race condition
    classica de duas escritas se sobrepondo produz um arquivo vazio/
    truncado. Uma unica chamada com todas as chaves elimina a concorrencia
    na raiz, e valida o estado final combinado de uma vez so (util para
    pares cruzados como default_chunk_size/default_chunk_overlap).
    """
    to_persist: dict[str, Any] = {}
    for key, value in values.items():
        spec = get_setting_spec(key)
        try:
            parsed = parse_catalog_value(spec, value)
        except ValueError as exc:
            raise ValueError(f'{key}: {exc}') from exc
        if spec.storage == 'local_env':
            if spec.key != 'answer_api_key':
                raise ValueError(f'Setting local_env sem handler: {spec.key}')
            save_answer_api_key('' if parsed is None else str(parsed), settings=settings)
            continue
        to_persist[spec.key] = parsed
    if not to_persist:
        return settings or get_settings()
    try:
        return save_user_settings(to_persist, settings=settings)
    except ValidationError as exc:
        first = exc.errors()[0]
        field = '.'.join(str(loc) for loc in first['loc']) or 'configuração'
        raise ValueError(f'{field}: {first["msg"]}') from exc
