import re
import sqlite3
from time import perf_counter
from typing import Literal

from free_plaud.notes.schemas import Note
from free_plaud.providers.answer import AnswerProvider
from free_plaud.providers.embed import Embedder
from free_plaud.retrieval.debug import build_ask_debug
from free_plaud.retrieval.models import AnswerClaim, AskDebug, AskResponse, Citation, SearchHit, UsedSource
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
    fuse_hits_by_rank,
    lexical_search_hits,
    match_terms_in_text,
    normalize_query_terms,
    open_semantic_search,
)
from free_plaud.storage.sqlite import (
    count_chunks,
    ensure_chunks_fts_current,
    get_notes_by_id,
    list_chunk_ids,
    list_chunks,
    search_chunks_fts,
)
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


def _contexts_for_answer_provider(claims: list[AnswerClaim]) -> list[str]:
    contexts: list[str] = []
    for index, claim in enumerate(claims, start=1):
        citation_refs = ', '.join(citation.chunk_id for citation in claim.citations)
        snippets = ' '.join(citation.snippet for citation in claim.citations)
        contexts.append(f'[{index}] chunks={citation_refs}\nClaim: {claim.text}\nTrecho: {snippets}')
    return contexts


def _filter_hits_to_persisted_chunks(hits: list[SearchHit], valid_chunk_ids: set[str]) -> tuple[list[SearchHit], int]:
    filtered: list[SearchHit] = []
    stale_chunk_ids: set[str] = set()
    for hit in hits:
        if hit.chunk.chunk_id in valid_chunk_ids:
            filtered.append(hit)
        else:
            stale_chunk_ids.add(hit.chunk.chunk_id)
    return filtered, len(stale_chunk_ids)


def _build_fts_match_query(query_terms: list[str]) -> str:
    escaped_terms = [term.replace('"', '""') for term in query_terms if term.strip()]
    return ' OR '.join(f'"{term}"' for term in escaped_terms)


