from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field

from free_plaud.app.config import Settings, get_settings, save_user_settings
from free_plaud.app.local_env import answer_api_key_is_configured, local_env_path_for, save_answer_api_key

SettingValueType = Literal['string', 'int', 'float', 'bool', 'path', 'enum', 'secret']
SettingStorage = Literal['user_settings', 'local_env']
SettingLayer = Literal['simple', 'advanced']


class SettingOption(BaseModel):
    value: str
    label: str


class SettingSpec(BaseModel):
    key: str
    label: str
    description: str
    group: str
    value_type: SettingValueType
    layer: SettingLayer = 'advanced'
    storage: SettingStorage = 'user_settings'
    options: list[SettingOption] = Field(default_factory=list)
    recommended: str | int | float | bool | None = None
    secret: bool = False
    placeholder: str | None = None


SETTING_SPECS: tuple[SettingSpec, ...] = (
    SettingSpec(
        key='embedding_model',
        label='Modelo de embedding',
        description='Modelo que transforma texto em vetores para busca semantica.',
        group='Embeddings',
        value_type='string',
        recommended='sentence-transformer:sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2',
        placeholder='chroma-default ou sentence-transformer:...',
    ),
    SettingSpec(
        key='embedding_device',
        label='Device de embedding',
        description='Onde roda o modelo de embedding quando ele suporta device.',
        group='Embeddings',
        value_type='enum',
        layer='simple',
        options=[SettingOption(value='auto', label='Auto'), SettingOption(value='cpu', label='CPU'), SettingOption(value='cuda', label='CUDA')],
        recommended='auto',
    ),
    SettingSpec(
        key='default_ask_strategy',
        label='Estratégia padrão',
        description='Busca usada por padrao ao perguntar ao corpus.',
        group='Retrieval',
        value_type='enum',
        layer='simple',
        options=[SettingOption(value='lexical', label='Lexical'), SettingOption(value='vector', label='Vector'), SettingOption(value='hybrid', label='Hybrid')],
        recommended='hybrid',
    ),
    SettingSpec(
        key='retrieval_top_k',
        label='Chunks por pergunta',
        description='Quantos chunks o Ask recupera para montar evidencias e resposta.',
        group='Retrieval',
        value_type='int',
        recommended=4,
    ),
    SettingSpec(
        key='default_chunk_size',
        label='Tamanho do chunk',
        description='Tamanho alvo de cada pedaço indexado do texto.',
        group='Chunks',
        value_type='int',
        recommended=800,
    ),
    SettingSpec(
        key='default_chunk_overlap',
        label='Sobreposição',
        description='Quanto texto um chunk repete do anterior para evitar corte de contexto.',
        group='Chunks',
        value_type='int',
        recommended=120,
    ),
    SettingSpec(
        key='corpus_commit_mode',
        label='Modo de commit',
        description='Quando a indexacao grava SQLite e Chroma.',
        group='Corpus',
        value_type='enum',
        options=[SettingOption(value='auto', label='Auto'), SettingOption(value='atomic', label='Atomic'), SettingOption(value='microbatch', label='Microbatch')],
        recommended='auto',
    ),
    SettingSpec(
        key='default_corpus_path',
        label='Pasta padrão do corpus',
        description='Pasta usada como default para indexar e reconstruir corpus.',
        group='Corpus',
        value_type='path',
        layer='simple',
        placeholder=r'D:\caminho\vault',
    ),
    SettingSpec(
        key='corpus_recursive_default',
        label='Indexar subpastas',
        description='Inclui arquivos dentro de subpastas ao indexar corpus.',
        group='Corpus',
        value_type='bool',
        layer='simple',
        recommended=True,
    ),
    SettingSpec(
        key='corpus_embedding_batch_size',
        label='Batch de embeddings',
        description='Quantidade de chunks processados por lote no embedding.',
        group='Corpus',
        value_type='int',
        recommended=64,
    ),
    SettingSpec(
        key='corpus_index_workers',
        label='Workers de indexação',
        description='Paralelismo para carregar e preparar arquivos antes do embedding.',
        group='Corpus',
        value_type='int',
        recommended=1,
    ),
    SettingSpec(
        key='answer_provider',
        label='Provedor de resposta',
        description='Quem transforma evidencias recuperadas em resposta final.',
        group='LLM',
        value_type='enum',
        layer='simple',
        options=[SettingOption(value='extractive', label='Extractive'), SettingOption(value='ollama', label='Ollama'), SettingOption(value='lmstudio', label='LM Studio'), SettingOption(value='openai-compatible', label='OpenAI-compatible')],
        recommended='extractive',
    ),
    SettingSpec(
        key='answer_model',
        label='Modelo de resposta',
        description='Modelo LLM usado pelo provider generativo.',
        group='LLM',
        value_type='string',
        layer='simple',
        recommended='llama3.1:8b',
    ),
    SettingSpec(
        key='answer_base_url',
        label='URL do provider',
        description='Endpoint OpenAI-compatible; vazio usa default do provider.',
        group='LLM',
        value_type='string',
        placeholder='http://localhost:11434/v1',
    ),
    SettingSpec(
        key='answer_temperature',
        label='Temperatura',
        description='Criatividade do LLM; RAG deve usar valor baixo.',
        group='LLM',
        value_type='float',
        recommended=0.2,
    ),
    SettingSpec(
        key='answer_timeout_seconds',
        label='Timeout da resposta',
        description='Tempo maximo para aguardar o provider de resposta.',
        group='LLM',
        value_type='int',
        recommended=60,
    ),
    SettingSpec(
        key='answer_api_key',
        label='API key',
        description='Segredo local para provider remoto; salvo apenas em pipeline/.env.',
        group='LLM',
        value_type='secret',
        layer='simple',
        storage='local_env',
        secret=True,
        placeholder='FREE_PLAUD_ANSWER_API_KEY',
    ),
    SettingSpec(
        key='answer_max_tokens',
        label='Max tokens da resposta',
        description='Limite de tokens de saida do provider; vazio usa o default do modelo. Suba para modelos de reasoning que truncam.',
        group='LLM',
        value_type='int',
        placeholder='vazio = default do modelo',
    ),
)


