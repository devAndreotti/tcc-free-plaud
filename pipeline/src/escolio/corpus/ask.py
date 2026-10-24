import re
import sqlite3
from collections.abc import Callable
from time import perf_counter
from typing import Literal

from escolio.corpus.answer_context import (
    build_answer_context_items,
    citation_snippet,
    normalize_answer_markers,
)
from escolio.corpus.ask_validation import (  # noqa: F401 (GeneratedAnswerValidation reexportado)
    GeneratedAnswerValidation,
    validate_generated_answer,
)
from escolio.notes.schemas import Note
from escolio.providers.answer import AnswerProvider, AnswerProviderError
from escolio.providers.answer_quality import (
    ANSWER_MARKER_PATTERN,
    contains_token_sequence,
)
from escolio.providers.embed import Embedder
from escolio.retrieval.debug import build_ask_debug
from escolio.retrieval.models import (
    AnswerClaim,
    AskDebug,
    AskDebugTimings,
    AskResponse,
    Chunk,
    Citation,
    SearchHit,
    UsedSource,
)
from escolio.retrieval.rag import (
    _build_no_answer,
    _dedupe_hits,
    _flatten_citations,
    _is_question_like,
    _question_needs_multiple_claims,
    _rank_claim_candidates,
    _support_level,
    _trim_claim_span,
)
from escolio.retrieval.search import (
    STOPWORDS,
    TOKEN_PATTERN,
    _stem_like,
    extract_named_query_terms,
    fuse_hits_by_rank,
    lexical_search_hits,
    match_terms_in_text,
    normalize_query_terms,
    open_semantic_search,
    terms_missing_from_vocabulary,
)
from escolio.storage.sqlite import (
    count_chunks,
    ensure_chunks_fts_current,
    get_notes_by_id,
    list_chunk_ids,
    list_chunks,
    list_fts_vocabulary,
    note_ids_under_root,
    search_chunks_fts,
)
from escolio.storage.vector import LocalVectorStore

RetrievalStrategy = Literal['lexical', 'vector', 'hybrid']

# Radicais do vocabulário do corpus, por (arquivo, chunks no FTS, último rowid): muda a cada indexação.
_VOCABULARY_STEMS: dict[tuple[str, int, int], frozenset[str]] = {}


def _vocabulary_key(connection: sqlite3.Connection) -> tuple[str, int, int]:
    # Consultas baratas: COUNT(*) no FTS varre a tabela (~40 ms com 4 mil chunks); o maior rowid
    # do FTS muda a cada chunk gravado.
    path = str(connection.execute('PRAGMA database_list').fetchone()[2])
    last_rowid = connection.execute('SELECT MAX(rowid) FROM chunks_fts').fetchone()[0]
    return path, count_chunks(connection), int(last_rowid or 0)


def corpus_vocabulary_stems(connection: sqlite3.Connection) -> frozenset[str] | None:
    """Radicais das palavras do corpus, em cache até a próxima indexação (~1 s com 4 mil chunks)."""
    try:
        key = _vocabulary_key(connection)
        if key[0] and key in _VOCABULARY_STEMS:
            return _VOCABULARY_STEMS[key]
        if ensure_chunks_fts_current(connection) == 'rebuilt':
            key = _vocabulary_key(connection)
        stems = frozenset(_stem_like(term) for term in list_fts_vocabulary(connection))
    except sqlite3.OperationalError:
        return None  # sem FTS, a pergunta segue sem este filtro
    if key[0]:  # banco em memória não tem caminho estável para servir de chave
        _VOCABULARY_STEMS.clear()  # ponytail: um corpus por vez; o app e o benchmark alternam pouco
        _VOCABULARY_STEMS[key] = stems
    return stems
TEAM_ANSWER_PATTERN = re.compile(r'\bequipe\s+(?:de|da|do|dos|das)\s+[0-9A-Za-zÀ-ÖØ-öø-ÿ_-]+')
SHORT_ANCHOR_MAX_LENGTH = 3
SHORT_ANCHOR_EXACT_BOOST = 1.0
SHORT_ANCHOR_TAIL_BOOST = 0.6
SHORT_ANCHOR_CONFLICT_PENALTY = 0.8


def _provider_failure_limitation(exc: Exception) -> str:
    detail = str(exc)[:200].rstrip('.') if isinstance(exc, AnswerProviderError) else type(exc).__name__
    return f'A IA falhou; usando resposta extrativa. Erro: {detail}.'


