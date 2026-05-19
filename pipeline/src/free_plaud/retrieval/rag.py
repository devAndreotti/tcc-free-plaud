import re
import unicodedata
from time import perf_counter
from typing import Literal

from free_plaud.notes.schemas import Note
from free_plaud.providers.embed import Embedder
from free_plaud.retrieval.indexer import index_note, index_note_in_vector_store
from free_plaud.retrieval.models import AnswerClaim, AskResponse, Citation, SearchHit, UsedSource
from free_plaud.retrieval.search import (
    extract_named_query_terms,
    hybrid_search,
    lexical_search_hits,
    match_terms_in_text,
    normalize_query_terms,
    semantic_search,
)
from free_plaud.storage.vector import LocalVectorStore

SENTENCE_SPLIT_PATTERN = re.compile(r'(?<=[.!?])\s+|\n+')
QUERY_TOKEN_PATTERN = re.compile(r"[0-9A-Za-zÀ-ÖØ-öø-ÿ_]+", re.UNICODE)
LEADING_INTERROGATIVES = {'qual', 'quais', 'como', 'onde', 'quando', 'quem', 'porque', 'por', 'que', 'o'}


def _collapse_whitespace(text: str) -> str:
    return re.sub(r'\s+', ' ', text).strip()


def _clean_claim_candidate(text: str) -> str:
    cleaned = text.replace('---', ' ')
    cleaned = re.sub(r'^[#>*`\-\s|]+', '', cleaned)
    cleaned = re.sub(r'[`*_]+', '', cleaned)
    cleaned = cleaned.strip(' -|:')
    return _collapse_whitespace(cleaned)


def _normalize_token(text: str) -> str:
    normalized = unicodedata.normalize('NFKD', text)
    ascii_only = normalized.encode('ascii', 'ignore').decode('ascii')
    return re.sub(r'[^0-9a-z]+', '', ascii_only.lower())


def _tokenize_for_phrase_match(text: str) -> list[str]:
    return [token for token in (_normalize_token(part) for part in QUERY_TOKEN_PATTERN.findall(text)) if token]


def _is_heading_like(candidate: str) -> bool:
    stripped = candidate.strip()
    if not stripped:
        return False
    if stripped.startswith('#'):
        return True
    words = stripped.split()
    return len(words) <= 6 and stripped.upper() == stripped


def _is_question_like(candidate: str) -> bool:
    stripped = candidate.strip().lstrip("\"'“”‘’").strip()
    lowered = stripped.lower()
    if stripped.endswith('?'):
        return True
    return len(stripped) < 80 and lowered.startswith(
        ('qual ', 'quais ', 'como ', 'o que ', 'por que ', 'quando ', 'onde ', 'quem ')
    )


def _is_noisy_claim(candidate: str) -> bool:
    if not candidate:
        return True
    if len(candidate) < 24:
        return True
    if _is_question_like(candidate):
        return True
    if candidate.count('|') >= 2:
        return True
    if _is_heading_like(candidate):
        return True
    return candidate[0].islower()


def _shorten_snippet(text: str, max_length: int = 220) -> str:
    collapsed = _collapse_whitespace(text)
    if len(collapsed) <= max_length:
        return collapsed
    return collapsed[: max_length - 3].rstrip() + '...'


def _sentence_candidates(text: str) -> list[str]:
    raw_parts = [_clean_claim_candidate(part) for part in SENTENCE_SPLIT_PATTERN.split(text)]
    base_candidates = [candidate for candidate in raw_parts if candidate]
    candidates: list[str] = []
    for index, candidate in enumerate(base_candidates):
        candidates.append(candidate)
        if _is_heading_like(candidate) and index + 1 < len(base_candidates):
            next_candidate = base_candidates[index + 1]
            if next_candidate and not _is_heading_like(next_candidate):
                candidates.append(f'{candidate} - {next_candidate}')
    return candidates


def _line_candidates(text: str) -> list[str]:
    cleaned_lines = [_clean_claim_candidate(line) for line in text.splitlines()]
    lines = [line for line in cleaned_lines if line]
    candidates: list[str] = []

    for index, line in enumerate(lines):
        candidates.append(line)
        if _is_heading_like(line) and index + 1 < len(lines):
            next_line = lines[index + 1]
            if next_line and not _is_heading_like(next_line):
                candidates.append(f'{line} - {next_line}')
        if index + 1 < len(lines):
            next_line = lines[index + 1]
            if not _is_heading_like(line) and not _is_heading_like(next_line):
                candidates.append(f'{line} {next_line}')
        if index + 2 < len(lines):
            next_line = lines[index + 1]
            third_line = lines[index + 2]
            if not any(_is_heading_like(candidate) for candidate in (line, next_line, third_line)):
                candidates.append(f'{line} {next_line} {third_line}')

    return candidates


