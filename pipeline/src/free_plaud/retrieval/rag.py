import re
from time import perf_counter

from free_plaud.notes.schemas import Note
from free_plaud.retrieval.indexer import index_note
from free_plaud.retrieval.models import AnswerClaim, AskResponse, Citation, SearchHit, UsedSource
from free_plaud.retrieval.search import lexical_search_hits, normalize_query_terms

SENTENCE_SPLIT_PATTERN = re.compile(r'(?<=[.!?])\s+|\n+')


def _collapse_whitespace(text: str) -> str:
    return re.sub(r'\s+', ' ', text).strip()


def _shorten_snippet(text: str, max_length: int = 220) -> str:
    collapsed = _collapse_whitespace(text)
    if len(collapsed) <= max_length:
        return collapsed
    return collapsed[: max_length - 3].rstrip() + '...'


def _sentence_candidates(text: str) -> list[str]:
    candidates = [_collapse_whitespace(part) for part in SENTENCE_SPLIT_PATTERN.split(text)]
    return [candidate for candidate in candidates if candidate]


def _best_claim_text(chunk_text: str, query_terms: list[str]) -> str:
    candidates = _sentence_candidates(chunk_text)
    if not candidates:
        return _shorten_snippet(chunk_text)

    scored: list[tuple[int, int, int, str]] = []
    for candidate in candidates:
        lower = candidate.lower()
        matches = sum(1 for term in query_terms if term in lower)
        if matches <= 0:
            continue
        is_complete = 1 if candidate[-1] in '.!?' else 0
        scored.append((matches, is_complete, len(candidate), candidate))

    if not scored:
        return _shorten_snippet(chunk_text)

    _, _, _, best = sorted(scored, key=lambda item: (-item[0], -item[1], -item[2]))[0]
    return best


def _citation_from_hit(note: Note, hit: SearchHit) -> Citation:
    chunk = hit.chunk
    return Citation(
        note_id=chunk.note_id,
        note_version=chunk.note_version,
        chunk_id=chunk.chunk_id,
        snippet=_shorten_snippet(chunk.chunk_text),
        source_path=str(note.source_path),
        char_start=chunk.char_start,
        char_end=chunk.char_end,
    )


def _support_level(hit: SearchHit, query_terms: list[str]) -> str:
    if hit.term_coverage >= 0.6 or len(hit.matched_terms) >= min(2, len(query_terms)):
        return 'direct'
    return 'partial'


def _build_claims(note: Note, hits: list[SearchHit], query_terms: list[str], *, max_claims: int) -> list[AnswerClaim]:
    claims: list[AnswerClaim] = []
    seen_texts: set[str] = set()
    for hit in hits[:max_claims]:
        claim_text = _best_claim_text(hit.chunk.chunk_text, query_terms)
        normalized = claim_text.lower()
        if not claim_text or normalized in seen_texts:
            continue
        seen_texts.add(normalized)
        claims.append(
            AnswerClaim(
                text=claim_text,
                citations=[_citation_from_hit(note, hit)],
                support_level=_support_level(hit, query_terms),
            )
        )
    return claims


def _flatten_citations(claims: list[AnswerClaim]) -> list[Citation]:
    flattened: list[Citation] = []
    seen_chunk_ids: set[str] = set()
    for claim in claims:
        for citation in claim.citations:
            if citation.chunk_id in seen_chunk_ids:
                continue
            seen_chunk_ids.add(citation.chunk_id)
            flattened.append(citation)
    return flattened


def _summarize_sources(note: Note, hits: list[SearchHit]) -> list[UsedSource]:
    if not hits:
        return []
    chunk_ids = list(dict.fromkeys(hit.chunk.chunk_id for hit in hits))
    return [
        UsedSource(
            doc_id=note.note_id,
            note_version=note.note_version,
            source_path=str(note.source_path),
            chunk_ids=chunk_ids,
        )
    ]


def _build_no_answer(
    *,
    question: str,
    reason: str,
    limitations: list[str],
    used_sources: list[UsedSource],
    latency_ms: int,
) -> AskResponse:
    return AskResponse(
        query=question,
        status='no_answer',
        no_answer=True,
        answer=None,
        claims=[],
        citations=[],
        limitations=limitations,
        reason_for_no_answer=reason,
        used_sources=used_sources,
        latency_ms=latency_ms,
    )


def answer_with_citations(
    note: Note,
    question: str,
    top_k: int = 3,
    *,
    min_term_coverage: float = 0.4,
    max_claims: int = 2,
) -> AskResponse:
    """Responde apenas quando há evidência recuperada suficiente e citável."""
    started_at = perf_counter()
    query_terms = normalize_query_terms(question)
    if not query_terms:
        return _build_no_answer(
            question=question,
            reason='query_without_content',
            limitations=['A pergunta não contém termos informativos suficientes para recuperação.'],
            used_sources=[],
            latency_ms=int((perf_counter() - started_at) * 1000),
        )

    chunks = index_note(note)
    hits = lexical_search_hits(question, chunks, top_k=top_k)
    used_sources = _summarize_sources(note, hits)

    if not hits:
        return _build_no_answer(
            question=question,
            reason='no_retrieval_hits',
            limitations=['Nenhum chunk recuperado contém termos informativos suficientes da pergunta.'],
            used_sources=used_sources,
            latency_ms=int((perf_counter() - started_at) * 1000),
        )

    if hits[0].term_coverage < min_term_coverage:
        return _build_no_answer(
            question=question,
            reason='insufficient_term_coverage',
            limitations=['Os trechos recuperados compartilham poucos termos informativos com a pergunta.'],
            used_sources=used_sources,
            latency_ms=int((perf_counter() - started_at) * 1000),
        )

    claims = _build_claims(note, hits, query_terms, max_claims=max(1, min(max_claims, top_k)))
    citations = _flatten_citations(claims)

    if not claims or any(not claim.citations for claim in claims):
        return _build_no_answer(
            question=question,
            reason='citation_validation_failed',
            limitations=['A evidência foi recuperada, mas não gerou claims citáveis de forma consistente.'],
            used_sources=used_sources,
            latency_ms=int((perf_counter() - started_at) * 1000),
        )

    answer = ' '.join(dict.fromkeys(claim.text for claim in claims))
    limitations: list[str] = []
    if any(claim.support_level == 'partial' for claim in claims):
        limitations.append('Parte da resposta depende de evidência parcial recuperada por busca lexical.')
    if len(citations) == 1:
        limitations.append('A resposta se apoia em um único chunk recuperado.')

    return AskResponse(
        query=question,
        status='answer',
        no_answer=False,
        answer=answer,
        claims=claims,
        citations=citations,
        limitations=limitations,
        reason_for_no_answer=None,
        used_sources=used_sources,
        latency_ms=int((perf_counter() - started_at) * 1000),
    )
