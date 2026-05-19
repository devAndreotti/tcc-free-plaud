import re
import unicodedata
from time import perf_counter
from typing import Literal

from free_plaud.notes.schemas import Note
from free_plaud.providers.embed import Embedder
from free_plaud.retrieval.indexer import index_note, index_note_in_vector_store
from free_plaud.retrieval.models import AnswerClaim, AskResponse, Citation, SearchHit, UsedSource
from free_plaud.retrieval.search import (
    LOW_SIGNAL_QUERY_TERMS,
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
ADMIN_PREFIX_MARKERS = {
    'anexo',
    'anexoi',
    'anexoii',
    'anexoiii',
    'clausula',
    'objetivo da sessao',
    'decisoes tomadas',
    'discussao',
    'especificacoes tecnicas',
    'matriz de prioridades',
    'infraestrutura',
}
DANGLING_TAIL_TOKENS = {'a', 'as', 'o', 'os', 'da', 'das', 'de', 'do', 'dos', 'e', 'em', 'na', 'nas', 'no', 'nos', 'para', 'por', 'que'}


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
        if _is_heading_like(candidate) and index + 1 < len(base_candidates):
            next_candidate = base_candidates[index + 1]
            if next_candidate and not _is_heading_like(next_candidate):
                candidates.append(f'{candidate} - {next_candidate}')
                continue
        candidates.append(candidate)
    return candidates


def _line_candidates(text: str) -> list[str]:
    cleaned_lines = [_clean_claim_candidate(line) for line in text.splitlines()]
    lines = [line for line in cleaned_lines if line]
    candidates: list[str] = []

    for index, line in enumerate(lines):
        if _is_heading_like(line) and index + 1 < len(lines):
            next_line = lines[index + 1]
            if next_line and not _is_heading_like(next_line):
                candidates.append(f'{line} - {next_line}')
                continue
        candidates.append(line)
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


def _phrase_match_score(question: str, candidate: str) -> tuple[int, int, int]:
    candidate_tokens = _tokenize_for_phrase_match(candidate)
    if not candidate_tokens:
        return 0, 0, -999

    candidate_windows = {
        tuple(candidate_tokens[index : index + size])
        for size in range(2, min(4, len(candidate_tokens)) + 1)
        for index in range(0, len(candidate_tokens) - size + 1)
    }
    longest = 0
    hits = 0
    earliest_index: int | None = None
    for phrase in _query_phrases(question):
        if phrase in candidate_windows:
            longest = max(longest, len(phrase))
            hits += 1
            for index in range(0, len(candidate_tokens) - len(phrase) + 1):
                if tuple(candidate_tokens[index : index + len(phrase)]) == phrase:
                    if earliest_index is None or index < earliest_index:
                        earliest_index = index
                    break
    return longest, hits, -(earliest_index if earliest_index is not None else 999)


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


def _signal_position_bonus(query_terms: list[str], candidate: str) -> int:
    lowered = candidate.lower()
    positions: list[int] = []
    for term in query_terms:
        index = lowered.find(term.lower())
        if index >= 0:
            positions.append(index)
    for match in re.finditer(r'[A-Za-z]+-[A-Za-z0-9.\-]+', candidate):
        positions.append(match.start())
    if not positions:
        return -999
    return -min(positions)


def _embedding_answer_bonus(query_terms: list[str], candidate: str) -> tuple[int, int]:
    normalized_terms = {_normalize_token(term) for term in query_terms}
    if 'embedding' not in normalized_terms and 'modelo' not in normalized_terms:
        return 0, -999

    lowered = candidate.lower()
    positions: list[int] = []
    strength = 0

    model_match = re.search(r'[A-Za-z]+-[A-Za-z0-9.\-]+', candidate)
    if model_match:
        strength += 2
        positions.append(model_match.start())
    chroma_index = lowered.find('chromadb')
    if chroma_index >= 0:
        strength += 1
        positions.append(chroma_index)
    embedding_index = lowered.find('embedding')
    if embedding_index >= 0:
        strength += 1
        positions.append(embedding_index)
    embeddings_index = lowered.find('embeddings')
    if embeddings_index >= 0:
        strength += 1
        positions.append(embeddings_index)

    if not positions:
        return strength, -999
    return strength, -min(positions)


def _normalized_contains(haystack: str, needle: str) -> bool:
    return _normalize_token(needle) in _normalize_token(haystack)


def _claim_query_terms(query_terms: list[str]) -> list[str]:
    informative_terms = [term for term in query_terms if term not in LOW_SIGNAL_QUERY_TERMS]
    return informative_terms or query_terms


def _trim_dangling_tail(candidate: str) -> str:
    cleaned = candidate.strip()
    if cleaned.endswith(('.', '!', '?')):
        return cleaned
    comma_index = cleaned.rfind(',')
    if comma_index >= 0 and (len(cleaned) - comma_index) <= 48:
        truncated = cleaned[:comma_index].strip()
        if truncated:
            cleaned = truncated
    words = cleaned.split()
    while words and _normalize_token(words[-1]) in DANGLING_TAIL_TOKENS:
        words.pop()
    return _collapse_whitespace(' '.join(words)).strip(' -,:;')


def _is_administrative_prefix(candidate: str) -> bool:
    collapsed = _collapse_whitespace(candidate)
    lowered = collapsed.lower()
    if any(_normalized_contains(lowered, marker) for marker in ADMIN_PREFIX_MARKERS):
        return True
    if _is_heading_like(collapsed):
        return True
    if len(collapsed) <= 60 and collapsed == collapsed.upper():
        return True
    return False


def _claim_variant_score(question: str, query_terms: list[str], candidate: str) -> tuple[int, ...] | None:
    matched_terms, term_coverage = match_terms_in_text(_claim_query_terms(query_terms), candidate)
    if not matched_terms:
        return None
    phrase_longest, phrase_hits, phrase_position = _phrase_match_score(question, candidate)
    signal_position = _signal_position_bonus(query_terms, candidate)
    embedding_bonus, embedding_position = _embedding_answer_bonus(query_terms, candidate)
    enumeration_bonus = _enumeration_bonus(question, candidate)
    entity_bonus = _entity_signal_bonus(candidate)
    is_complete = 1 if candidate[-1] in '.!?' else 0
    starts_clean = 1 if candidate[0].isupper() or candidate[0].isdigit() else 0
    noisy_penalty = 1 if _is_noisy_claim(candidate) else 0
    preferred_length = 1 if 24 <= len(candidate) <= 220 else 0
    term_density = int((len(matched_terms) * 1000) / max(len(candidate), 1))
    return (
        phrase_longest,
        phrase_hits,
        phrase_position,
        embedding_bonus,
        embedding_position,
        signal_position,
        enumeration_bonus,
        entity_bonus,
        term_density,
        len(matched_terms),
        int(round(term_coverage * 100)),
        is_complete,
        starts_clean,
        preferred_length,
        -noisy_penalty,
        -len(candidate),
    )


def _trim_claim_span(question: str, query_terms: list[str], claim_text: str) -> str:
    variants: list[str] = []
    seen_variants: set[str] = set()

    def add_variant(text: str) -> None:
        cleaned = _clean_claim_candidate(text)
        if not cleaned or cleaned in seen_variants:
            return
        seen_variants.add(cleaned)
        variants.append(cleaned)

    add_variant(claim_text)

    queue = [claim_text]
    seen_queue: set[str] = {claim_text}
    while queue:
        current = queue.pop(0)
        for separator in (' - ', ': '):
            if separator not in current:
                continue
            prefix, suffix = current.split(separator, 1)
            if _is_administrative_prefix(prefix):
                add_variant(suffix)
                if suffix not in seen_queue:
                    seen_queue.add(suffix)
                    queue.append(suffix)

    window_sizes = (1, 2) if _question_needs_multiple_claims(question) else (1,)

    for base in list(variants):
        parts = [_clean_claim_candidate(part) for part in SENTENCE_SPLIT_PATTERN.split(base)]
        sentences = [part for part in parts if part]
        for start in range(len(sentences)):
            for size in window_sizes:
                window = sentences[start : start + size]
                if len(window) != size:
                    continue
                add_variant(' '.join(window))

    scored: list[tuple[tuple[int, ...], str]] = []
    for variant in variants:
        is_prefixed_administrative = False
        for separator in (' - ', ': '):
            if separator not in variant:
                continue
            prefix, _ = variant.split(separator, 1)
            if _is_administrative_prefix(prefix):
                is_prefixed_administrative = True
                break
        if is_prefixed_administrative:
            continue
        score = _claim_variant_score(question, query_terms, variant)
        if score is None:
            continue
        scored.append((score, variant))

    if not scored:
        return claim_text

    scored.sort(key=lambda item: item[0], reverse=True)
    return _trim_dangling_tail(scored[0][1])


def _question_needs_multiple_claims(question: str) -> bool:
    lowered = _collapse_whitespace(question.lower())
    clause_count = len(
        re.findall(r'(^|(?:\se\s+|[,;]\s*))(?:(?:qual|quais|como|onde|quando|quem|porque)\b)', lowered)
    )
    if clause_count >= 2:
        return True
    return any(marker in lowered for marker in (' e qual ', ' e quais ', ', qual ', ', quais '))


def _rank_claim_candidates(chunk_text: str, question: str, query_terms: list[str]) -> list[tuple[tuple[int, ...], str]]:
    candidate_query_terms = _claim_query_terms(query_terms)
    sentence_candidates = _sentence_candidates(chunk_text)
    line_candidates = _line_candidates(chunk_text)
    candidates = list(dict.fromkeys([*sentence_candidates, *line_candidates]))
    if not candidates:
        return []

    scored: list[tuple[tuple[int, ...], str]] = []
    for index, candidate in enumerate(candidates):
        matched_terms, term_coverage = match_terms_in_text(candidate_query_terms, candidate)
        matches = len(matched_terms)
        if matches <= 0 and not candidate.endswith('?'):
            continue
        variants = [(candidate, matches, term_coverage)]
        if candidate.endswith('?') and matches > 0 and index + 1 < len(candidates):
            next_candidate = candidates[index + 1]
            if next_candidate and not _is_heading_like(next_candidate):
                next_matches, next_coverage = match_terms_in_text(candidate_query_terms, next_candidate)
                variants.append((next_candidate, max(matches, len(next_matches)), max(term_coverage, next_coverage)))

        for variant_text, variant_matches, variant_coverage in variants:
            if variant_matches <= 0:
                continue
            phrase_longest, phrase_hits, phrase_position = _phrase_match_score(question, variant_text)
            signal_position = _signal_position_bonus(query_terms, variant_text)
            embedding_bonus, embedding_position = _embedding_answer_bonus(query_terms, variant_text)
            enumeration_bonus = _enumeration_bonus(question, variant_text)
            entity_bonus = _entity_signal_bonus(variant_text)
            is_complete = 1 if variant_text[-1] in '.!?' else 0
            preferred_length = 1 if 40 <= len(variant_text) <= 260 else 0
            starts_clean = 1 if variant_text[0].isupper() or variant_text[0].isdigit() else 0
            noisy_penalty = 1 if _is_noisy_claim(variant_text) else 0
            line_count = min(variant_text.count(' - ') + variant_text.count('\n') + 1, 3)
            term_density = int((variant_matches * 1000) / max(len(variant_text), 1))
            score_key = (
                phrase_longest,
                phrase_hits,
                phrase_position,
                embedding_bonus,
                embedding_position,
                signal_position,
                term_density,
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
    covered_terms: set[str] = set()
    candidate_rows: list[tuple[tuple[int, ...], SearchHit, str]] = []

    for hit_index, hit in enumerate(hits[: max(max_claims, 1) * 2]):
        ranked_candidates = _rank_claim_candidates(hit.chunk.chunk_text, question, query_terms)
        for candidate_index, (score_key, claim_text) in enumerate(ranked_candidates[:3]):
            candidate_rows.append(((*score_key, -hit_index, -candidate_index), hit, claim_text))

    for _, hit, claim_text in sorted(candidate_rows, key=lambda item: item[0], reverse=True):
        trimmed_claim = _trim_claim_span(question, query_terms, claim_text)
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

    effective_max_claims = max(1, min(max_claims, top_k))
    if not _question_needs_multiple_claims(question):
        effective_max_claims = 1

    claims = _build_claims(note, question, hits, query_terms, max_claims=effective_max_claims)
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