def _query_phrases(question: str) -> list[tuple[str, ...]]:
    tokens = _tokenize_for_phrase_match(question)
    while tokens and tokens[0] in LEADING_INTERROGATIVES:
        tokens = tokens[1:]

    phrases: list[tuple[str, ...]] = []
    seen: set[tuple[str, ...]] = set()
    for size in range(4, 1, -1):
        for index in range(0, max(len(tokens) - size + 1, 0)):
            phrase = tuple(tokens[index : index + size])
            if phrase in seen:
                continue
            if sum(1 for token in phrase if len(token) >= 3) < 2:
                continue
            seen.add(phrase)
            phrases.append(phrase)
    return phrases


def _phrase_match_score(question: str, candidate: str) -> tuple[int, int]:
    candidate_tokens = _tokenize_for_phrase_match(candidate)
    if not candidate_tokens:
        return 0, 0

    candidate_windows = {
        tuple(candidate_tokens[index : index + size])
        for size in range(2, min(4, len(candidate_tokens)) + 1)
        for index in range(0, len(candidate_tokens) - size + 1)
    }
    longest = 0
    hits = 0
    for phrase in _query_phrases(question):
        if phrase in candidate_windows:
            longest = max(longest, len(phrase))
            hits += 1
    return longest, hits


def _enumeration_bonus(question: str, candidate: str) -> int:
    if not question.lower().startswith('quais'):
        return 0
    lowered = candidate.lower()
    bonus = 0
    if ' e ' in lowered:
        bonus += 1
    if candidate.count('(') >= 2:
        bonus += 1
    if len(re.findall(r'(?:^|\s)-\s+\S', candidate)) >= 2:
        bonus += 1
    return bonus


def _entity_signal_bonus(candidate: str) -> int:
    bonus = 0
    if '`' in candidate:
        bonus += 2
    if re.search(r'[A-Za-z]+-[A-Za-z0-9.\-]+', candidate):
        bonus += 1
    if re.search(r'\([^)]*[A-Za-z][^)]*\)', candidate):
        bonus += 1
    return bonus


def _rank_claim_candidates(chunk_text: str, question: str, query_terms: list[str]) -> list[tuple[tuple[int, ...], str]]:
    sentence_candidates = _sentence_candidates(chunk_text)
    line_candidates = _line_candidates(chunk_text)
    candidates = list(dict.fromkeys([*sentence_candidates, *line_candidates]))
    if not candidates:
        return []

    scored: list[tuple[tuple[int, ...], str]] = []
    for index, candidate in enumerate(candidates):
        matched_terms, term_coverage = match_terms_in_text(query_terms, candidate)
        matches = len(matched_terms)
        if matches <= 0 and not candidate.endswith('?'):
            continue
        variants = [(candidate, matches, term_coverage)]
        if candidate.endswith('?') and matches > 0 and index + 1 < len(candidates):
            next_candidate = candidates[index + 1]
            if next_candidate and not _is_heading_like(next_candidate):
                next_matches, next_coverage = match_terms_in_text(query_terms, next_candidate)
                variants.append((next_candidate, max(matches, len(next_matches)), max(term_coverage, next_coverage)))

        for variant_text, variant_matches, variant_coverage in variants:
            if variant_matches <= 0:
                continue
            phrase_longest, phrase_hits = _phrase_match_score(question, variant_text)
            enumeration_bonus = _enumeration_bonus(question, variant_text)
            entity_bonus = _entity_signal_bonus(variant_text)
            is_complete = 1 if variant_text[-1] in '.!?' else 0
            preferred_length = 1 if 40 <= len(variant_text) <= 260 else 0
            starts_clean = 1 if variant_text[0].isupper() or variant_text[0].isdigit() else 0
            noisy_penalty = 1 if _is_noisy_claim(variant_text) else 0
            line_count = min(variant_text.count(' - ') + variant_text.count('\n') + 1, 3)
            score_key = (
                phrase_longest,
                phrase_hits,
                variant_matches,
                int(round(variant_coverage * 100)),
                enumeration_bonus,
                entity_bonus,
                line_count,
                preferred_length,
                starts_clean,
                is_complete,
                -noisy_penalty,
                -len(variant_text),
            )
            scored.append((score_key, variant_text))

    return sorted(scored, key=lambda item: item[0], reverse=True)


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
    if hit.term_coverage >= 0.6 or len(hit.matched_terms) >= min(2, len(query_terms)) or hit.score >= 0.7:
        return 'direct'
    return 'partial'


