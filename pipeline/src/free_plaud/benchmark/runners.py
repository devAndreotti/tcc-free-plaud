from datetime import UTC, datetime
from time import perf_counter
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field

from free_plaud.benchmark.datasets import BenchmarkDataset, BenchmarkSample
from free_plaud.benchmark.metrics import mean_reciprocal_rank, recall_at_k_from_ranks
from free_plaud.notes.schemas import Note
from free_plaud.providers.embed import Embedder
from free_plaud.retrieval.indexer import index_note, index_note_in_vector_store
from free_plaud.retrieval.models import Chunk, SearchHit
from free_plaud.retrieval.search import lexical_search_hits, semantic_search
from free_plaud.storage.models import BenchmarkQueryRecord, BenchmarkRunRecord
from free_plaud.storage.sqlite import insert_benchmark_query, insert_benchmark_run, replace_chunks_for_note, upsert_note
from free_plaud.storage.vector import LocalVectorStore

PIPELINE_VERSION = 'pipeline-0.7.0'


class BenchmarkQueryResult(BaseModel):
    sample_id: str
    question: str
    expected_note_id: str | None = None
    expected_chunk_id: str | None = None
    expected_ref: str | None = None
    retrieved: list[dict[str, object]] = Field(default_factory=list)
    relevant_rank: int | None = None
    hit_at_k: int
    reciprocal_rank: float
    latency_ms: int


class BenchmarkRunResult(BaseModel):
    benchmark_run_id: str
    run_name: str
    dataset_name: str
    retrieval_strategy: str
    chunking_strategy: str
    embedding_model: str
    top_k: int
    chunk_size: int
    overlap: int
    metrics: dict[str, float | int]
    queries: list[BenchmarkQueryResult]
    started_at: datetime
    finished_at: datetime
    duration_ms: int


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


def run_benchmark(
    note: Note,
    dataset: BenchmarkDataset,
    *,
    connection=None,
    strategy: Literal['lexical', 'vector'] = 'lexical',
    top_k: int = 3,
    chunk_size: int = 800,
    overlap: int = 120,
    run_name: str = 'benchmark',
    vector_store: LocalVectorStore | None = None,
    embedder: Embedder | None = None,
) -> BenchmarkRunResult:
    """Executa benchmark reproduzível sobre uma nota canônica."""
    started_at = datetime.now(UTC)
    started_perf = perf_counter()

    if strategy == 'lexical':
        chunks = index_note(note, chunk_size=chunk_size, overlap=overlap)
    elif strategy == 'vector':
        if vector_store is None or embedder is None:
            raise ValueError('Vector store e embedder sao obrigatorios para strategy=vector.')
        chunks = index_note_in_vector_store(note, vector_store, embedder, chunk_size=chunk_size, overlap=overlap)
    else:
        raise ValueError("strategy deve ser 'lexical' ou 'vector'.")

    if connection is not None:
        upsert_note(connection, note)
        replace_chunks_for_note(connection, note.note_id, chunks)

    query_results: list[BenchmarkQueryResult] = []
    for sample in dataset.samples:
        query_started = perf_counter()
        if strategy == 'lexical':
            hits = lexical_search_hits(sample.question, chunks, top_k=top_k)
        else:
            hits = semantic_search(sample.question, vector_store, embedder, top_k=top_k, note_id=note.note_id)  # type: ignore[arg-type]
        latency_ms = int((perf_counter() - query_started) * 1000)
        query_results.append(_run_query(sample, hits, latency_ms))

    ranks = [result.relevant_rank for result in query_results]
    finished_at = datetime.now(UTC)
    duration_ms = int((perf_counter() - started_perf) * 1000)
    metrics: dict[str, float | int] = {
        'query_count': len(query_results),
        'mrr': mean_reciprocal_rank(ranks),
        'recall_at_3': recall_at_k_from_ranks(ranks, 3),
        'recall_at_5': recall_at_k_from_ranks(ranks, 5),
        'recall_at_10': recall_at_k_from_ranks(ranks, 10),
        'latency_ms': duration_ms,
        'avg_latency_ms': sum(result.latency_ms for result in query_results) / len(query_results)
        if query_results
        else 0.0,
    }
    run_result = BenchmarkRunResult(
        benchmark_run_id=f'run-{uuid4().hex[:12]}',
        run_name=run_name,
        dataset_name=dataset.dataset_name,
        retrieval_strategy=strategy,
        chunking_strategy='fixed_char_window',
        embedding_model=embedder.model_name if embedder else 'not-used',
        top_k=top_k,
        chunk_size=chunk_size,
        overlap=overlap,
        metrics=metrics,
        queries=query_results,
        started_at=started_at,
        finished_at=finished_at,
        duration_ms=duration_ms,
    )

    if connection is not None:
        _persist_benchmark_result(connection, note, run_result)
    return run_result


def _persist_benchmark_result(connection, note: Note, result: BenchmarkRunResult) -> None:
    insert_benchmark_run(
        connection,
        BenchmarkRunRecord(
            benchmark_run_id=result.benchmark_run_id,
            run_name=result.run_name,
            dataset_name=result.dataset_name,
            corpus_snapshot=note.content_hash,
            retrieval_strategy=result.retrieval_strategy,
            chunking_strategy=result.chunking_strategy,
            embedding_model=result.embedding_model,
            top_k=result.top_k,
            query_count=len(result.queries),
            pipeline_version=PIPELINE_VERSION,
            status='success',
            config={'chunk_size': result.chunk_size, 'overlap': result.overlap},
            metrics=dict(result.metrics),
            started_at=result.started_at,
            finished_at=result.finished_at,
            duration_ms=result.duration_ms,
        ),
    )
    for query in result.queries:
        insert_benchmark_query(
            connection,
            BenchmarkQueryRecord(
                benchmark_run_id=result.benchmark_run_id,
                query_id=query.sample_id,
                query_text=query.question,
                expected_note_id=query.expected_note_id,
                expected_chunk_id=query.expected_chunk_id,
                expected_ref=query.expected_ref,
                retrieved=query.retrieved,
                hit_at_k=query.hit_at_k,  # type: ignore[arg-type]
                reciprocal_rank=query.reciprocal_rank,
                latency_ms=query.latency_ms,
            ),
        )


def run_demo_benchmark(note: Note, samples: list[BenchmarkSample]) -> list[dict[str, float | str]]:
    """Mantém compatibilidade com o comando demo antigo."""
    dataset = BenchmarkDataset(dataset_name='demo', samples=samples)
    result = run_benchmark(note, dataset, strategy='lexical', top_k=3)
    return [
        {
            'sample_id': query.sample_id,
            'recall_at_3': result.metrics['recall_at_3'],
        }
        for query in result.queries
    ]
