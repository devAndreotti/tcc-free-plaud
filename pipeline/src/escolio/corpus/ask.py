import sqlite3
from collections.abc import Callable
from time import perf_counter

from escolio.corpus import ask_retrieval
from escolio.corpus.answer_context import (
    build_answer_context_items,
    normalize_answer_markers,
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
    _drop_unknown_answer_markers,
    _hits_for_citations,
    _summarize_corpus_sources,
    _trim_claim_preserving_query_terms,
    _with_cited_context_citations,
    _with_source_limitations,
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
from escolio.providers.answer import AnswerProvider, AnswerProviderError
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
    _question_needs_multiple_claims,
)
from escolio.retrieval.search import (
    extract_named_query_terms,
    match_terms_in_text,
    normalize_query_terms,
    terms_missing_from_vocabulary,
)
from escolio.storage.sqlite import (
    count_chunks,
    get_notes_by_id,
    list_chunk_ids,
    note_ids_under_root,
    search_chunks_fts,
)
from escolio.storage.vector import LocalVectorStore


def _provider_failure_limitation(exc: Exception) -> str:
    detail = str(exc)[:200].rstrip('.') if isinstance(exc, AnswerProviderError) else type(exc).__name__
    return f'A IA falhou; usando resposta extrativa. Erro: {detail}.'