def _chunk_overlap_ratio(left: SearchHit, right: SearchHit) -> float:
    if left.chunk.note_id != right.chunk.note_id:
        return 0.0
    overlap = max(0, min(left.chunk.char_end, right.chunk.char_end) - max(left.chunk.char_start, right.chunk.char_start))
    if overlap <= 0:
        return 0.0
    left_size = max(left.chunk.char_end - left.chunk.char_start, 1)
    right_size = max(right.chunk.char_end - right.chunk.char_start, 1)
    return overlap / min(left_size, right_size)


def _dedupe_hits(hits: list[SearchHit], *, max_overlap_ratio: float = 0.65) -> list[SearchHit]:
    deduped: list[SearchHit] = []
    for hit in hits:
        if any(
            hit.chunk.chunk_id == existing.chunk.chunk_id or _chunk_overlap_ratio(hit, existing) >= max_overlap_ratio
            for existing in deduped
        ):
            continue
        deduped.append(hit)
    return deduped


def _build_claims(
    note: Note,
    question: str,
    hits: list[SearchHit],
    query_terms: list[str],
    *,
    max_claims: int,
) -> list[AnswerClaim]:
    claims: list[AnswerClaim] = []
    seen_texts: set[str] = set()
    seen_chunk_ids: set[str] = set()
    candidate_rows: list[tuple[tuple[int, ...], SearchHit, str]] = []

    for hit_index, hit in enumerate(hits[: max(max_claims, 1) * 2]):
        ranked_candidates = _rank_claim_candidates(hit.chunk.chunk_text, question, query_terms)
        for candidate_index, (score_key, claim_text) in enumerate(ranked_candidates[:3]):
            candidate_rows.append(((*score_key, -hit_index, -candidate_index), hit, claim_text))

    for _, hit, claim_text in sorted(candidate_rows, key=lambda item: item[0], reverse=True):
        normalized = claim_text.lower()
        if (
            not claim_text
            or _is_question_like(claim_text)
            or normalized in seen_texts
            or hit.chunk.chunk_id in seen_chunk_ids
        ):
            continue
        seen_texts.add(normalized)
        seen_chunk_ids.add(hit.chunk.chunk_id)
        claims.append(
            AnswerClaim(
                text=claim_text,
                citations=[_citation_from_hit(note, hit)],
                support_level=_support_level(hit, query_terms),
            )
        )
        if len(claims) >= max_claims:
            break
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


def _retrieve_hits(
    note: Note,
    question: str,
    *,
    top_k: int,
    strategy: Literal['lexical', 'vector', 'hybrid'],
    vector_store: LocalVectorStore | None,
    embedder: Embedder | None,
) -> list[SearchHit]:
    if strategy == 'lexical':
        chunks = index_note(note)
        return lexical_search_hits(question, chunks, top_k=top_k)

    if strategy not in {'vector', 'hybrid'}:
        raise ValueError("strategy deve ser 'lexical', 'vector' ou 'hybrid'.")

    if vector_store is None or embedder is None:
        raise ValueError('Vector store e embedder sao obrigatorios para strategy=vector e strategy=hybrid.')

    chunks = index_note_in_vector_store(note, vector_store, embedder)
    candidate_pool_size = max(top_k * 8, 24)

    if strategy == 'vector':
        hits = semantic_search(
            question,
            vector_store,
            embedder,
            top_k=candidate_pool_size,
            note_id=note.note_id,
        )
        reranked = sorted(
            hits,
            key=lambda item: (-item.term_coverage, -len(item.matched_terms), -item.score, item.chunk.chunk_index),
        )
        return reranked[:top_k]

    return hybrid_search(
        question,
        chunks,
        vector_store,
        embedder,
        top_k=top_k,
        note_id=note.note_id,
        lexical_pool_size=max(top_k * 3, top_k),
        vector_pool_size=candidate_pool_size,
    )


