"""Execução do benchmark de uma nota (uma estratégia por vez) e persistência do resultado."""

from datetime import UTC, datetime
from time import perf_counter
from typing import Literal
from uuid import uuid4

from escolio.benchmark.datasets import BenchmarkDataset, BenchmarkSample
from escolio.benchmark.metrics import (
    mean_reciprocal_rank,
    ndcg_at_k,
    recall_at_k_from_ranks,
)
from escolio.benchmark.query_scoring import _run_query
from escolio.benchmark.runner_models import (
    PIPELINE_VERSION,
    BenchmarkQueryResult,
    BenchmarkRunResult,
    BenchmarkSettingsSnapshot,
)
from escolio.notes.schemas import Note
from escolio.providers.embed import Embedder
from escolio.retrieval.indexer import index_note, index_note_in_vector_store
from escolio.retrieval.search import (
    DEFAULT_HYBRID_LEXICAL_WEIGHT,
    DEFAULT_HYBRID_RANK_CONSTANT,
    DEFAULT_HYBRID_VECTOR_WEIGHT,
    hybrid_search,
    lexical_search_hits,
    semantic_search,
)
from escolio.storage.models import BenchmarkQueryRecord, BenchmarkRunRecord
from escolio.storage.sqlite import (
    insert_benchmark_query,
    insert_benchmark_run,
    replace_chunks_for_note,
    upsert_note,
)
from escolio.storage.vector import LocalVectorStore


def run_benchmark(
    note: Note,
    dataset: BenchmarkDataset,
    *,
    connection=None,
    strategy: Literal['lexical', 'vector', 'hybrid'] = 'lexical',
    top_k: int = 3,
    chunk_size: int = 800,
    overlap: int = 120,
    run_name: str = 'benchmark',
    vector_store: LocalVectorStore | None = None,
    embedder: Embedder | None = None,
    hybrid_rank_constant: int = DEFAULT_HYBRID_RANK_CONSTANT,
    hybrid_lexical_weight: float = DEFAULT_HYBRID_LEXICAL_WEIGHT,
    hybrid_vector_weight: float = DEFAULT_HYBRID_VECTOR_WEIGHT,
    hybrid_lexical_pool: int | None = None,
    hybrid_vector_pool: int | None = None,
    settings_snapshot: BenchmarkSettingsSnapshot | None = None,
    reuse_vectors: bool = False,
) -> BenchmarkRunResult:
    """Executa benchmark reproduzível sobre uma nota canônica.

    `reuse_vectors` pula o embedding quando o store já tem estes chunks. O chunk_id inclui o
    hash do texto e as posições, então ids iguais são textos iguais; só use quando o store foi
    preenchido pelo mesmo embedder (como na comparação, que zera o store no início).
    """
    started_at = datetime.now(UTC)
    started_perf = perf_counter()

    if strategy == 'lexical':
        chunks = index_note(note, chunk_size=chunk_size, overlap=overlap)
    elif strategy in {'vector', 'hybrid'}:
        if vector_store is None or embedder is None:
            raise ValueError('Vector store e embedder sao obrigatorios para strategy=vector e strategy=hybrid.')
        chunks = index_note(note, chunk_size=chunk_size, overlap=overlap)
        if not (reuse_vectors and vector_store.has_chunk_ids([chunk.chunk_id for chunk in chunks])):
            chunks = index_note_in_vector_store(note, vector_store, embedder, chunk_size=chunk_size, overlap=overlap)
    else:
        raise ValueError("strategy deve ser 'lexical', 'vector' ou 'hybrid'.")

    if connection is not None:
        upsert_note(connection, note)
        replace_chunks_for_note(connection, note.note_id, chunks)

    query_results: list[BenchmarkQueryResult] = []
    for sample in dataset.samples:
        query_started = perf_counter()
        if strategy == 'lexical':
            hits = lexical_search_hits(sample.question, chunks, top_k=top_k)
        elif strategy == 'hybrid':
            hits = hybrid_search(
                sample.question,
                chunks,
                vector_store,  # type: ignore[arg-type]
                embedder,  # type: ignore[arg-type]
                top_k=top_k,
                note_id=note.note_id,
                lexical_pool_size=hybrid_lexical_pool or max(top_k * 3, top_k),
                vector_pool_size=hybrid_vector_pool or max(top_k * 8, 24),
                rank_constant=hybrid_rank_constant,
                lexical_weight=hybrid_lexical_weight,
                vector_weight=hybrid_vector_weight,
            )
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
        'ndcg_at_3': ndcg_at_k(ranks, 3),
        'ndcg_at_5': ndcg_at_k(ranks, 5),
        'ndcg_at_10': ndcg_at_k(ranks, 10),
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
        hybrid_config=(
            {
                'rank_constant': hybrid_rank_constant,
                'lexical_weight': hybrid_lexical_weight,
                'vector_weight': hybrid_vector_weight,
                'lexical_pool': hybrid_lexical_pool or max(top_k * 3, top_k),
                'vector_pool': hybrid_vector_pool or max(top_k * 8, 24),
            }
            if strategy == 'hybrid'
            else None
        ),
        settings_snapshot=settings_snapshot,
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
            config={
                'chunk_size': result.chunk_size,
                'overlap': result.overlap,
                'hybrid_config': result.hybrid_config,
                'settings_snapshot': (
                    result.settings_snapshot.model_dump(mode='json') if result.settings_snapshot else None
                ),
            },
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
