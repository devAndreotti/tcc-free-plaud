from typing import Protocol

from escolio.app.config import Settings
from escolio.providers.embed import (
    EmbeddingDevice,
    _resolve_sentence_transformer_device,
)
from escolio.retrieval.models import SearchHit

DEFAULT_RERANK_MODEL = 'BAAI/bge-reranker-v2-m3'


class Reranker(Protocol):
    """Pontua pares pergunta-passagem; score maior significa mais relevante."""

    model_name: str

    def score(self, query: str, passages: list[str]) -> list[float]:
        """Devolve um score por passagem, na mesma ordem da entrada."""


class CrossEncoderReranker:
    """Reranker local via sentence_transformers.CrossEncoder (import feito só na criação)."""

    def __init__(self, model_name: str = DEFAULT_RERANK_MODEL, *, device: EmbeddingDevice = 'cpu') -> None:
        from sentence_transformers import CrossEncoder

        self.model_name = model_name
        self.device = _resolve_sentence_transformer_device(device)
        try:
            self._model = CrossEncoder(model_name, device=self.device)
        except Exception as exc:
            raise RuntimeError(
                f"Falha ao carregar reranker '{model_name}' no device '{self.device}'. "
                f"Causa original: {type(exc).__name__}: {exc}"
            ) from exc

    def score(self, query: str, passages: list[str]) -> list[float]:
        if not passages:
            return []
        scores = self._model.predict([(query, passage) for passage in passages])
        return [float(score) for score in scores]


def rerank_hits(
    query: str,
    hits: list[SearchHit],
    reranker: Reranker | None,
    top_k: int,
) -> list[SearchHit]:
    """Reordena hits pelo score do reranker; sem reranker, só corta em top_k e mantém a ordem.

    O score do reranker vai em `rerank_score`: `score` não muda, porque os limiares de abstenção
    do ask foram calibrados na escala RRF/vetor e logits do cross-encoder os distorceriam.

    O desempate é estável: hits com o mesmo score mantêm a ordem original.
    """
    if reranker is None or not hits:
        return hits[:top_k]

    scores = reranker.score(query, [hit.chunk.chunk_text for hit in hits])
    if len(scores) != len(hits):
        raise ValueError(f'Reranker devolveu {len(scores)} scores para {len(hits)} hits.')

    order = sorted(range(len(hits)), key=lambda index: (-scores[index], index))
    return [hits[index].model_copy(update={'rerank_score': scores[index]}) for index in order[:top_k]]


_RERANKER_CACHE: dict[tuple[str, str], Reranker] = {}


def reranker_from_settings(settings: Settings) -> Reranker | None:
    """Reranker configurado (cacheado: carregar o cross-encoder custa segundos); vazio desliga."""
    model_name = settings.rerank_model.strip()
    if not model_name:
        return None
    key = (model_name, settings.embedding_device)
    if key not in _RERANKER_CACHE:
        _RERANKER_CACHE[key] = CrossEncoderReranker(model_name, device=settings.embedding_device)
    return _RERANKER_CACHE[key]