def _citation_from_corpus_hit(hit: SearchHit, note_lookup: dict[str, Note], claim_text: str | None = None) -> Citation:
    chunk = hit.chunk
    note = note_lookup.get(chunk.note_id)
    return Citation(
        note_id=chunk.note_id,
        note_version=chunk.note_version,
        chunk_id=chunk.chunk_id,
        snippet=citation_snippet(chunk.chunk_text, claim_text),
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


SINGLE_CHUNK_LIMITATION = 'A resposta se apoia em um único trecho recuperado.'
MULTI_FILE_LIMITATION = 'A resposta combina evidência de múltiplos arquivos do corpus.'


def _with_cited_context_citations(
    answer: str,
    answer_sources: list[str],
    citations: list[Citation],
    hits: list[SearchHit],
    note_lookup: dict[str, Note],
) -> list[Citation]:
    """Acrescenta a citação dos trechos que a resposta gerada cita com [n] e que os claims não trouxeram."""
    cited_ids = {
        answer_sources[int(match.group(1)) - 1]
        for match in ANSWER_MARKER_PATTERN.finditer(answer)
        if 1 <= int(match.group(1)) <= len(answer_sources)
    }
    known_ids = {citation.chunk_id for citation in citations}
    extra = [
        _citation_from_corpus_hit(hit, note_lookup)
        for hit in hits
        if hit.chunk.chunk_id in cited_ids and hit.chunk.chunk_id not in known_ids
    ]
    return [*citations, *extra]


def _with_source_limitations(
    limitations: list[str],
    citations: list[Citation],
    cited_sources: list[UsedSource],
) -> list[str]:
    kept = [line for line in limitations if line not in {SINGLE_CHUNK_LIMITATION, MULTI_FILE_LIMITATION}]
    if len(citations) == 1:
        kept.append(SINGLE_CHUNK_LIMITATION)
    if len(cited_sources) > 1:
        kept.append(MULTI_FILE_LIMITATION)
    return kept


def _drop_unknown_answer_markers(text: str, context_count: int) -> str:
    """Mantém [n] só para contextos que existem; marcador inventado some sem derrubar a resposta."""
    return ANSWER_MARKER_PATTERN.sub(
        lambda match: match.group() if 1 <= int(match.group(1)) <= context_count else '',
        text,
    )


def _normalized_anchor_tokens(text: str) -> list[str]:
    return [token.casefold() for token in TOKEN_PATTERN.findall(text)]


def _has_conflicting_short_anchor(tokens: list[str], prefix: list[str], expected_anchor: str) -> bool:
    if not prefix:
        return False
    width = len(prefix) + 1
    for index in range(len(tokens) - width + 1):
        if tokens[index : index + len(prefix)] != prefix:
            continue
        candidate = tokens[index + len(prefix)]
        if (
            candidate != expected_anchor
            and 0 < len(candidate) <= SHORT_ANCHOR_MAX_LENGTH
            and candidate not in STOPWORDS
        ):
            return True
    return False


def _short_anchor_sequences(question: str) -> list[list[str]]:
    tokens = TOKEN_PATTERN.findall(question)
    normalized = [token.casefold() for token in tokens]
    sequences: list[list[str]] = []
    for index, token in enumerate(tokens):
        anchor = token.casefold()
        if len(anchor) > SHORT_ANCHOR_MAX_LENGTH or anchor in STOPWORDS:
            continue
        if not (token.isupper() or any(char.isdigit() for char in token)):
            continue

        previous_terms = [
            normalized[item]
            for item in range(max(0, index - 2), index)
            if len(normalized[item]) >= 4 and normalized[item] not in STOPWORDS
        ]
        if not previous_terms:
            continue

        for width in range(1, len(previous_terms) + 1):
            sequence = [*previous_terms[-width:], anchor]
            if sequence not in sequences:
                sequences.append(sequence)
    return sequences


def _anchor_evidence_tokens(hit: SearchHit, note: Note | None) -> list[str]:
    parts = [hit.chunk.note_id, hit.chunk.chunk_text]
    if note is not None:
        parts.extend([note.title, note.source_name, str(note.source_path)])
    return _normalized_anchor_tokens('\n'.join(part for part in parts if part))


def _short_anchor_score_delta(question: str, hit: SearchHit, note: Note | None) -> float:
    sequences = _short_anchor_sequences(question)
    if not sequences:
        return 0.0

    evidence_tokens = _anchor_evidence_tokens(hit, note)
    delta = 0.0
    for sequence in sequences:
        if contains_token_sequence(evidence_tokens, sequence):
            delta += SHORT_ANCHOR_EXACT_BOOST
        elif len(sequence) > 2 and contains_token_sequence(evidence_tokens, sequence[-2:]):
            delta += SHORT_ANCHOR_TAIL_BOOST

        if _has_conflicting_short_anchor(evidence_tokens, sequence[:-1], sequence[-1]):
            delta -= SHORT_ANCHOR_CONFLICT_PENALTY
    return delta


def _rerank_hits_by_short_anchor(question: str, hits: list[SearchHit], note_lookup: dict[str, Note]) -> list[SearchHit]:
    if not hits or not _short_anchor_sequences(question):
        return hits

    ranked_rows: list[tuple[float, float, int, int, SearchHit]] = []
    for original_index, hit in enumerate(hits):
        note = note_lookup.get(hit.chunk.note_id)
        delta = _short_anchor_score_delta(question, hit, note)
        reranked_hit = hit.model_copy(update={'score': hit.score + delta}) if delta else hit
        ranked_rows.append(
            (reranked_hit.score, reranked_hit.term_coverage, len(reranked_hit.matched_terms), original_index, reranked_hit)
        )

    return [
        row[-1]
        for row in sorted(
            ranked_rows,
            key=lambda item: (-item[0], -item[1], -item[2], item[3]),
        )
    ]


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
    note_ids: frozenset[str] | None = None,
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
            note_ids=note_ids,
        )
    except sqlite3.OperationalError:
        return lexical_search_hits(query, _chunks_in_scope(connection, note_ids), top_k=top_k)

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
    return lexical_search_hits(query, _chunks_in_scope(connection, note_ids), top_k=top_k)