def answer_with_citations(
    note: Note,
    question: str,
    top_k: int = 3,
    *,
    strategy: Literal['lexical', 'vector', 'hybrid'] = 'lexical',
    vector_store: LocalVectorStore | None = None,
    embedder: Embedder | None = None,
    min_term_coverage: float = 0.4,
    min_vector_score: float = 0.55,
    min_vector_term_coverage: float = 0.2,
    min_hybrid_term_coverage: float = 0.2,
    max_claims: int = 2,
) -> AskResponse:
    """Responde apenas quando há evidência recuperada suficiente e citável."""
    started_at = perf_counter()
    query_terms = normalize_query_terms(question)
    named_query_terms = extract_named_query_terms(question)
    if not query_terms:
        return _build_no_answer(
            question=question,
            reason='query_without_content',
            limitations=['A pergunta não contém termos informativos suficientes para recuperação.'],
            used_sources=[],
            latency_ms=int((perf_counter() - started_at) * 1000),
        )

    hits = _retrieve_hits(
        note,
        question,
        top_k=top_k,
        strategy=strategy,
        vector_store=vector_store,
        embedder=embedder,
    )
    hits = _dedupe_hits(hits)
    used_sources = _summarize_sources(note, hits)

    if not hits:
        return _build_no_answer(
            question=question,
            reason='no_retrieval_hits',
            limitations=['Nenhum chunk recuperado contém termos informativos suficientes da pergunta.'],
            used_sources=used_sources,
            latency_ms=int((perf_counter() - started_at) * 1000),
        )

    if strategy == 'lexical' and hits[0].term_coverage < min_term_coverage:
        return _build_no_answer(
            question=question,
            reason='insufficient_term_coverage',
            limitations=['Os trechos recuperados compartilham poucos termos informativos com a pergunta.'],
            used_sources=used_sources,
            latency_ms=int((perf_counter() - started_at) * 1000),
        )

    if strategy == 'vector':
        top_hit = hits[0]
        if top_hit.score < min_vector_score or top_hit.term_coverage < min_vector_term_coverage:
            return _build_no_answer(
                question=question,
                reason='insufficient_vector_evidence',
                limitations=['Os hits vetoriais recuperados nao apresentam evidencia lexical ou score suficiente para responder.'],
                used_sources=used_sources,
                latency_ms=int((perf_counter() - started_at) * 1000),
            )

    if strategy == 'hybrid':
        top_hit = hits[0]
        if top_hit.term_coverage < min_hybrid_term_coverage and len(top_hit.matched_terms) < 1:
            return _build_no_answer(
                question=question,
                reason='insufficient_hybrid_evidence',
                limitations=['Os hits hibridos recuperados nao apresentam evidencia lexical suficiente para responder com seguranca.'],
                used_sources=used_sources,
                latency_ms=int((perf_counter() - started_at) * 1000),
            )

    claims = _build_claims(note, question, hits, query_terms, max_claims=max(1, min(max_claims, top_k)))
    citations = _flatten_citations(claims)
    grounded_text = ' '.join(claim.text for claim in claims)
    _, grounded_coverage = match_terms_in_text(query_terms, grounded_text)

    if not claims or any(not claim.citations for claim in claims):
        return _build_no_answer(
            question=question,
            reason='citation_validation_failed',
            limitations=['A evidência foi recuperada, mas não gerou claims citáveis de forma consistente.'],
            used_sources=used_sources,
            latency_ms=int((perf_counter() - started_at) * 1000),
        )

    if strategy in {'vector', 'hybrid'} and grounded_coverage < min_vector_term_coverage:
        return _build_no_answer(
            question=question,
            reason='insufficient_grounded_claims',
            limitations=['Os claims gerados nao mantiveram ancoragem textual suficiente com a pergunta.'],
            used_sources=used_sources,
            latency_ms=int((perf_counter() - started_at) * 1000),
        )

    if strategy in {'vector', 'hybrid'} and named_query_terms:
        _, named_coverage = match_terms_in_text(named_query_terms, grounded_text)
        if named_coverage < 1.0:
            return _build_no_answer(
                question=question,
                reason='missing_named_anchor',
                limitations=['A resposta nao sustentou os anchors nomeados presentes na pergunta.'],
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
                limitations=[
                    'A resposta vetorial recuperada ficou curta e pouco especifica para os termos da pergunta.'
                    if strategy == 'vector'
                    else 'A resposta hibrida recuperada ficou curta e pouco especifica para os termos da pergunta.'
                ],
                used_sources=used_sources,
                latency_ms=int((perf_counter() - started_at) * 1000),
            )

    limitations: list[str] = []
    if any(claim.support_level == 'partial' for claim in claims):
        limitations.append(
            'Parte da resposta depende de evidencia parcial recuperada por '
            + (
                'busca vetorial.'
                if strategy == 'vector'
                else 'busca hibrida.'
                if strategy == 'hybrid'
                else 'busca lexical.'
            )
        )
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
