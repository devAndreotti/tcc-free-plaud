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
        label='Modelo de busca por significado',
        description='Modelo que transforma o texto em números (vetores) para achar trechos pelo significado, não só pelas palavras exatas.',
        group='Embeddings',
        value_type='string',
        recommended='sentence-transformer:sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2',
        placeholder='chroma-default ou sentence-transformer:...',
    ),
    SettingSpec(
        key='embedding_device',
        label='Onde roda a busca por significado',
        description='Processador (CPU) ou placa de vídeo (GPU) para a busca por significado. O modelo padrão sempre usa o processador.',
        group='Embeddings',
        value_type='enum',
        layer='simple',
        options=DEVICE_OPTIONS,
        recommended='auto',
    ),
    SettingSpec(
        key='default_ask_strategy',
        label='Como buscar nas notas',
        description='Forma padrão de achar trechos das notas para responder: por palavra exata, por significado ou pelas duas juntas.',
        group='Retrieval',
        value_type='enum',
        layer='simple',
        options=STRATEGY_OPTIONS,
        recommended='hybrid',
    ),
    SettingSpec(
        key='retrieval_top_k',
        label='Trechos por pergunta',
        description='Quantos trechos das notas servem de base para cada resposta.',
        group='Retrieval',
        value_type='int',
        recommended=4,
    ),
    SettingSpec(
        key='default_chunk_size',
        label='Tamanho do trecho (caracteres)',
        description='Tamanho alvo de cada pedaço em que as notas são divididas para indexar, contado em caracteres.',
        group='Chunks',
        value_type='int',
        recommended=800,
    ),
    SettingSpec(
        key='default_chunk_overlap',
        label='Repetição entre trechos (caracteres)',
        description='Quantos caracteres do fim de um trecho se repetem no começo do seguinte, para a frase não ficar cortada sem contexto.',
        group='Chunks',
        value_type='int',
        recommended=120,
    ),
    SettingSpec(
        key='corpus_commit_mode',
        label='Como salvar o índice',
        description='Quando as notas indexadas são gravadas. Automático (padrão) grava pastas pequenas de uma vez e pastas grandes em partes.',
        group='Corpus',
        value_type='enum',
        options=COMMIT_MODE_OPTIONS,
        recommended='auto',
    ),
    SettingSpec(
        key='default_corpus_path',
        label='Pasta padrão das notas',
        description='Pasta de notas que o app usa por padrão ao indexar ou reconstruir o índice.',
        group='Corpus',
        value_type='path',
        layer='simple',
        placeholder=r'D:\caminho\vault',
    ),
    SettingSpec(
        key='corpus_recursive_default',
        label='Indexar subpastas',
        description='Inclui também as notas que estão dentro de subpastas ao indexar.',
        group='Corpus',
        value_type='bool',
        layer='simple',
        recommended=True,
    ),
    SettingSpec(
        key='corpus_embedding_batch_size',
        label='Trechos enviados por vez',
        description='Quantos trechos são enviados de uma vez ao modelo de busca por significado durante a indexação.',
        group='Corpus',
        value_type='int',
        recommended=64,
    ),
    SettingSpec(
        key='corpus_index_workers',
        label='Arquivos preparados ao mesmo tempo',
        description='Quantas notas são lidas e preparadas em paralelo antes da busca por significado. 1 faz uma de cada vez.',
        group='Corpus',
        value_type='int',
        recommended=1,
    ),
    SettingSpec(
        key='answer_provider',
        label='Quem escreve a resposta',
        description='Quem escreve a resposta final com base nos trechos encontrados.',
        group='LLM',
        value_type='enum',
        layer='simple',
        options=ANSWER_PROVIDER_OPTIONS,
        recommended='extractive',
    ),
    SettingSpec(
        key='answer_model',
        label='Modelo de resposta',
        description='Modelo de IA que escreve a resposta. Os menores, de cerca de 3 bilhões de parâmetros (como qwen2.5:3b), cabem em placa de vídeo de 4 GB e respondem em segundos; os de 7 bilhões ou mais ficam lentos.',
        group='LLM',
        value_type='string',
        layer='simple',
        recommended='qwen2.5:3b',
    ),
    SettingSpec(
        key='answer_base_url',
        label='Endereço da IA',
        description='Endereço do servidor que roda a IA. Deixe vazio para usar o endereço padrão do provedor escolhido.',
        group='LLM',
        value_type='string',
        placeholder='http://localhost:11434/v1',
    ),
    SettingSpec(
        key='answer_temperature',
        label='Variação da redação',
        description='Quanto a IA pode se afastar do texto das notas ao responder. Valor baixo (padrão 0,2) deixa a resposta mais fiel às notas.',
        group='LLM',
        value_type='float',
        recommended=0.2,
    ),
    SettingSpec(
        key='answer_timeout_seconds',
        label='Tempo máximo de espera (segundos)',
        description='Quantos segundos esperar a IA responder antes de desistir.',
        group='LLM',
        value_type='int',
        recommended=60,
    ),
    SettingSpec(
        key='answer_api_key',
        label='Chave da IA (API key)',
        description='Chave secreta de um serviço de IA na internet. Fica salva só neste computador, no arquivo pipeline/.env.',
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
        description='Modelo que roda no seu PC para transcrever a pergunta gravada por voz no chat.',
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
        description='Idioma em que a voz será transcrita. "Automático" só funciona com alguns modelos; se der erro, escolha o idioma.',
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
        label='Onde transcrever a voz',
        description='Processador (CPU) ou placa de vídeo (GPU) para transcrever a voz. Automático escolhe sozinho.',
        group=AUDIO_GROUP,
        value_type='enum',
        layer='simple',
        options=DEVICE_OPTIONS,
        recommended='auto',
    ),
    SettingSpec(
        key='answer_max_tokens',
        label='Tamanho máximo da resposta (tokens)',
        description='Limite de tamanho da resposta, em tokens (um token é um pedaço de palavra). Vazio usa o padrão do modelo. Aumente se a resposta vier cortada.',
        group='LLM',
        value_type='int',
        placeholder='vazio = default do modelo',
    ),
    SettingSpec(
        key='extract_structure',
        label='Extrair decisões e tarefas com IA',
        description='Usa a IA de resposta para achar decisões, tarefas com responsável e prazo e temas nas notas. Desligado usa regras fixas, sem IA.',
        group='LLM',
        value_type='bool',
        recommended=False,
    ),
)


def iter_setting_specs() -> tuple[SettingSpec, ...]:
    return SETTING_SPECS


