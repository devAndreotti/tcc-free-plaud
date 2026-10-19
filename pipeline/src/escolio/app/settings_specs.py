from typing import Literal

from pydantic import BaseModel, Field

from escolio.providers.audio_catalog import load_catalog

SettingValueType = Literal['string', 'int', 'float', 'bool', 'path', 'enum', 'secret']
SettingStorage = Literal['user_settings', 'local_env']
SettingLayer = Literal['simple', 'advanced']


class SettingOption(BaseModel):
    value: str
    label: str
    # Explica a opção para quem não conhece o termo (aparece no dropdown e abaixo dele).
    description: str | None = None


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
        label='Modelo de embedding',
        description='Modelo que transforma texto em vetores para busca semântica.',
        group='Embeddings',
        value_type='string',
        recommended='sentence-transformer:sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2',
        placeholder='chroma-default ou sentence-transformer:...',
    ),
    SettingSpec(
        key='embedding_device',
        label='Device de embedding',
        description='Onde roda o modelo de embedding quando ele suporta device (o chroma-default sempre usa o processador).',
        group='Embeddings',
        value_type='enum',
        layer='simple',
        options=[
            SettingOption(value='auto', label='Auto', description='Usa a placa de vídeo NVIDIA (CUDA) se houver; senão, o processador. A escolha segura.'),
            SettingOption(value='cpu', label='CPU', description='Roda no processador. Funciona em qualquer PC; mais lento com modelos grandes.'),
            SettingOption(value='cuda', label='CUDA', description='Roda na placa de vídeo NVIDIA: bem mais rápido, mas exige GPU NVIDIA com CUDA; sem ela, dá erro.'),
        ],
        recommended='auto',
    ),
    SettingSpec(
        key='default_ask_strategy',
        label='Estratégia padrão',
        description='Busca usada por padrão ao perguntar ao corpus.',
        group='Retrieval',
        value_type='enum',
        layer='simple',
        options=[
            SettingOption(value='lexical', label='Lexical', description='Só palavras exatas (FTS5). A mais rápida.'),
            SettingOption(value='vector', label='Vetorial', description='Por significado, mesmo sem as palavras exatas.'),
            SettingOption(value='hybrid', label='Híbrida', description='Palavra-chave e significado combinados.'),
        ],
        recommended='hybrid',
    ),
    SettingSpec(
        key='retrieval_top_k',
        label='Chunks por pergunta',
        description='Quantos chunks o Ask recupera para montar evidências e resposta.',
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
        description='Quando a indexação grava SQLite e Chroma.',
        group='Corpus',
        value_type='enum',
        options=[
            SettingOption(value='auto', label='Auto', description='Grava tudo de uma vez em pastas pequenas e em lotes nas grandes (acima de 32 arquivos ou 64 chunks).'),
            SettingOption(value='atomic', label='Atomic', description='Grava tudo de uma vez no fim: ou a pasta inteira entra no índice, ou nada.'),
            SettingOption(value='microbatch', label='Microbatch', description='Grava em lotes durante a indexação: o progresso não se perde se parar no meio.'),
        ],
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
        description='Quem transforma evidências recuperadas em resposta final.',
        group='LLM',
        value_type='enum',
        layer='simple',
        options=[
            SettingOption(
                value='extractive',
                label='Extractive',
                description='Sem IA generativa: monta a resposta com trechos das suas notas, cada um com a fonte. Rápido, offline e sem custo.',
            ),
            SettingOption(
                value='ollama',
                label='Ollama',
                description='IA local pelo Ollama (localhost:11434): escreve a resposta a partir dos trechos sem enviar nada para fora. Precisa do Ollama aberto e de um modelo baixado.',
            ),
            SettingOption(
                value='lmstudio',
                label='LM Studio',
                description='IA local pelo servidor do LM Studio (localhost:1234). Mesmo papel do Ollama: privado, mas exige o servidor ligado com um modelo carregado.',
            ),
            SettingOption(
                value='openai-compatible',
                label='OpenAI-compatible',
                description='Qualquer API no padrão OpenAI (OpenAI, OpenRouter, Groq…). Usa a API key e envia os trechos recuperados para o serviço.',
            ),
        ],
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
        options=[
            SettingOption(value='auto', label='Auto', description='Usa a placa de vídeo NVIDIA (CUDA) se houver; senão, o processador. A escolha segura.'),
            SettingOption(value='cpu', label='CPU', description='Roda no processador. Funciona em qualquer PC; mais lento com modelos grandes.'),
            SettingOption(value='cuda', label='CUDA', description='Roda na placa de vídeo NVIDIA: bem mais rápido, mas exige GPU NVIDIA com CUDA; sem ela, dá erro.'),
        ],
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


