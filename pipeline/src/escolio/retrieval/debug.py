import re
from collections.abc import Mapping, Sequence

from escolio.notes.schemas import Note
from escolio.retrieval.models import (
    AskDebug,
    AskDebugHit,
    AskDebugTimings,
    SearchHit,
)


def _short_debug_snippet(text: str, max_length: int = 180) -> str:
    collapsed = re.sub(r'\s+', ' ', text).strip()
    if len(collapsed) <= max_length:
        return collapsed
    return collapsed[: max_length - 3].rstrip() + '...'


def _debug_hit(hit: SearchHit, note_lookup: Mapping[str, Note]) -> AskDebugHit:
    note = note_lookup.get(hit.chunk.note_id)
    return AskDebugHit(
        chunk_id=hit.chunk.chunk_id,
        note_id=hit.chunk.note_id,
        note_version=hit.chunk.note_version,
        source_path=str(note.source_path) if note else None,
        score=hit.score,
        strategy=hit.strategy,
        matched_terms=hit.matched_terms,
        term_coverage=hit.term_coverage,
        distance=hit.distance,
        snippet=_short_debug_snippet(hit.chunk.chunk_text),
    )


def build_ask_debug(
    *,
    strategy: str,
    query_terms: Sequence[str],
    named_query_terms: Sequence[str] = (),
    hits: Sequence[SearchHit] = (),
    rejected_hits: Sequence[SearchHit] = (),
    note_lookup: Mapping[str, Note] | None = None,
    no_answer_reason: str | None = None,
    stale_vector_hits_count: int = 0,
    timings: AskDebugTimings | None = None,
    answer_provider: str | None = None,
    provider_model: str | None = None,
) -> AskDebug:
    lookup = note_lookup or {}
    return AskDebug(
        strategy=strategy,
        query_terms=list(query_terms),
        named_query_terms=list(named_query_terms),
        hits=[_debug_hit(hit, lookup) for hit in hits],
        rejected_hits=[_debug_hit(hit, lookup) for hit in rejected_hits],
        no_answer_reason=no_answer_reason,
        stale_vector_hits_count=stale_vector_hits_count,
        timings=timings,
        answer_provider=answer_provider,
        provider_model=provider_model,
    )
