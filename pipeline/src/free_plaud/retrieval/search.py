import re
import unicodedata

from free_plaud.providers.embed import Embedder
from free_plaud.retrieval.models import Chunk, SearchHit
from free_plaud.storage.vector import LocalVectorStore

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


def extract_named_query_terms(query: str) -> list[str]:
    """Extrai anchors nomeados da pergunta, como produtos, siglas e tecnologias."""
    seen: set[str] = set()
    named_terms: list[str] = []
    for token in TOKEN_PATTERN.findall(query):
        lowered = token.lower()
        if lowered in STOPWORDS or len(token) <= 3:
            continue
        if token.isupper() or token[:1].isupper():
            if lowered in seen:
                continue
            seen.add(lowered)
            named_terms.append(token)
    return named_terms


def _strip_accents(text: str) -> str:
    normalized = unicodedata.normalize('NFKD', text)
    return ''.join(char for char in normalized if not unicodedata.combining(char))


def _stem_like(token: str) -> str:
    normalized = _strip_accents(token.lower())
    normalized = re.sub(r'[^0-9a-z_]+', '', normalized)
    for suffix in (
        'mente',
        'coes',
        'cao',
        'ando',
        'endo',
        'indo',
        'ndo',
        'ados',
        'adas',
        'idos',
        'idas',
        'ado',
        'ada',
        'ido',
        'ida',
        'ar',
        'er',
        'ir',
        'es',
        's',
    ):
        if len(normalized) > len(suffix) + 2 and normalized.endswith(suffix):
            normalized = normalized[: -len(suffix)]
            break
    if len(normalized) > 3 and normalized[-1] in {'a', 'e', 'i', 'o', 'u'}:
        normalized = normalized[:-1]
    return normalized


def _term_matches(query_term: str, candidate_term: str) -> bool:
    left = _stem_like(query_term)
    right = _stem_like(candidate_term)
    if not left or not right:
        return False
    if left == right:
        return True
    shorter, longer = sorted((left, right), key=len)
    return len(shorter) >= 4 and shorter in longer


def match_terms_in_text(query_terms: list[str], text: str) -> tuple[list[str], float]:
    if not query_terms:
        return [], 0.0
    haystack_terms = set(TOKEN_PATTERN.findall(text.lower()))
    matched_terms = [
        term for term in query_terms if any(_term_matches(term, candidate) for candidate in haystack_terms)
    ]
    return matched_terms, len(matched_terms) / len(query_terms)


def lexical_search_hits(query: str, chunks: list[Chunk], top_k: int = 5) -> list[SearchHit]:
    """Busca lexical simples com score e cobertura para decisões de evidência."""
    if top_k <= 0:
        return []

    normalized_terms = normalize_query_terms(query)
    if not normalized_terms:
        return []

    scored: list[SearchHit] = []
    for chunk in chunks:
        matched_terms, term_coverage = match_terms_in_text(normalized_terms, chunk.chunk_text)
        if not matched_terms:
            continue
        scored.append(
            SearchHit(
                chunk=chunk,
                score=float(len(matched_terms)),
                matched_terms=matched_terms,
                term_coverage=term_coverage,
                strategy='lexical',
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


def semantic_search(
    query: str,
    vector_store: LocalVectorStore,
    embedder: Embedder,
    *,
    top_k: int = 5,
    note_id: str | None = None,
) -> list[SearchHit]:
    """Executa busca semântica no vector store local."""
    if not query.strip() or top_k <= 0:
        return []
    query_terms = normalize_query_terms(query)
    query_embedding = embedder.embed([query])[0]
    hits = vector_store.query(query_embedding, top_k=top_k, note_id=note_id)
    for hit in hits:
        matched_terms, term_coverage = match_terms_in_text(query_terms, hit.chunk.chunk_text)
        hit.matched_terms = matched_terms
        hit.term_coverage = term_coverage
    return hits
