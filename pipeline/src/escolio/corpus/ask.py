import sqlite3
from collections.abc import Callable
from time import perf_counter

from escolio.corpus import ask_retrieval
from escolio.corpus.answer_context import (
    build_answer_context_items,  # noqa: F401 (reexportado: testes importam de ask)
)
from escolio.corpus.ask_anchors import (  # noqa: F401 (reexportados para quem importa de ask)
    SHORT_ANCHOR_CONFLICT_PENALTY,
    SHORT_ANCHOR_EXACT_BOOST,
    SHORT_ANCHOR_MAX_LENGTH,
    SHORT_ANCHOR_TAIL_BOOST,
    _rerank_hits_by_short_anchor,
)
from escolio.corpus.ask_claims import (  # noqa: F401 (reexportados para quem importa de ask)
    MULTI_FILE_LIMITATION,
    SINGLE_CHUNK_LIMITATION,
    TEAM_ANSWER_PATTERN,
    _build_corpus_claims,
    _citation_from_corpus_hit,
    _hits_for_citations,
    _summarize_corpus_sources,
    _with_cited_context_citations,
    _with_source_limitations,
    answer_limitations,
    build_claims_for_answer,
)
from escolio.corpus.ask_generation import elapsed_ms, generate_answer, provider_identity
from escolio.corpus.ask_grounding import (
    grounding_rejection,
    retrieval_rejection,
    vocabulary_rejection,
)
from escolio.corpus.ask_retrieval import (
    RetrievalStrategy,
    corpus_vocabulary_stems,
)
from escolio.corpus.ask_validation import (  # noqa: F401 (GeneratedAnswerValidation reexportado)
    GeneratedAnswerValidation,
    validate_generated_answer,
)
from escolio.notes.schemas import Note
from escolio.providers.answer import AnswerProvider
from escolio.providers.embed import Embedder
from escolio.retrieval.debug import build_ask_debug
from escolio.retrieval.models import (
    AskDebug,
    AskDebugTimings,
    AskResponse,
    SearchHit,
    UsedSource,
)
from escolio.retrieval.rag import (
    _build_no_answer,
    _dedupe_hits,
    _flatten_citations,
)
from escolio.retrieval.search import (
    extract_named_query_terms,
    normalize_query_terms,
)
from escolio.storage.sqlite import (
    count_chunks,
    get_notes_by_id,
    list_chunk_ids,
    note_ids_under_root,
    search_chunks_fts,
)
from escolio.storage.vector import LocalVectorStore


def fts_lexical_search_hits(
    connection: sqlite3.Connection,
    query: str,
    *,
    top_k: int = 5,
    candidate_limit: int | None = None,
    note_ids: frozenset[str] | None = None,
) -> list[SearchHit]:
    """Busca lexical FTS5/BM25 (em ask_retrieval); `search_chunks_fts` é lido aqui a cada chamada."""
    return ask_retrieval.fts_lexical_search_hits(
        connection,
        query,
        top_k=top_k,
        candidate_limit=candidate_limit,
        note_ids=note_ids,
        search_rows=search_chunks_fts,
    )