def _chunks_in_scope(connection: sqlite3.Connection, note_ids: frozenset[str] | None) -> list[Chunk]:
    chunks = list_chunks(connection)
    if note_ids is None:
        return chunks
    return [chunk for chunk in chunks if chunk.note_id in note_ids]


def _trim_claim_preserving_query_terms(question: str, query_terms: list[str], claim_text: str) -> str:
    trimmed = _trim_claim_span(question, query_terms, claim_text)
    original_matches = set(match_terms_in_text(query_terms, claim_text)[0])
    trimmed_matches = set(match_terms_in_text(query_terms, trimmed)[0])
    lost_matches = original_matches - trimmed_matches
    if lost_matches and len(claim_text) <= 260:
        return claim_text.strip(' -,:;')
    lowered_question = question.lower()
    team_answer = TEAM_ANSWER_PATTERN.search(claim_text)
    if (
        team_answer
        and ('equipe' in lowered_question or 'responsavel' in lowered_question)
        and team_answer.group(0) not in trimmed
    ):
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
                citations=[_citation_from_corpus_hit(hit, note_lookup, trimmed_claim)],
                support_level=_support_level(hit, query_terms),
            )
        )
        if len(claims) >= max_claims:
            break

    return claims


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
    # O escopo entra na consulta (FTS: IN; Chroma: $in), então a pasta nunca fica sem candidatos por pool curto.
    if strategy == 'lexical':
        return fts_lexical_search_hits(connection, question, top_k=top_k, note_ids=note_ids), 0

    if vector_store is None or embedder is None:
        raise ValueError('Vector store e embedder sao obrigatorios para strategy=vector e strategy=hybrid.')

    candidate_pool_size = max(top_k * 8, 24)
    if strategy == 'vector':
        vector_hits = open_semantic_search(question, vector_store, embedder, top_k=candidate_pool_size, note_ids=note_ids)
        filtered_hits, stale_count = _filter_hits_to_persisted_chunks(vector_hits, valid_chunk_ids)
        return filtered_hits[:top_k], stale_count

    if strategy == 'hybrid':
        lexical_hits = fts_lexical_search_hits(
            connection,
            question,
            top_k=max(top_k * 3, top_k),
            note_ids=note_ids,
        )
        vector_hits = open_semantic_search(question, vector_store, embedder, top_k=candidate_pool_size, note_ids=note_ids)
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
