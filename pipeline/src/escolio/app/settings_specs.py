from typing import Literal

from pydantic import BaseModel, Field

from escolio.app.setting_options import (
    ANSWER_PROVIDER_OPTIONS,
    COMMIT_MODE_OPTIONS,
    DEVICE_OPTIONS,
    STRATEGY_OPTIONS,
    SettingOption,
)
from escolio.providers.audio_catalog import load_catalog

SettingValueType = Literal['string', 'int', 'float', 'bool', 'path', 'enum', 'secret']
SettingStorage = Literal['user_settings', 'local_env']
SettingLayer = Literal['simple', 'advanced']


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


_LANGUAGE_LABELS = {
    'pt': 'Português',
    'en': 'Inglês',
    'es': 'Espanhol',
    'fr': 'Francês',
    'de': 'Alemão',
    'it': 'Italiano',
    'ja': 'Japonês',
    'ko': 'Coreano',
    'zh': 'Chinês',
    'ru': 'Russo',
    'yue': 'Cantonês',
}


def _audio_language_options() -> list[SettingOption]:
    """Opcoes de idioma derivadas do catalogo real de modelos de voz (fonte
    unica de verdade - evita lista hardcoded divergindo do que os modelos
    realmente suportam). "auto" so funciona de verdade com faster-whisper;
    ver providers/audio_runtime.py."""
    codes = sorted({lang for model in load_catalog().values() for lang in model.languages if lang != '*'})
    options = [SettingOption(value='auto', label='Automático (detectar idioma)')]
    options += [SettingOption(value=code, label=_LANGUAGE_LABELS.get(code, code.upper())) for code in codes]
    return options


AUDIO_GROUP = 'Áudio'

SETTING_SPECS: tuple[SettingSpec, ...] = (
    SettingSpec(
        key='embedding_model',
        label='Modelo de busca semântica',
        description='Modelo que transforma texto em vetores para busca semântica.',
        group='Embeddings',
        value_type='string',
        recommended='sentence-transformer:sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2',
        placeholder='chroma-default ou sentence-transformer:...',
    ),
    SettingSpec(
        key='embedding_device',
        label='Dispositivo de busca semântica',
        description='Onde roda o modelo de busca semântica quando ele suporta device (o chroma-default sempre usa o processador).',
        group='Embeddings',
        value_type='enum',
        layer='simple',
        options=DEVICE_OPTIONS,
        recommended='auto',
    ),
    SettingSpec(
        key='default_ask_strategy',
        label='Estratégia padrão',
        description='Busca usada por padrão ao perguntar ao corpus.',
        group='Retrieval',
        value_type='enum',
        layer='simple',
        options=STRATEGY_OPTIONS,
        recommended='hybrid',
    ),
    SettingSpec(
        key='retrieval_top_k',
        label='Trechos por pergunta',
        description='Quantos trechos a pergunta recupera para montar evidências e resposta.',
        group='Retrieval',
        value_type='int',
        recommended=4,
    ),
    SettingSpec(
        key='default_chunk_size',
        label='Tamanho do trecho',
        description='Tamanho alvo de cada pedaço indexado do texto.',
        group='Chunks',
        value_type='int',
        recommended=800,
    ),
    SettingSpec(
        key='default_chunk_overlap',
        label='Sobreposição',
        description='Quanto texto um trecho repete do anterior para evitar corte de contexto.',
        group='Chunks',
        value_type='int',
        recommended=120,
    ),
    SettingSpec(
        key='corpus_commit_mode',
        label='Modo de commit',
        description='Quando a indexação grava SQLite e Chroma.',
        group='Corpus',
        value_type='enum',
        options=COMMIT_MODE_OPTIONS,
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
        label='Lote de indexação',
        description='Quantidade de trechos processados por lote no modelo de busca semântica.',
        group='Corpus',
        value_type='int',
        recommended=64,
    ),
    SettingSpec(
        key='corpus_index_workers',
        label='Workers de indexação',
        description='Paralelismo para carregar e preparar arquivos antes do modelo de busca semântica.',
        group='Corpus',
        value_type='int',
        recommended=1,
    ),
    SettingSpec(
        key='answer_provider',
        label='Provedor de resposta',
        description='Quem transforma evidências recuperadas em resposta final.',
        group='LLM',
        value_type='enum',
        layer='simple',
        options=ANSWER_PROVIDER_OPTIONS,
        recommended='extractive',
    ),
    SettingSpec(
        key='answer_model',
        label='Modelo de resposta',
        description='Modelo que escreve a resposta. Os de ~3B (como qwen2.5:3b) cabem numa GPU de 4 GB e respondem em segundos; 7B ou mais ficam lentos.',
        group='LLM',
        value_type='string',
        layer='simple',
        recommended='qwen2.5:3b',
    ),
    SettingSpec(
        key='answer_base_url',
        label='URL do provider',
        description='Endereço do servidor da IA; vazio usa o padrão do provedor escolhido.',
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
        description='Tempo máximo para aguardar o provider de resposta.',
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
        placeholder='ESCOLIO_ANSWER_API_KEY',
    ),
    SettingSpec(
        key='audio_model',
        label='Modelo de transcrição (voz)',
        description='Modelo local usado para transcrever o áudio gravado no chat.',
        group=AUDIO_GROUP,
        value_type='enum',
        layer='simple',
        options=[
            SettingOption(value='whisper-small', label='Whisper Small (multilíngue)'),
            SettingOption(value='moonshine-tiny-en', label='Moonshine Tiny (inglês)'),
            SettingOption(value='sensevoice-small', label='SenseVoice Small'),
            SettingOption(value='sensevoice-gguf-q8', label='SenseVoice GGUF Q8'),
        ],
        recommended='whisper-small',
    ),
    SettingSpec(
        key='audio_language',
        label='Idioma da transcrição',
        description='Idioma usado pelo modelo de voz. "Automático" só funciona com modelos faster-whisper.',
        group=AUDIO_GROUP,
        value_type='enum',
        layer='simple',
        options=_audio_language_options(),
        recommended='pt',
    ),
    SettingSpec(
        key='audio_input_device',
        label='Microfone',
        description='Dispositivo usado para gravar a pergunta por voz. "Padrão do sistema" segue o microfone padrão do Windows.',
        group=AUDIO_GROUP,
        value_type='string',
        layer='simple',
    ),
    SettingSpec(
        key='audio_device',
        label='Device de transcrição',
        description='Onde roda o modelo de voz quando ele suporta device.',
        group=AUDIO_GROUP,
        value_type='enum',
        layer='simple',
        options=DEVICE_OPTIONS,
        recommended='auto',
    ),
    SettingSpec(
        key='answer_max_tokens',
        label='Max tokens da resposta',
        description='Limite de tokens de saída do provider; vazio usa o default do modelo. Suba para modelos de reasoning que truncam.',
        group='LLM',
        value_type='int',
        placeholder='vazio = default do modelo',
    ),
)


def iter_setting_specs() -> tuple[SettingSpec, ...]:
    return SETTING_SPECS