def iter_setting_specs() -> tuple[SettingSpec, ...]:
    return SETTING_SPECS


def get_setting_spec(key: str) -> SettingSpec:
    for spec in SETTING_SPECS:
        if spec.key == key:
            return spec
    raise KeyError(f'Setting desconhecida: {key}')


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


def _warning_for(settings: Settings, spec: SettingSpec) -> str | None:
    if spec.key == 'embedding_model' and settings.embedding_model == 'fake-hash':
        return 'fake-hash é modelo de teste; use chroma-default ou sentence-transformer real.'
    if spec.key == 'embedding_device' and settings.embedding_model == 'chroma-default':
        return 'Device nao se aplica ao chroma-default.'
    return None


def settings_catalog_payload(settings: Settings | None = None) -> list[dict[str, Any]]:
    resolved = settings or get_settings()
    rows: list[dict[str, Any]] = []
    for index, spec in enumerate(SETTING_SPECS, start=1):
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
                'options': [option.model_dump() for option in spec.options],
                'recommended': spec.recommended,
                'secret': spec.secret,
                'placeholder': spec.placeholder,
                'warning': _warning_for(resolved, spec),
                'local_env_path': str(local_env_path_for(resolved)) if spec.storage == 'local_env' else None,
            }
        )
    return rows


def parse_catalog_value(spec: SettingSpec, value: Any) -> Any:
    if value is None or value == '':
        return None
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
        raise ValueError(f'Valor booleano invalido para {spec.key}: {value}')
    if spec.value_type == 'enum':
        cleaned = str(value).strip()
        allowed = {option.value for option in spec.options}
        if cleaned not in allowed:
            raise ValueError(f'Valor invalido para {spec.key}: {cleaned}. Opcoes: {", ".join(sorted(allowed))}')
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
