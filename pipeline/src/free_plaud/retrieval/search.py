import re
import unicodedata
from functools import lru_cache

from free_plaud.providers.embed import Embedder
from free_plaud.retrieval.models import Chunk, SearchHit
from free_plaud.storage.vector import LocalVectorStore

TOKEN_PATTERN = re.compile(r"[0-9A-Za-zÀ-ÖØ-öø-ÿ_]+", re.UNICODE)
DEFAULT_HYBRID_RANK_CONSTANT = 60
DEFAULT_HYBRID_LEXICAL_WEIGHT = 1.5
DEFAULT_HYBRID_VECTOR_WEIGHT = 1.0
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
LOW_SIGNAL_QUERY_TERMS = {
    'foi',
    'foram',
    'era',
    'eram',
    'sao',
    'ser',
    'estar',
    'tem',
    'teve',
    'havia',
    'existe',
    'existem',
    'escolhido',
    'escolhida',
    'aprovado',
    'aprovada',
    'adotado',
    'adotada',
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
    tokens = TOKEN_PATTERN.findall(query)
    for index, token in enumerate(tokens):
        lowered = token.lower()
        if lowered in STOPWORDS:
            continue
        is_named_token = len(token) > 3 and (token.isupper() or token[:1].isupper())
        is_short_anchor = _is_adjacent_short_anchor(tokens, index)
        if is_named_token or is_short_anchor:
            if lowered in seen:
                continue
            seen.add(lowered)
            named_terms.append(token)
    return named_terms


def _is_adjacent_short_anchor(tokens: list[str], index: int) -> bool:
    token = tokens[index]
    lowered = token.lower()
    if len(token) > 3 or lowered in STOPWORDS:
        return False
    if not (token.isupper() or any(char.isdigit() for char in token)):
        return False

    neighbors = [tokens[item].lower() for item in (index - 1, index + 1) if 0 <= item < len(tokens)]
    return any(len(neighbor) >= 4 and neighbor not in STOPWORDS for neighbor in neighbors)


@lru_cache(maxsize=65536)
def _strip_accents(text: str) -> str:
    normalized = unicodedata.normalize('NFKD', text)
    return ''.join(char for char in normalized if not unicodedata.combining(char))


@lru_cache(maxsize=65536)
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
    return _stem_matches(left, right)


def _stem_matches(left: str, right: str) -> bool:
    if not left or not right:
        return False
    if left == right:
        return True
    shorter, longer = sorted((left, right), key=len)
    return len(shorter) >= 4 and shorter in longer


@lru_cache(maxsize=4096)
def _text_stems(text: str) -> frozenset[str]:
    # O mesmo chunk é comparado centenas de vezes por pergunta (busca + montagem das afirmações).
    return frozenset(_stem_like(candidate) for candidate in TOKEN_PATTERN.findall(text.lower()))


def match_terms_in_text(query_terms: list[str], text: str) -> tuple[list[str], float]:
    if not query_terms:
        return [], 0.0
    haystack_stems = _text_stems(text)
    query_stems = [(term, _stem_like(term)) for term in query_terms]
    matched_terms = [
        term
        for term, stem in query_stems
        if stem in haystack_stems or any(_stem_matches(stem, candidate) for candidate in haystack_stems)
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


def _named_anchor_coverage(query: str, text: str) -> float:
    named_terms = extract_named_query_terms(query)
    if not named_terms:
        return 0.0
    _, coverage = match_terms_in_text(named_terms, text)
    return coverage


def _high_signal_query_terms(query_terms: list[str]) -> list[str]:
    return [term for term in query_terms if len(term) >= 4 and term not in LOW_SIGNAL_QUERY_TERMS]


def _open_hit_evidence_score(
    hit: SearchHit,
    *,
    query_term_count: int,
    named_anchor_coverage: float,
    high_signal_match_count: int,
) -> float:
    matched_count = len(hit.matched_terms)
    adjusted = hit.score
    adjusted += hit.term_coverage * 0.6
    adjusted += min(matched_count, 4) * 0.06
    adjusted += min(high_signal_match_count, 3) * 0.08
    adjusted += named_anchor_coverage * 0.2

    if matched_count == 0:
        adjusted -= 0.35
    if hit.term_coverage == 0:
        adjusted -= 0.25
    if query_term_count >= 4 and matched_count <= 1:
        adjusted -= 0.12
    return adjusted


def _is_low_evidence_open_hit(
    hit: SearchHit,
    *,
    query_term_count: int,
    named_terms_present: bool,
    named_anchor_coverage: float,
    high_signal_term_count: int,
    high_signal_match_count: int,
) -> bool:
    matched_count = len(hit.matched_terms)
    if query_term_count >= 3 and matched_count == 0:
        return True
    if query_term_count >= 5 and hit.term_coverage < 0.2 and matched_count < 2:
        return True
    if high_signal_term_count >= 3 and high_signal_match_count == 0:
        return True
    return bool(named_terms_present and named_anchor_coverage <= 0.0 and hit.term_coverage < 0.34)


def open_semantic_search(
    query: str,
    vector_store: LocalVectorStore,
    embedder: Embedder,
    *,
    top_k: int = 5,
) -> list[SearchHit]:
    """Busca vetorial aberta com reranking lexical-aware e poda leve de falso positivo."""
    if not query.strip() or top_k <= 0:
        return []

    query_terms = normalize_query_terms(query)
    high_signal_terms = _high_signal_query_terms(query_terms)
    named_terms = extract_named_query_terms(query)
    candidate_pool = max(top_k * 4, 12)
    hits = semantic_search(query, vector_store, embedder, top_k=candidate_pool, note_id=None)
    if not hits:
        return []

    ranked_rows: list[tuple[float, float, int, float, SearchHit]] = []
    for hit in hits:
        anchor_coverage = _named_anchor_coverage(query, hit.chunk.chunk_text)
        high_signal_matches = [term for term in hit.matched_terms if term in high_signal_terms]
        evidence_score = _open_hit_evidence_score(
            hit,
            query_term_count=len(query_terms),
            named_anchor_coverage=anchor_coverage,
            high_signal_match_count=len(high_signal_matches),
        )
        ranked_rows.append((evidence_score, hit.term_coverage, len(hit.matched_terms), anchor_coverage, hit))

    reranked = [
        row[-1]
        for row in sorted(
            ranked_rows,
            key=lambda item: (-item[0], -item[1], -item[2], -item[3], -item[4].score, item[4].chunk.chunk_index),
        )
    ]

    filtered = [
        hit
        for hit in reranked
        if not _is_low_evidence_open_hit(
            hit,
            query_term_count=len(query_terms),
            named_terms_present=bool(named_terms),
            named_anchor_coverage=_named_anchor_coverage(query, hit.chunk.chunk_text),
            high_signal_term_count=len(high_signal_terms),
            high_signal_match_count=len([term for term in hit.matched_terms if term in high_signal_terms]),
        )
    ]

    selected = filtered if filtered else ([] if len(query_terms) >= 4 else reranked[:1])
    return selected[:top_k]


def _fuse_hits_by_rank(
    lexical_hits: list[SearchHit],
    vector_hits: list[SearchHit],
    *,
    top_k: int,
    rank_constant: int = DEFAULT_HYBRID_RANK_CONSTANT,
    lexical_weight: float = DEFAULT_HYBRID_LEXICAL_WEIGHT,
    vector_weight: float = DEFAULT_HYBRID_VECTOR_WEIGHT,
) -> list[SearchHit]:
    fused: dict[str, SearchHit] = {}
    fused_scores: dict[str, float] = {}

    for source_hits, weight in ((lexical_hits, lexical_weight), (vector_hits, vector_weight)):
        for rank, hit in enumerate(source_hits, start=1):
            chunk_id = hit.chunk.chunk_id
            fused_scores[chunk_id] = fused_scores.get(chunk_id, 0.0) + (weight / (rank_constant + rank))
            existing = fused.get(chunk_id)
            if existing is None:
                fused[chunk_id] = SearchHit(
                    chunk=hit.chunk,
                    score=0.0,
                    matched_terms=list(hit.matched_terms),
                    term_coverage=hit.term_coverage,
                    strategy='hybrid',
                    distance=hit.distance,
                )
                continue

            existing.matched_terms = list(dict.fromkeys([*existing.matched_terms, *hit.matched_terms]))
            existing.term_coverage = max(existing.term_coverage, hit.term_coverage)
            if existing.distance is None and hit.distance is not None:
                existing.distance = hit.distance

    ranked = sorted(
        (
            SearchHit(
                chunk=hit.chunk,
                score=fused_scores[chunk_id],
                matched_terms=hit.matched_terms,
                term_coverage=hit.term_coverage,
                strategy='hybrid',
                distance=hit.distance,
            )
            for chunk_id, hit in fused.items()
        ),
        key=lambda item: (-item.score, -item.term_coverage, -len(item.matched_terms), item.chunk.chunk_index),
    )
    return ranked[:top_k]


def fuse_hits_by_rank(
    lexical_hits: list[SearchHit],
    vector_hits: list[SearchHit],
    *,
    top_k: int,
    rank_constant: int = DEFAULT_HYBRID_RANK_CONSTANT,
    lexical_weight: float = DEFAULT_HYBRID_LEXICAL_WEIGHT,
    vector_weight: float = DEFAULT_HYBRID_VECTOR_WEIGHT,
) -> list[SearchHit]:
    """API publica para fusao de hits ja recuperados por caminhos diferentes."""
    return _fuse_hits_by_rank(
        lexical_hits,
        vector_hits,
        top_k=top_k,
        rank_constant=rank_constant,
        lexical_weight=lexical_weight,
        vector_weight=vector_weight,
    )


def hybrid_search(
    query: str,
    chunks: list[Chunk],
    vector_store: LocalVectorStore,
    embedder: Embedder,
    *,
    top_k: int = 5,
    note_id: str | None = None,
    lexical_pool_size: int | None = None,
    vector_pool_size: int | None = None,
    rank_constant: int = DEFAULT_HYBRID_RANK_CONSTANT,
    lexical_weight: float = DEFAULT_HYBRID_LEXICAL_WEIGHT,
    vector_weight: float = DEFAULT_HYBRID_VECTOR_WEIGHT,
) -> list[SearchHit]:
    """Combina lexical + vector com rank fusion simples e reproduzível."""
    if not query.strip() or top_k <= 0:
        return []

    lexical_hits = lexical_search_hits(query, chunks, top_k=lexical_pool_size or max(top_k * 2, top_k))
    vector_hits = semantic_search(
        query,
        vector_store,
        embedder,
        top_k=vector_pool_size or max(top_k * 4, top_k),
        note_id=note_id,
    )
    return _fuse_hits_by_rank(
        lexical_hits,
        vector_hits,
        top_k=top_k,
        rank_constant=rank_constant,
        lexical_weight=lexical_weight,
        vector_weight=vector_weight,
    )
