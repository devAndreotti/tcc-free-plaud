from typing import Literal, Protocol

from chromadb.utils import embedding_functions
from pydantic import BaseModel

EmbeddingDevice = Literal['cpu', 'cuda', 'auto']
EMBEDDING_TEST_MODEL_HELP = (
    "fake-hash e modelo de teste e nao deve ser usado no app real. "
    "Use chroma-default ou sentence-transformer:<modelo>. "
    "Para voltar ao preset CPU rapido, rode: uv run free-plaud config preset apply cpu_rapido"
)


class EmbeddingConfigurationError(ValueError):
    """Erro de configuracao de embedding seguro para mostrar em CLI/TUI."""


def validate_runtime_embedding_model(model_name: str) -> None:
    """Falha cedo para modelos que nao podem operar retrieval vetorial real."""
    if model_name == 'fake-hash':
        raise EmbeddingConfigurationError(EMBEDDING_TEST_MODEL_HELP)
    if model_name == 'chroma-default':
        return
    if model_name.startswith('sentence-transformer:') and model_name.split(':', 1)[1].strip():
        return
    if model_name.startswith('sentence-transformer:'):
        raise EmbeddingConfigurationError('Embedding model sentence-transformer precisa informar o nome do modelo.')
    raise EmbeddingConfigurationError(f'Embedding model nao suportado: {model_name}')


class EmbeddingDiagnostics(BaseModel):
    model_name: str
    requested_device: EmbeddingDevice
    resolved_device: str | None
    device_applicable: bool
    message: str


class Embedder(Protocol):
    model_name: str

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Produz embeddings para um conjunto de textos."""


class ChromaDefaultEmbedder:
    """Wrapper fino para o embedding default local do ChromaDB."""

    def __init__(self) -> None:
        from chromadb.utils.embedding_functions.onnx_mini_lm_l6_v2 import (
            ONNXMiniLM_L6_V2,
        )

        self.model_name = 'chroma-default'
        # Mesmo modelo do DefaultEmbeddingFunction, mas reaproveitado: o Default do Chroma cria
        # um ONNXMiniLM_L6_V2 novo a cada chamada e recarrega a sessão ONNX (~1,5 s) toda vez.
        self._embedding_function = ONNXMiniLM_L6_V2()
        self._query_function = None

    def _single_text_function(self):
        """Instância para um texto só (a pergunta), sem completar a entrada até 256 tokens.

        Divide a sessão ONNX com a instância principal. A média do modelo usa a máscara de
        atenção, então o vetor é idêntico e a inferência fica ~5x mais rápida. Só vale para um
        texto por chamada: o Chroma tokeniza cada texto separado e o lote precisa de tamanho fixo.
        """
        if self._query_function is None:
            from chromadb.utils.embedding_functions.onnx_mini_lm_l6_v2 import (
                ONNXMiniLM_L6_V2,
            )

            query_function = ONNXMiniLM_L6_V2()
            query_function.__dict__['model'] = self._embedding_function.model
            query_function.tokenizer.enable_padding(pad_id=0, pad_token='[PAD]')
            self._query_function = query_function
        return self._query_function

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        function = self._single_text_function() if len(texts) == 1 else self._embedding_function
        embeddings = function(texts)
        return [list(map(float, embedding)) for embedding in embeddings]


class SentenceTransformerEmbedder:
    """Wrapper local para modelos Sentence Transformers via Chroma."""

    def __init__(self, model_name: str, *, device: str = 'cpu', normalize_embeddings: bool = False) -> None:
        self.model_name = model_name
        self.device = device
        try:
            self._embedding_function = embedding_functions.SentenceTransformerEmbeddingFunction(
                model_name=model_name,
                device=device,
                normalize_embeddings=normalize_embeddings,
            )
        except Exception as exc:
            raise RuntimeError(
                "Falha ao inicializar embedding sentence-transformer "
                f"'{model_name}' no device '{device}'. "
                "Verifique a instalacao de sentence-transformers, torch e numpy. "
                "Se acabou de trocar para CUDA, feche TUI/processos Python e reinstale numpy/torch. "
                f"Causa original: {type(exc).__name__}: {exc}"
            ) from exc

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        try:
            embeddings = self._embedding_function(texts)
            return [list(map(float, embedding)) for embedding in embeddings]
        except Exception as exc:
            raise RuntimeError(
                "Falha ao gerar embeddings sentence-transformer "
                f"'{self.model_name}' no device '{self.device}'. "
                f"Causa original: {type(exc).__name__}: {exc}"
            ) from exc


def _cuda_available() -> bool:
    try:
        import torch
    except Exception:
        return False
    return bool(torch.cuda.is_available())


def _resolve_sentence_transformer_device(device: EmbeddingDevice) -> str:
    if device == 'cpu':
        return 'cpu'
    if device == 'cuda':
        if not _cuda_available():
            raise ValueError('CUDA indisponivel para embeddings sentence-transformer.')
        return 'cuda'
    return 'cuda' if _cuda_available() else 'cpu'


def describe_embedding_config(model_name: str, *, device: EmbeddingDevice = 'cpu') -> EmbeddingDiagnostics:
    """Descreve modelo e device sem inicializar embedding pesado."""
    if model_name == 'chroma-default':
        return EmbeddingDiagnostics(
            model_name=model_name,
            requested_device=device,
            resolved_device=None,
            device_applicable=False,
            message='Device CUDA nao se aplica ao chroma-default.',
        )
    if model_name.startswith('sentence-transformer:'):
        resolved_model_name = model_name.split(':', 1)[1].strip()
        if not resolved_model_name:
            raise ValueError('Embedding model sentence-transformer precisa informar o nome do modelo.')
        resolved_device = _resolve_sentence_transformer_device(device)
        return EmbeddingDiagnostics(
            model_name=resolved_model_name,
            requested_device=device,
            resolved_device=resolved_device,
            device_applicable=True,
            message=f'Embedding sentence-transformer configurado para {resolved_device}.',
        )
    raise ValueError(f'Embedding model nao suportado: {model_name}')


def get_embedder(model_name: str, *, device: EmbeddingDevice = 'cpu') -> Embedder:
    """Resolve o adaptador de embeddings configurado para o backend."""
    validate_runtime_embedding_model(model_name)
    if model_name == 'chroma-default':
        return ChromaDefaultEmbedder()
    if model_name.startswith('sentence-transformer:'):
        resolved_model_name = model_name.split(':', 1)[1].strip()
        return SentenceTransformerEmbedder(resolved_model_name, device=_resolve_sentence_transformer_device(device))
    raise EmbeddingConfigurationError(f'Embedding model nao suportado: {model_name}')