def fts_lexical_search_hits(
    connection: sqlite3.Connection,
    query: str,
    *,
    top_k: int = 5,
    candidate_limit: int | None = None,
    note_ids: frozenset[str] | None = None,
) -> list[SearchHit]:
    """Busca lexical do corpus via FTS5/BM25 (implementação em ask_retrieval).

    `search_chunks_fts` é lido deste módulo a cada chamada, para os testes conseguirem substituí-lo.
    """
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
    answer_provider_name = answer_provider.provider_name if answer_provider is not None else None
    provider_model_value = getattr(answer_provider, 'model', None) if answer_provider is not None else None
    provider_model = str(provider_model_value) if provider_model_value is not None else None

    def _elapsed_ms(stage_started_at: float) -> int:
        return int((perf_counter() - stage_started_at) * 1000)

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

    note_ids: frozenset[str] | None = None
    if source_root:
        note_ids = frozenset(note_ids_under_root(connection, source_root))
        if not note_ids:
            return _no_answer('source_root_without_notes', ['Nenhuma nota indexada está na pasta escolhida.'], [])

    # Um termo de conteúdo que não está em nenhuma nota quase sempre é o assunto da pergunta
    # ("senha", "Splunk", "orçamento"): os outros termos acham trechos parecidos e o chat responderia
    # outra coisa. No benchmark, separa 6 de 10 negativas sem recusar nenhuma das 39 positivas.
    vocabulary_stems = corpus_vocabulary_stems(connection)
    missing_terms = terms_missing_from_vocabulary(query_terms, vocabulary_stems) if vocabulary_stems else []
    if missing_terms:
        quoted = ', '.join(f'"{term}"' for term in missing_terms)
        verb = 'aparece' if len(missing_terms) == 1 else 'aparecem'
        return _no_answer(
            'query_term_not_in_corpus',
            [f'A pergunta cita {quoted}, que não {verb} em nenhuma nota do corpus.'],
            [],
        )

    retrieval_started_at = perf_counter()
    valid_chunk_ids = list_chunk_ids(connection)
    raw_hits, stale_vector_hits_count = retrieve_corpus_hits(
        question,
        connection=connection,
        valid_chunk_ids=valid_chunk_ids,
        top_k=top_k,
        strategy=strategy,
        vector_store=vector_store,
        embedder=embedder,
        note_ids=note_ids,
    )
    hits = _dedupe_hits(raw_hits)
    stale_limitations = (
        [f'{stale_vector_hits_count} hit(s) vetoriais desatualizados foram descartados por não existirem no SQLite.']
        if stale_vector_hits_count
        else []
    )

    def _with_stale_limitations(limitations: list[str]) -> list[str]:
        return [*limitations, *stale_limitations]

    note_lookup = get_notes_by_id(connection, [hit.chunk.note_id for hit in hits])
    hits = _rerank_hits_by_short_anchor(question, hits, note_lookup)
    used_sources = _summarize_corpus_sources(hits, note_lookup)
    stage_timings.retrieval_ms = _elapsed_ms(retrieval_started_at)

    if not hits:
        return _no_answer(
            'no_retrieval_hits',
            _with_stale_limitations(['Nenhum trecho do corpus contém termos informativos suficientes da pergunta.']),
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
                _with_stale_limitations(['Os hits vetoriais recuperados não apresentam evidência lexical ou score suficiente.']),
                used_sources,
                rejected_hits=hits,
            )

    if strategy == 'hybrid':
        top_hit = hits[0]
        if top_hit.term_coverage < min_hybrid_term_coverage and len(top_hit.matched_terms) < 1:
            return _no_answer(
                'insufficient_hybrid_evidence',
                _with_stale_limitations(['Os hits híbridos recuperados não apresentam evidência lexical suficiente.']),
                used_sources,
                rejected_hits=hits,
            )

    claim_started_at = perf_counter()
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
    stage_timings.claim_build_ms = _elapsed_ms(claim_started_at)

    if not claims or any(not claim.citations for claim in claims):
        return _no_answer(
            'citation_validation_failed',
            _with_stale_limitations(['A evidência foi recuperada, mas não gerou frases extraídas citáveis de forma consistente.']),
            used_sources,
            rejected_hits=hits,
        )

    if strategy in {'vector', 'hybrid'} and grounded_coverage < min_vector_term_coverage:
        if len(grounded_matches) <= 1:
            reason = 'insufficient_vector_specificity' if strategy == 'vector' else 'insufficient_hybrid_specificity'
            return _no_answer(
                reason,
                _with_stale_limitations(['As frases extraídas não trouxeram especificidade textual suficiente.']),
                used_sources,
                rejected_hits=hits,
            )
        return _no_answer(
            'insufficient_grounded_claims',
            _with_stale_limitations(['As frases extraídas não mantiveram ancoragem textual suficiente com a pergunta.']),
            used_sources,
            rejected_hits=hits,
        )

    if strategy in {'vector', 'hybrid'} and named_query_terms:
        _, named_coverage = match_terms_in_text(named_query_terms, grounded_text)
        if named_coverage < 1.0:
            return _no_answer(
                'missing_named_anchor',
                _with_stale_limitations(['A resposta não sustentou os nomes citados na pergunta.']),
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
                _with_stale_limitations(['A resposta recuperada ficou curta e pouco específica para os termos da pergunta.']),
                used_sources,
                rejected_hits=hits,
            )

    cited_sources = _summarize_corpus_sources(_hits_for_citations(hits, citations), note_lookup)
    limitations: list[str] = []
    if any(claim.support_level == 'partial' for claim in claims):
        limitations.append('Parte da resposta depende de evidência parcial recuperada.')
    if len(citations) == 1:
        limitations.append(SINGLE_CHUNK_LIMITATION)
    if len(cited_sources) > 1:
        limitations.append(MULTI_FILE_LIMITATION)

    generated = False
    answer_sources: list[str] = []
    discard_reason: str | None = None
    if answer_provider is not None:
        context_started_at = perf_counter()
        context_items = build_answer_context_items(claims, hits, note_lookup)
        answer_contexts = [context for context, _ in context_items]
        stage_timings.context_build_ms = _elapsed_ms(context_started_at)

        provider_started_at = perf_counter()
        try:
            if on_answer_delta is not None and hasattr(answer_provider, 'answer_stream'):
                generated_answer = answer_provider.answer_stream(question, answer_contexts, on_answer_delta)
            else:
                generated_answer = answer_provider.answer(question, answer_contexts)
        except Exception as exc:
            stage_timings.provider_ms = _elapsed_ms(provider_started_at)
            discard_reason = 'provider_error'
            limitations.append(_provider_failure_limitation(exc))
        else:
            stage_timings.provider_ms = _elapsed_ms(provider_started_at)
            generated_answer = normalize_answer_markers(generated_answer)

            validation_started_at = perf_counter()
            validation = validate_generated_answer(question, generated_answer, answer_contexts, claims)
            stage_timings.validation_ms = _elapsed_ms(validation_started_at)
            if validation.action == 'accept':
                answer = _drop_unknown_answer_markers(generated_answer, len(answer_contexts))
                generated = True
                answer_sources = [chunk_id for _, chunk_id in context_items]
                citations = _with_cited_context_citations(answer, answer_sources, citations, hits, note_lookup)
                cited_sources = _summarize_corpus_sources(_hits_for_citations(hits, citations), note_lookup)
                limitations = _with_source_limitations(limitations, citations, cited_sources)
            elif validation.action == 'no_answer':
                return _no_answer(
                    validation.reason or 'generated_answer_rejected',
                    _with_stale_limitations(validation.limitations),
                    cited_sources,
                    rejected_hits=hits,
                    discard_reason=validation.reason or 'generated_answer_rejected',
                )
            else:
                discard_reason = validation.reason
                limitations.extend(validation.limitations)

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
