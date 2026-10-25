import re

from escolio.corpus.answer_context import citation_snippet
from escolio.notes.schemas import Note
from escolio.providers.answer_quality import ANSWER_MARKER_PATTERN
from escolio.retrieval.models import AnswerClaim, Citation, SearchHit, UsedSource
from escolio.retrieval.rag import (
    _is_question_like,
    _question_needs_multiple_claims,
    _rank_claim_candidates,
    _support_level,
    _trim_claim_span,
)
from escolio.retrieval.search import match_terms_in_text

TEAM_ANSWER_PATTERN = re.compile(r'\bequipe\s+(?:de|da|do|dos|das)\s+[0-9A-Za-zÀ-ÖØ-öø-ÿ_-]+')


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


def build_claims_for_answer(
    question: str,
    hits: list[SearchHit],
    query_terms: list[str],
    note_lookup: dict[str, Note],
    *,
    top_k: int,
    max_claims: int,
) -> list[AnswerClaim]:
    """Monta os claims da resposta extrativa; a pergunta sem pedido de vários pontos fica com um claim só."""
    effective_max_claims = max(1, min(max_claims, top_k))
    if not _question_needs_multiple_claims(question):
        effective_max_claims = 1
    return _build_corpus_claims(question, hits, query_terms, note_lookup, max_claims=effective_max_claims)


def answer_limitations(claims: list[AnswerClaim], citations: list[Citation], cited_sources: list[UsedSource]) -> list[str]:
    """Limitações da resposta extrativa, conforme o suporte dos claims e a quantidade de trechos e arquivos citados."""
    limitations: list[str] = []
    if any(claim.support_level == 'partial' for claim in claims):
        limitations.append('Parte da resposta depende de evidência parcial recuperada.')
    if len(citations) == 1:
        limitations.append(SINGLE_CHUNK_LIMITATION)
    if len(cited_sources) > 1:
        limitations.append(MULTI_FILE_LIMITATION)
    return limitations