def retrieve_corpus_hits(
    question: str,
    *,
    connection: sqlite3.Connection,
    valid_chunk_ids: set[str],
    top_k: int,
    strategy: RetrievalStrategy,
    vector_store: LocalVectorStore | None,
    embedder: Embedder | None,
    note_ids: frozenset[str] | None = None,
) -> tuple[list[SearchHit], int]:
    """Recupera os hits do corpus (implementação em ask_retrieval); `search_chunks_fts` vem deste módulo."""
    return ask_retrieval.retrieve_corpus_hits(
        question,
        connection=connection,
        valid_chunk_ids=valid_chunk_ids,
        top_k=top_k,
        strategy=strategy,
        vector_store=vector_store,
        embedder=embedder,
        search_rows=search_chunks_fts,
        note_ids=note_ids,
    )


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
    source_root: str | None = None,
    on_answer_delta: Callable[[str], None] | None = None,
) -> AskResponse:
    """Responde usando todo o corpus persistido (ou só a pasta `source_root`), mantendo citacoes por chunk."""
    started_at = perf_counter()
    query_terms = normalize_query_terms(question)
    named_query_terms = extract_named_query_terms(question)
    note_lookup: dict[str, Note] = {}
    stale_vector_hits_count = 0
    stage_timings = AskDebugTimings()
    answer_provider_name, provider_model = provider_identity(answer_provider)

    def _debug_payload(
        *,
        reason: str | None = None,
        hits: list[SearchHit] | None = None,
        rejected_hits: list[SearchHit] | None = None,
    ) -> AskDebug | None:
        if not include_debug:
            return None
        debug_timings = stage_timings.model_copy(update={'total_ms': int((perf_counter() - started_at) * 1000)})
        return build_ask_debug(
            strategy=strategy,
            query_terms=query_terms,
            named_query_terms=named_query_terms,
            hits=hits or [],
            rejected_hits=rejected_hits or [],
            note_lookup=note_lookup,
            no_answer_reason=reason,
            stale_vector_hits_count=stale_vector_hits_count,
            timings=debug_timings,
            answer_provider=answer_provider_name,
            provider_model=provider_model,
        )

    def _no_answer(
        reason: str,
        limitations: list[str],
        used_sources: list[UsedSource],
        rejected_hits: list[SearchHit] | None = None,
        discard_reason: str | None = None,
    ) -> AskResponse:
        return _build_no_answer(
            question=question,
            reason=reason,
            limitations=limitations,
            used_sources=used_sources,
            latency_ms=int((perf_counter() - started_at) * 1000),
            debug=_debug_payload(reason=reason, rejected_hits=rejected_hits),
            answer_discard_reason=discard_reason,
            answer_model=provider_model,
        )

    if not query_terms:
        return _no_answer('query_without_content', ['A pergunta não contém termos informativos suficientes para recuperação.'], [])

    if count_chunks(connection) == 0:
        return _no_answer('empty_corpus', ['O corpus persistido ainda não contém trechos indexados.'], [])

    note_ids = frozenset(note_ids_under_root(connection, source_root)) if source_root else None
    if source_root and not note_ids:
        return _no_answer('source_root_without_notes', ['Nenhuma nota indexada está na pasta escolhida.'], [])

    rejection = vocabulary_rejection(query_terms, corpus_vocabulary_stems(connection))
    if rejection is not None:
        return _no_answer(rejection[0], rejection[1], [])

    retrieval_started_at = perf_counter()
    raw_hits, stale_vector_hits_count = retrieve_corpus_hits(
        question,
        connection=connection,
        valid_chunk_ids=list_chunk_ids(connection),
        top_k=top_k,
        strategy=strategy,
        vector_store=vector_store,
        embedder=embedder,
        note_ids=note_ids,
    )
    hits = _dedupe_hits(raw_hits)
    stale_limitations = [f'{stale_vector_hits_count} hit(s) vetoriais desatualizados foram descartados por não existirem no SQLite.'] if stale_vector_hits_count else []

    def _with_stale_limitations(limitations: list[str]) -> list[str]:
        return [*limitations, *stale_limitations]

    note_lookup = get_notes_by_id(connection, [hit.chunk.note_id for hit in hits])
    hits = _rerank_hits_by_short_anchor(question, hits, note_lookup)
    used_sources = _summarize_corpus_sources(hits, note_lookup)
    stage_timings.retrieval_ms = elapsed_ms(retrieval_started_at)

    rejection = retrieval_rejection(
        strategy=strategy,
        hits=hits,
        min_term_coverage=min_term_coverage,
        min_vector_score=min_vector_score,
        min_vector_term_coverage=min_vector_term_coverage,
        min_hybrid_term_coverage=min_hybrid_term_coverage,
    )
    if rejection is not None:
        return _no_answer(rejection[0], _with_stale_limitations(rejection[1]), used_sources, rejected_hits=hits)

    claim_started_at = perf_counter()
    claims = build_claims_for_answer(question, hits, query_terms, note_lookup, top_k=top_k, max_claims=max_claims)
    citations = _flatten_citations(claims)
    stage_timings.claim_build_ms = elapsed_ms(claim_started_at)

    answer = ' '.join(dict.fromkeys(claim.text for claim in claims))
    rejection = grounding_rejection(
        query_terms=query_terms,
        named_query_terms=named_query_terms,
        strategy=strategy,
        claims=claims,
        answer=answer,
        min_vector_term_coverage=min_vector_term_coverage,
    )
    if rejection is not None:
        return _no_answer(rejection[0], _with_stale_limitations(rejection[1]), used_sources, rejected_hits=hits)

    cited_sources = _summarize_corpus_sources(_hits_for_citations(hits, citations), note_lookup)
    limitations = answer_limitations(claims, citations, cited_sources)

    generated = False
    answer_sources: list[str] = []
    discard_reason: str | None = None
    if answer_provider is not None:
        generation = generate_answer(
            question,
            answer=answer,
            claims=claims,
            hits=hits,
            citations=citations,
            cited_sources=cited_sources,
            limitations=limitations,
            note_lookup=note_lookup,
            provider=answer_provider,
            on_answer_delta=on_answer_delta,
            validate=validate_generated_answer,
            stage_timings=stage_timings,
        )
        if generation.rejection is not None:
            reason, rejected_limitations = generation.rejection
            return _no_answer(
                reason,
                _with_stale_limitations(rejected_limitations),
                cited_sources,
                rejected_hits=hits,
                discard_reason=reason,
            )
        answer, citations, cited_sources = generation.answer, generation.citations, generation.cited_sources
        limitations, generated, answer_sources = generation.limitations, generation.generated, generation.answer_sources
        discard_reason = generation.discard_reason

    return AskResponse(
        query=question,
        status='answer',
        no_answer=False,
        answer=answer,
        generated=generated,
        answer_sources=answer_sources,
        claims=claims,
        citations=citations,
        limitations=[*limitations, *stale_limitations],
        reason_for_no_answer=None,
        used_sources=cited_sources,
        latency_ms=int((perf_counter() - started_at) * 1000),
        debug=_debug_payload(hits=hits),
        answer_discard_reason=discard_reason,
        answer_model=provider_model,
    )
