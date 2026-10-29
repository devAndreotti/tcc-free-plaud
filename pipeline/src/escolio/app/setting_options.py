"""Opções dos selects de Configurações, com a explicação que aparece para o usuário."""

from pydantic import BaseModel


class SettingOption(BaseModel):
    value: str
    label: str
    # Explica a opção para quem não conhece o termo (aparece no dropdown e abaixo dele).
    description: str | None = None


# Embedding e transcrição usam as mesmas três.
DEVICE_OPTIONS = [
    SettingOption(value='auto', label='Auto', description='Usa a placa de vídeo NVIDIA (CUDA) se houver; senão, o processador. A escolha segura.'),
    SettingOption(value='cpu', label='CPU', description='Roda no processador. Funciona em qualquer PC; mais lento com modelos grandes.'),
    SettingOption(value='cuda', label='CUDA', description='Roda na placa de vídeo NVIDIA: bem mais rápido, mas exige GPU NVIDIA com CUDA; sem ela, dá erro.'),
]

STRATEGY_OPTIONS = [
    SettingOption(value='lexical', label='Lexical', description='Só palavras exatas (FTS5). A mais rápida.'),
    SettingOption(value='vector', label='Vetorial', description='Por significado, mesmo sem as palavras exatas.'),
    SettingOption(value='hybrid', label='Híbrida', description='Palavra-chave e significado combinados.'),
]

COMMIT_MODE_OPTIONS = [
    SettingOption(value='auto', label='Auto', description='Grava tudo de uma vez em pastas pequenas e em lotes nas grandes (acima de 32 arquivos ou 64 chunks).'),
    SettingOption(value='atomic', label='Atomic', description='Grava tudo de uma vez no fim: ou a pasta inteira entra no índice, ou nada.'),
    SettingOption(value='microbatch', label='Microbatch', description='Grava em lotes durante a indexação: o progresso não se perde se parar no meio.'),
]

ANSWER_PROVIDER_OPTIONS = [
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
]
