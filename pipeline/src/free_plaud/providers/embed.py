from typing import Protocol

from chromadb.utils import embedding_functions


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


def get_embedder(model_name: str) -> Embedder:
    """Resolve o adaptador de embeddings configurado para o backend."""
    if model_name == 'chroma-default':
        return ChromaDefaultEmbedder()
    if model_name.startswith('sentence-transformer:'):
        resolved_model_name = model_name.split(':', 1)[1].strip()
        if not resolved_model_name:
            raise ValueError('Embedding model sentence-transformer precisa informar o nome do modelo.')
        return SentenceTransformerEmbedder(resolved_model_name)
    raise ValueError(f'Embedding model nao suportado: {model_name}')
