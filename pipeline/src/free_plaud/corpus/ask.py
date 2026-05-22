import re
import sqlite3
from time import perf_counter
from typing import Literal

from free_plaud.notes.schemas import Note
from free_plaud.providers.embed import Embedder
from free_plaud.retrieval.models import AnswerClaim, AskResponse, Chunk, Citation, SearchHit, UsedSource
from free_plaud.retrieval.rag import (
    _build_no_answer,
    _dedupe_hits,
    _flatten_citations,
    _is_question_like,
    _question_needs_multiple_claims,
    _rank_claim_candidates,
    _shorten_snippet,
    _support_level,
    _trim_claim_span,
)
from free_plaud.retrieval.search import (
    extract_named_query_terms,
    hybrid_search,
    lexical_search_hits,
    match_terms_in_text,
    normalize_query_terms,
    open_semantic_search,
)
from free_plaud.storage.sqlite import get_notes_by_id, list_chunks
from free_plaud.storage.vector import LocalVectorStore

RetrievalStrategy = Literal['lexical', 'vector', 'hybrid']
TEAM_ANSWER_PATTERN = re.compile(r'\bequipe\s+(?:de|da|do|dos|das)\s+[0-9A-Za-zÀ-ÖØ-öø-ÿ_-]+')


def _citation_from_corpus_hit(hit: SearchHit, note_lookup: dict[str, Note]) -> Citation:
    chunk = hit.chunk
    note = note_lookup.get(chunk.note_id)
    return Citation(
        note_id=chunk.note_id,
        note_version=chunk.note_version,
        chunk_id=chunk.chunk_id,
        snippet=_shorten_snippet(chunk.chunk_text),
        source_path=str(note.source_path) if note else None,
        char_start=chunk.char_start,
        char_end=chunk.char_end,
    )


def _summarize_corpus_sources(hits: list[SearchHit], note_lookup: dict[str, Note]) -> list[UsedSource]:
    grouped: dict[str, list[str]] = {}
    versions: dict[str, int] = {}
    for hit in hits:
        grouped.setdefault(hit.chunk.note_id, [])
        if hit.chunk.chunk_id not in grouped[hit.chunk.note_id]:
            grouped[hit.chunk.note_id].append(hit.chunk.chunk_id)
        versions[hit.chunk.note_id] = hit.chunk.note_version

    sources: list[UsedSource] = []
    for note_id, chunk_ids in grouped.items():
        note = note_lookup.get(note_id)
        sources.append(
            UsedSource(
                doc_id=note_id,
                note_version=note.note_version if note else versions[note_id],
                source_path=str(note.source_path) if note else None,
                chunk_ids=chunk_ids,
            )
        )
    return sources


def _hits_for_citations(hits: list[SearchHit], citations: list[Citation]) -> list[SearchHit]:
    cited_chunk_ids = {citation.chunk_id for citation in citations}
    return [hit for hit in hits if hit.chunk.chunk_id in cited_chunk_ids]


def _filter_hits_to_persisted_chunks(hits: list[SearchHit], valid_chunk_ids: set[str]) -> tuple[list[SearchHit], int]:
    filtered: list[SearchHit] = []
    stale_chunk_ids: set[str] = set()
    for hit in hits:
        if hit.chunk.chunk_id in valid_chunk_ids:
            filtered.append(hit)
        else:
            stale_chunk_ids.add(hit.chunk.chunk_id)
    return filtered, len(stale_chunk_ids)


def _trim_claim_preserving_query_terms(question: str, query_terms: list[str], claim_text: str) -> str:
    trimmed = _trim_claim_span(question, query_terms, claim_text)
    original_matches = set(match_terms_in_text(query_terms, claim_text)[0])
    trimmed_matches = set(match_terms_in_text(query_terms, trimmed)[0])
    lost_matches = original_matches - trimmed_matches
    if lost_matches and len(claim_text) <= 260:
        return claim_text.strip(' -,:;')
    lowered_question = question.lower()
    team_answer = TEAM_ANSWER_PATTERN.search(claim_text)
    if team_answer and ('equipe' in lowered_question or 'responsavel' in lowered_question):
        if team_answer.group(0) not in trimmed:
            return claim_text.strip(' -,:;')
    return trimmed


