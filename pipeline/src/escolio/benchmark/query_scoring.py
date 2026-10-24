"""Pontuação de uma consulta: relevância do trecho, ranking e payload dos hits recuperados."""

from escolio.benchmark.datasets import BenchmarkSample
from escolio.benchmark.runner_models import BenchmarkQueryResult
from escolio.retrieval.models import Chunk, SearchHit


def _contains_expected_terms(text: str, expected_terms: list[str]) -> bool:
    if not expected_terms:
        return True
    lowered = text.lower()
    return all(term.lower() in lowered for term in expected_terms)


def _is_relevant(sample: BenchmarkSample, chunk: Chunk) -> bool:
    if sample.expected_chunk_id:
        return chunk.chunk_id == sample.expected_chunk_id
    if sample.expected_note_id and chunk.note_id != sample.expected_note_id:
        return False
    return _contains_expected_terms(chunk.chunk_text, sample.expected_terms)


def _retrieved_payload(hits: list[SearchHit]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for rank, hit in enumerate(hits, start=1):
        rows.append(
            {
                'rank': rank,
                'chunk_id': hit.chunk.chunk_id,
                'note_id': hit.chunk.note_id,
                'score': hit.score,
                'distance': hit.distance,
                'matched_terms': hit.matched_terms,
                'term_coverage': hit.term_coverage,
                'char_start': hit.chunk.char_start,
                'char_end': hit.chunk.char_end,
            }
        )
    return rows


def _run_query(sample: BenchmarkSample, hits: list[SearchHit], latency_ms: int) -> BenchmarkQueryResult:
    relevant_rank: int | None = None
    for rank, hit in enumerate(hits, start=1):
        if _is_relevant(sample, hit.chunk):
            relevant_rank = rank
            break
    reciprocal_rank = (1 / relevant_rank) if relevant_rank else 0.0
    return BenchmarkQueryResult(
        sample_id=sample.sample_id,
        question=sample.question,
        expected_note_id=sample.expected_note_id,
        expected_chunk_id=sample.expected_chunk_id,
        expected_ref=sample.expected_ref,
        retrieved=_retrieved_payload(hits),
        relevant_rank=relevant_rank,
        hit_at_k=1 if relevant_rank else 0,
        reciprocal_rank=reciprocal_rank,
        latency_ms=latency_ms,
    )
