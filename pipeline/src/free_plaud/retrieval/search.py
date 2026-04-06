import re

from free_plaud.retrieval.models import Chunk, SearchHit

TOKEN_PATTERN = re.compile(r"[0-9A-Za-zÀ-ÖØ-öø-ÿ_]+", re.UNICODE)
STOPWORDS = {
    'a',
    'ao',
    'aos',
    'as',
    'como',
    'com',
    'da',
    'das',
    'de',
    'do',
    'dos',
    'e',
    'em',
    'na',
    'nas',
    'no',
    'nos',
    'o',
    'os',
    'para',
    'por',
    'qual',
    'quais',
    'que',
    'se',
    'sem',
    'sua',
    'suas',
    'seu',
    'seus',
    'uma',
    'um',
}


def normalize_query_terms(query: str) -> list[str]:
    """Extrai termos informativos da pergunta para a busca lexical inicial."""
    seen: set[str] = set()
    normalized: list[str] = []
    for token in TOKEN_PATTERN.findall(query.lower()):
        if len(token) <= 1 or token in STOPWORDS or token in seen:
            continue
        seen.add(token)
        normalized.append(token)
    return normalized


def lexical_search_hits(query: str, chunks: list[Chunk], top_k: int = 5) -> list[SearchHit]:
    """Busca lexical simples com score e cobertura para decisões de evidência."""
    if top_k <= 0:
        return []

    normalized_terms = normalize_query_terms(query)
    if not normalized_terms:
        return []

    scored: list[SearchHit] = []
    for chunk in chunks:
        haystack_terms = set(TOKEN_PATTERN.findall(chunk.chunk_text.lower()))
        matched_terms = [term for term in normalized_terms if term in haystack_terms]
        if not matched_terms:
            continue
        scored.append(
            SearchHit(
                chunk=chunk,
                score=float(len(matched_terms)),
                matched_terms=matched_terms,
                term_coverage=len(matched_terms) / len(normalized_terms),
            )
        )

    ranked = sorted(
        scored,
        key=lambda item: (-item.score, -item.term_coverage, item.chunk.chunk_index),
    )
    return ranked[:top_k]


def lexical_search(query: str, chunks: list[Chunk], top_k: int = 5) -> list[Chunk]:
    """Mantem compatibilidade com o scaffold inicial retornando apenas chunks."""
    return [hit.chunk for hit in lexical_search_hits(query, chunks, top_k=top_k)]