def _build_corpus_claims(
    question: str,
    hits: list[SearchHit],
    query_terms: list[str],
    note_lookup: dict[str, Note],
    *,
    max_claims: int,
) -> list[AnswerClaim]:
    claims: list[AnswerClaim] = []
    seen_texts: set[str] = set()
    seen_chunk_ids: set[str] = set()
    covered_terms: set[str] = set()
    candidate_rows: list[tuple[tuple[int, ...], SearchHit, str]] = []

    for hit_index, hit in enumerate(hits[: max(max_claims, 1) * 3]):
        ranked_candidates = _rank_claim_candidates(hit.chunk.chunk_text, question, query_terms)
        if not ranked_candidates:
            continue

        selected_score, selected_text = next(
            ((score_key, claim_text) for score_key, claim_text in ranked_candidates if not _is_question_like(claim_text)),
            ranked_candidates[0],
        )
        for score_key, claim_text in ranked_candidates[1:5]:
            if _is_question_like(claim_text):
                continue
            starts_clean = 1 if claim_text[0].isupper() or claim_text[0].isdigit() else 0
            selected_starts_clean = 1 if selected_text[0].isupper() or selected_text[0].isdigit() else 0
            if score_key[2] < max(selected_score[2] - 1, 1):
                continue
            if score_key[3] < max(selected_score[3] - 33, 0):
                continue
            preserves_phrase_alignment = score_key[0] >= selected_score[0] and score_key[1] >= max(
                selected_score[1] - 1,
                0,
            )
            is_more_direct = (
                preserves_phrase_alignment
                and score_key[5] > selected_score[5]
                and len(claim_text) + 20 < len(selected_text)
            )
            same_evidence_shorter = (
                score_key[2] >= selected_score[2]
                and score_key[3] >= selected_score[3]
                and len(claim_text) + 40 < len(selected_text)
            )
            if starts_clean > selected_starts_clean or (
                starts_clean == selected_starts_clean and (is_more_direct or same_evidence_shorter)
            ):
                selected_score = score_key
                selected_text = claim_text

        candidate_rows.append(((*selected_score, -hit_index), hit, selected_text))

    for _, hit, claim_text in sorted(candidate_rows, key=lambda item: item[0], reverse=True):
        trimmed_claim = _trim_claim_preserving_query_terms(question, query_terms, claim_text)
        normalized = trimmed_claim.lower()
        if (
            not trimmed_claim
            or _is_question_like(trimmed_claim)
            or normalized in seen_texts
            or hit.chunk.chunk_id in seen_chunk_ids
        ):
            continue

        matched_terms, _ = match_terms_in_text(query_terms, trimmed_claim)
        new_terms = set(matched_terms) - covered_terms
        if claims and not new_terms:
            continue

        seen_texts.add(normalized)
        seen_chunk_ids.add(hit.chunk.chunk_id)
        covered_terms.update(matched_terms)
        claims.append(
            AnswerClaim(
                text=trimmed_claim,
                citations=[_citation_from_corpus_hit(hit, note_lookup)],
                support_level=_support_level(hit, query_terms),
            )
        )
        if len(claims) >= max_claims:
            break

    return claims


def _retrieve_corpus_hits(
    question: str,
    chunks: list[Chunk],
    *,
    top_k: int,
    strategy: RetrievalStrategy,
    vector_store: LocalVectorStore | None,
    embedder: Embedder | None,
) -> list[SearchHit]:
    if strategy == 'lexical':
        return lexical_search_hits(question, chunks, top_k=top_k)

    if vector_store is None or embedder is None:
        raise ValueError('Vector store e embedder sao obrigatorios para strategy=vector e strategy=hybrid.')

    candidate_pool_size = max(top_k * 8, 24)
    if strategy == 'vector':
        return open_semantic_search(question, vector_store, embedder, top_k=candidate_pool_size)[:top_k]

    if strategy == 'hybrid':
        return hybrid_search(
            question,
            chunks,
            vector_store,
            embedder,
            top_k=top_k,
            note_id=None,
            lexical_pool_size=max(top_k * 3, top_k),
            vector_pool_size=candidate_pool_size,
        )

    raise ValueError("strategy deve ser 'lexical', 'vector' ou 'hybrid'.")