def fts_lexical_search_hits(
    connection: sqlite3.Connection,
    query: str,
    *,
    top_k: int = 5,
    candidate_limit: int | None = None,
) -> list[SearchHit]:
    """Busca lexical do corpus via FTS5/BM25, com fallback Python se FTS falhar."""
    if top_k <= 0:
        return []

    query_terms = normalize_query_terms(query)
    if not query_terms:
        return []

    match_query = _build_fts_match_query(query_terms)
    if not match_query:
        return []

    try:
        ensure_chunks_fts_current(connection)
        candidate_rows = search_chunks_fts(
            connection,
            match_query,
            limit=candidate_limit or max(top_k * 4, 40),
        )
    except sqlite3.OperationalError:
        return lexical_search_hits(query, list_chunks(connection), top_k=top_k)

    scored: list[SearchHit] = []
    for rank, (chunk, bm25_score) in enumerate(candidate_rows, start=1):
        matched_terms, term_coverage = match_terms_in_text(query_terms, chunk.chunk_text)
        if not matched_terms:
            continue
        scored.append(
            SearchHit(
                chunk=chunk,
                score=float(len(matched_terms)) + (1.0 / rank),
                matched_terms=matched_terms,
                term_coverage=term_coverage,
                strategy='lexical',
                distance=abs(bm25_score),
            )
        )

    if scored:
        return scored[:top_k]
    return lexical_search_hits(query, list_chunks(connection), top_k=top_k)


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
    *,
    connection: sqlite3.Connection,
    valid_chunk_ids: set[str],
    top_k: int,
    strategy: RetrievalStrategy,
    vector_store: LocalVectorStore | None,
    embedder: Embedder | None,
) -> tuple[list[SearchHit], int]:
    if strategy == 'lexical':
        return fts_lexical_search_hits(connection, question, top_k=top_k), 0

    if vector_store is None or embedder is None:
        raise ValueError('Vector store e embedder sao obrigatorios para strategy=vector e strategy=hybrid.')

    candidate_pool_size = max(top_k * 8, 24)
    if strategy == 'vector':
        vector_hits = open_semantic_search(question, vector_store, embedder, top_k=candidate_pool_size)
        filtered_hits, stale_count = _filter_hits_to_persisted_chunks(vector_hits, valid_chunk_ids)
        return filtered_hits[:top_k], stale_count

    if strategy == 'hybrid':
        lexical_hits = fts_lexical_search_hits(
            connection,
            question,
            top_k=max(top_k * 3, top_k),
        )
        vector_hits = open_semantic_search(question, vector_store, embedder, top_k=candidate_pool_size)
        filtered_vector_hits, stale_count = _filter_hits_to_persisted_chunks(vector_hits, valid_chunk_ids)
        return (
            fuse_hits_by_rank(
                lexical_hits,
                filtered_vector_hits,
                top_k=top_k,
            ),
            stale_count,
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
    answer_provider: AnswerProvider | None = None,
    include_debug: bool = False,
) -> AskResponse:
    """Responde usando todo o corpus persistido, mantendo citacoes por chunk."""
    started_at = perf_counter()
    query_terms = normalize_query_terms(question)
    named_query_terms = extract_named_query_terms(question)
    note_lookup: dict[str, Note] = {}
    stale_vector_hits_count = 0

    def _debug_payload(
        *,
        reason: str | None = None,
        hits: list[SearchHit] | None = None,
        rejected_hits: list[SearchHit] | None = None,
    ) -> AskDebug | None:
        if not include_debug:
            return None
        return build_ask_debug(
            strategy=strategy,
            query_terms=query_terms,
            named_query_terms=named_query_terms,
            hits=hits or [],
            rejected_hits=rejected_hits or [],
            note_lookup=note_lookup,
            no_answer_reason=reason,
            stale_vector_hits_count=stale_vector_hits_count,
        )

    def _no_answer(
        reason: str,
        limitations: list[str],
        used_sources: list[UsedSource],
        rejected_hits: list[SearchHit] | None = None,
    ) -> AskResponse:
        return _build_no_answer(
            question=question,
            reason=reason,
            limitations=limitations,
            used_sources=used_sources,
            latency_ms=int((perf_counter() - started_at) * 1000),
            debug=_debug_payload(reason=reason, hits=rejected_hits, rejected_hits=rejected_hits),
        )

    if not query_terms:
        return _no_answer('query_without_content', ['A pergunta nao contem termos informativos suficientes para recuperacao.'], [])

    if count_chunks(connection) == 0:
        return _no_answer('empty_corpus', ['O corpus persistido ainda nao contem chunks indexados.'], [])

    valid_chunk_ids = list_chunk_ids(connection)
    raw_hits, stale_vector_hits_count = _retrieve_corpus_hits(
        question,
        connection=connection,
        valid_chunk_ids=valid_chunk_ids,
        top_k=top_k,
        strategy=strategy,
        vector_store=vector_store,
        embedder=embedder,
    )
    hits = _dedupe_hits(raw_hits)
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
        return _no_answer(
            'no_retrieval_hits',
            _with_stale_limitations(['Nenhum chunk do corpus contem termos informativos suficientes da pergunta.']),
            used_sources,
        )

    if strategy == 'lexical' and hits[0].term_coverage < min_term_coverage:
        return _no_answer(
            'insufficient_term_coverage',
            _with_stale_limitations(['Os trechos recuperados compartilham poucos termos informativos com a pergunta.']),
            used_sources,
            rejected_hits=hits,
        )

    if strategy == 'vector':
        top_hit = hits[0]
        if top_hit.score < min_vector_score or top_hit.term_coverage < min_vector_term_coverage:
            return _no_answer(
                'insufficient_vector_evidence',
                _with_stale_limitations(['Os hits vetoriais recuperados nao apresentam evidencia lexical ou score suficiente.']),
                used_sources,
                rejected_hits=hits,
            )

    if strategy == 'hybrid':
        top_hit = hits[0]
        if top_hit.term_coverage < min_hybrid_term_coverage and len(top_hit.matched_terms) < 1:
            return _no_answer(
                'insufficient_hybrid_evidence',
                _with_stale_limitations(['Os hits hibridos recuperados nao apresentam evidencia lexical suficiente.']),
                used_sources,
                rejected_hits=hits,
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
        return _no_answer(
            'citation_validation_failed',
            _with_stale_limitations(['A evidencia foi recuperada, mas nao gerou claims citaveis de forma consistente.']),
            used_sources,
            rejected_hits=hits,
        )

    if strategy in {'vector', 'hybrid'} and grounded_coverage < min_vector_term_coverage:
        if len(grounded_matches) <= 1:
            reason = 'insufficient_vector_specificity' if strategy == 'vector' else 'insufficient_hybrid_specificity'
            return _no_answer(
                reason,
                _with_stale_limitations(['Os claims gerados nao trouxeram especificidade textual suficiente.']),
                used_sources,
                rejected_hits=hits,
            )
        return _no_answer(
            'insufficient_grounded_claims',
            _with_stale_limitations(['Os claims gerados nao mantiveram ancoragem textual suficiente com a pergunta.']),
            used_sources,
            rejected_hits=hits,
        )

    if strategy in {'vector', 'hybrid'} and named_query_terms:
        _, named_coverage = match_terms_in_text(named_query_terms, grounded_text)
        if named_coverage < 1.0:
            return _no_answer(
                'missing_named_anchor',
                _with_stale_limitations(['A resposta nao sustentou os anchors nomeados presentes na pergunta.']),
                used_sources,
                rejected_hits=hits,
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
            reason = 'insufficient_vector_specificity' if strategy == 'vector' else 'insufficient_hybrid_specificity'
            return _no_answer(
                reason,
                _with_stale_limitations(['A resposta recuperada ficou curta e pouco especifica para os termos da pergunta.']),
                used_sources,
                rejected_hits=hits,
            )

    cited_sources = _summarize_corpus_sources(_hits_for_citations(hits, citations), note_lookup)
    limitations: list[str] = list(stale_limitations)
    if any(claim.support_level == 'partial' for claim in claims):
        limitations.append('Parte da resposta depende de evidencia parcial recuperada.')
    if len(citations) == 1:
        limitations.append('A resposta se apoia em um unico chunk recuperado.')
    if len(cited_sources) > 1:
        limitations.append('A resposta combina evidencia de multiplos arquivos do corpus.')

    if answer_provider is not None:
        try:
            answer = answer_provider.answer(question, _contexts_for_answer_provider(claims))
        except Exception as exc:  # noqa: BLE001 - RAG deve sobreviver a provider externo indisponivel.
            limitations.append(f'Provider de resposta falhou; usando resposta extrativa. Erro: {exc}')

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
        debug=_debug_payload(hits=hits),
    )
