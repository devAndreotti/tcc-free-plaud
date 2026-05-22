from typing import Literal, Protocol

from chromadb.utils import embedding_functions
from pydantic import BaseModel

EmbeddingDevice = Literal['cpu', 'cuda', 'auto']


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
        self.model_name = 'chroma-default'
        self._embedding_function = embedding_functions.DefaultEmbeddingFunction()

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        embeddings = self._embedding_function(texts)
        return [list(map(float, embedding)) for embedding in embeddings]


class SentenceTransformerEmbedder:
    """Wrapper local para modelos Sentence Transformers via Chroma."""

    def __init__(self, model_name: str, *, device: str = 'cpu', normalize_embeddings: bool = False) -> None:
        self.model_name = model_name
        self._embedding_function = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name=model_name,
            device=device,
            normalize_embeddings=normalize_embeddings,
        )

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        embeddings = self._embedding_function(texts)
        return [list(map(float, embedding)) for embedding in embeddings]


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
    if model_name == 'chroma-default':
        return ChromaDefaultEmbedder()
    if model_name.startswith('sentence-transformer:'):
        resolved_model_name = model_name.split(':', 1)[1].strip()
        if not resolved_model_name:
            raise ValueError('Embedding model sentence-transformer precisa informar o nome do modelo.')
        return SentenceTransformerEmbedder(resolved_model_name, device=_resolve_sentence_transformer_device(device))
    raise ValueError(f'Embedding model nao suportado: {model_name}')