def answer_corpus_with_citations(
    question: str,
    *,
    connection: sqlite3.Connection,
    vector_store: LocalVectorStore | None = None,
    embedder: Embedder | None = None,
    strategy: RetrievalStrategy = 'hybrid',
    top_k: int = 6,
    min_term_coverage: float = 0.35,
    min_vector_score: float = 0.55,
    min_vector_term_coverage: float = 0.2,
    min_hybrid_term_coverage: float = 0.2,
    max_claims: int = 3,
) -> AskResponse:
    """Responde usando todo o corpus persistido, mantendo citacoes por chunk."""
    started_at = perf_counter()
    query_terms = normalize_query_terms(question)
    named_query_terms = extract_named_query_terms(question)
    if not query_terms:
        return _build_no_answer(
            question=question,
            reason='query_without_content',
            limitations=['A pergunta nao contem termos informativos suficientes para recuperacao.'],
            used_sources=[],
            latency_ms=int((perf_counter() - started_at) * 1000),
        )

    chunks = list_chunks(connection)
    if not chunks:
        return _build_no_answer(
            question=question,
            reason='empty_corpus',
            limitations=['O corpus persistido ainda nao contem chunks indexados.'],
            used_sources=[],
            latency_ms=int((perf_counter() - started_at) * 1000),
        )

    raw_hits = _retrieve_corpus_hits(
        question,
        chunks,
        top_k=top_k,
        strategy=strategy,
        vector_store=vector_store,
        embedder=embedder,
    )
    filtered_hits, stale_vector_hits_count = _filter_hits_to_persisted_chunks(
        raw_hits,
        {chunk.chunk_id for chunk in chunks},
    )
    hits = _dedupe_hits(filtered_hits)
    stale_limitations = (
        [f'{stale_vector_hits_count} hit(s) vetoriais stale foram descartados por nao existirem no SQLite.']
        if stale_vector_hits_count
        else []
    )

    def _with_stale_limitations(limitations: list[str]) -> list[str]:
        return [*stale_limitations, *limitations]

    note_lookup = get_notes_by_id(connection, [hit.chunk.note_id for hit in hits])
    used_sources = _summarize_corpus_sources(hits, note_lookup)

    if not hits:
        return _build_no_answer(
            question=question,
            reason='no_retrieval_hits',
            limitations=_with_stale_limitations(['Nenhum chunk do corpus contem termos informativos suficientes da pergunta.']),
            used_sources=used_sources,
            latency_ms=int((perf_counter() - started_at) * 1000),
        )

    if strategy == 'lexical' and hits[0].term_coverage < min_term_coverage:
        return _build_no_answer(
            question=question,
            reason='insufficient_term_coverage',
            limitations=_with_stale_limitations(
                ['Os trechos recuperados compartilham poucos termos informativos com a pergunta.']
            ),
            used_sources=used_sources,
            latency_ms=int((perf_counter() - started_at) * 1000),
        )

    if strategy == 'vector':
        top_hit = hits[0]
        if top_hit.score < min_vector_score or top_hit.term_coverage < min_vector_term_coverage:
            return _build_no_answer(
                question=question,
                reason='insufficient_vector_evidence',
                limitations=_with_stale_limitations(
                    ['Os hits vetoriais recuperados nao apresentam evidencia lexical ou score suficiente.']
                ),
                used_sources=used_sources,
                latency_ms=int((perf_counter() - started_at) * 1000),
            )

    if strategy == 'hybrid':
        top_hit = hits[0]
        if top_hit.term_coverage < min_hybrid_term_coverage and len(top_hit.matched_terms) < 1:
            return _build_no_answer(
                question=question,
                reason='insufficient_hybrid_evidence',
                limitations=_with_stale_limitations(
                    ['Os hits hibridos recuperados nao apresentam evidencia lexical suficiente.']
                ),
                used_sources=used_sources,
                latency_ms=int((perf_counter() - started_at) * 1000),
            )

    effective_max_claims = max(1, min(max_claims, top_k))
    if not _question_needs_multiple_claims(question):
        effective_max_claims = 1

    claims = _build_corpus_claims(
        question,
        hits,
        query_terms,
        note_lookup,
        max_claims=effective_max_claims,
    )
    citations = _flatten_citations(claims)
    grounded_text = ' '.join(claim.text for claim in claims)
    grounded_matches, grounded_coverage = match_terms_in_text(query_terms, grounded_text)

    if not claims or any(not claim.citations for claim in claims):
        return _build_no_answer(
            question=question,
            reason='citation_validation_failed',
            limitations=_with_stale_limitations(
                ['A evidencia foi recuperada, mas nao gerou claims citaveis de forma consistente.']
            ),
            used_sources=used_sources,
            latency_ms=int((perf_counter() - started_at) * 1000),
        )

    if strategy in {'vector', 'hybrid'} and grounded_coverage < min_vector_term_coverage:
        if len(grounded_matches) <= 1:
            return _build_no_answer(
                question=question,
                reason='insufficient_vector_specificity' if strategy == 'vector' else 'insufficient_hybrid_specificity',
                limitations=_with_stale_limitations(
                    ['Os claims gerados nao trouxeram especificidade textual suficiente.']
                ),
                used_sources=used_sources,
                latency_ms=int((perf_counter() - started_at) * 1000),
            )
        return _build_no_answer(
            question=question,
            reason='insufficient_grounded_claims',
            limitations=_with_stale_limitations(
                ['Os claims gerados nao mantiveram ancoragem textual suficiente com a pergunta.']
            ),
            used_sources=used_sources,
            latency_ms=int((perf_counter() - started_at) * 1000),
        )

    if strategy in {'vector', 'hybrid'} and named_query_terms:
        _, named_coverage = match_terms_in_text(named_query_terms, grounded_text)
        if named_coverage < 1.0:
            return _build_no_answer(
                question=question,
                reason='missing_named_anchor',
                limitations=_with_stale_limitations(
                    ['A resposta nao sustentou os anchors nomeados presentes na pergunta.']
                ),
                used_sources=used_sources,
                latency_ms=int((perf_counter() - started_at) * 1000),
            )

    answer = ' '.join(dict.fromkeys(claim.text for claim in claims))
    if strategy in {'vector', 'hybrid'}:
        best_claim_match_count = max((len(match_terms_in_text(query_terms, claim.text)[0]) for claim in claims), default=0)
        if (
            len(query_terms) >= 3
            and best_claim_match_count <= 1
            and len(answer) < 80
            and all(claim.support_level == 'partial' for claim in claims)
        ):
            return _build_no_answer(
                question=question,
                reason='insufficient_vector_specificity' if strategy == 'vector' else 'insufficient_hybrid_specificity',
                limitations=_with_stale_limitations(
                    ['A resposta recuperada ficou curta e pouco especifica para os termos da pergunta.']
                ),
                used_sources=used_sources,
                latency_ms=int((perf_counter() - started_at) * 1000),
            )

    cited_sources = _summarize_corpus_sources(_hits_for_citations(hits, citations), note_lookup)
    limitations: list[str] = list(stale_limitations)
    if any(claim.support_level == 'partial' for claim in claims):
        limitations.append('Parte da resposta depende de evidencia parcial recuperada.')
    if len(citations) == 1:
        limitations.append('A resposta se apoia em um unico chunk recuperado.')
    if len(cited_sources) > 1:
        limitations.append('A resposta combina evidencia de multiplos arquivos do corpus.')

    return AskResponse(
        query=question,
        status='answer',
        no_answer=False,
        answer=answer,
        claims=claims,
        citations=citations,
        limitations=limitations,
        reason_for_no_answer=None,
        used_sources=cited_sources,
        latency_ms=int((perf_counter() - started_at) * 1000),
    )
