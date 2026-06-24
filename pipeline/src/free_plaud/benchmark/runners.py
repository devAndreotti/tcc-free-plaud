from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field

from free_plaud.benchmark.datasets import (
    BenchmarkDataset,
    BenchmarkSample,
    BenchmarkSuite,
    load_benchmark_dataset,
)
from free_plaud.benchmark.metrics import mean_reciprocal_rank, ndcg_at_k, recall_at_k_from_ranks
from free_plaud.ingest.loaders import load_document
from free_plaud.notes.schemas import Note
from free_plaud.notes.structurer import structure_document
from free_plaud.providers.embed import Embedder
from free_plaud.retrieval.indexer import index_note, index_note_in_vector_store
from free_plaud.retrieval.models import Chunk, SearchHit
from free_plaud.retrieval.search import (
    DEFAULT_HYBRID_LEXICAL_WEIGHT,
    DEFAULT_HYBRID_RANK_CONSTANT,
    DEFAULT_HYBRID_VECTOR_WEIGHT,
    hybrid_search,
    lexical_search_hits,
    semantic_search,
)
from free_plaud.storage.models import BenchmarkQueryRecord, BenchmarkRunRecord
from free_plaud.storage.sqlite import insert_benchmark_query, insert_benchmark_run, replace_chunks_for_note, upsert_note
from free_plaud.storage.vector import LocalVectorStore

PIPELINE_VERSION = 'pipeline-0.7.0'


class BenchmarkSettingsSnapshot(BaseModel):
    """Configuração operacional gravada junto do resultado experimental."""

    embedding_model: str
    embedding_device: str
    default_ask_strategy: str
    retrieval_top_k: int
    default_chunk_size: int
    default_chunk_overlap: int
    answer_provider: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


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
    hybrid_config: dict[str, int | float | None] | None = None
    settings_snapshot: BenchmarkSettingsSnapshot | None = None
    started_at: datetime
    finished_at: datetime
    duration_ms: int


class BenchmarkStrategySummary(BaseModel):
    strategy: str
    case_count: int
    query_count: int
    mrr: float
    recall_at_3: float
    recall_at_5: float
    recall_at_10: float
    ndcg_at_10: float
    duration_ms: int
    avg_query_latency_ms: float


class BenchmarkCaseComparisonResult(BaseModel):
    case_id: str
    document_path: str
    dataset_path: str
    note_id: str
    note_title: str
    lexical: BenchmarkRunResult
    vector: BenchmarkRunResult
    hybrid: BenchmarkRunResult


class BenchmarkComparisonResult(BaseModel):
    comparison_id: str
    suite_name: str
    embedding_model: str
    top_k: int
    chunk_size: int
    overlap: int
    hybrid_config: dict[str, int | float | None] | None = None
    settings_snapshot: BenchmarkSettingsSnapshot | None = None
    summaries: dict[str, BenchmarkStrategySummary]
    cases: list[BenchmarkCaseComparisonResult]
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


def _summarize_strategy(strategy: str, runs: list[BenchmarkRunResult]) -> BenchmarkStrategySummary:
    ranks = [query.relevant_rank for run in runs for query in run.queries]
    query_latencies = [query.latency_ms for run in runs for query in run.queries]
    return BenchmarkStrategySummary(
        strategy=strategy,
        case_count=len(runs),
        query_count=len(ranks),
        mrr=mean_reciprocal_rank(ranks),
        recall_at_3=recall_at_k_from_ranks(ranks, 3),
        recall_at_5=recall_at_k_from_ranks(ranks, 5),
        recall_at_10=recall_at_k_from_ranks(ranks, 10),
        ndcg_at_10=ndcg_at_k(ranks, 10),
        duration_ms=sum(run.duration_ms for run in runs),
        avg_query_latency_ms=(sum(query_latencies) / len(query_latencies)) if query_latencies else 0.0,
    )


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
) -> BenchmarkRunResult:
    """Executa benchmark reproduzível sobre uma nota canônica."""
    started_at = datetime.now(UTC)
    started_perf = perf_counter()

    if strategy == 'lexical':
        chunks = index_note(note, chunk_size=chunk_size, overlap=overlap)
    elif strategy in {'vector', 'hybrid'}:
        if vector_store is None or embedder is None:
            raise ValueError('Vector store e embedder sao obrigatorios para strategy=vector e strategy=hybrid.')
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


def compare_benchmark_suite(
    suite: BenchmarkSuite,
    *,
    workspace_dir: Path,
    connection=None,
    top_k: int = 3,
    chunk_size: int = 800,
    overlap: int = 120,
    vector_store: LocalVectorStore,
    embedder: Embedder,
    hybrid_rank_constant: int = DEFAULT_HYBRID_RANK_CONSTANT,
    hybrid_lexical_weight: float = DEFAULT_HYBRID_LEXICAL_WEIGHT,
    hybrid_vector_weight: float = DEFAULT_HYBRID_VECTOR_WEIGHT,
    hybrid_lexical_pool: int | None = None,
    hybrid_vector_pool: int | None = None,
    settings_snapshot: BenchmarkSettingsSnapshot | None = None,
) -> BenchmarkComparisonResult:
    """Compara lexical, vector e hybrid em múltiplos documentos de forma reproduzível."""
    started_at = datetime.now(UTC)
    started_perf = perf_counter()
    vector_store.reset()

    case_results: list[BenchmarkCaseComparisonResult] = []
    lexical_runs: list[BenchmarkRunResult] = []
    vector_runs: list[BenchmarkRunResult] = []
    hybrid_runs: list[BenchmarkRunResult] = []

    for case in suite.cases:
        document_path = workspace_dir / case.document_path
        dataset_path = workspace_dir / case.dataset_path
        note = structure_document(load_document(document_path))
        dataset = load_benchmark_dataset(dataset_path)

        lexical_result = run_benchmark(
            note,
            dataset,
            connection=connection,
            strategy='lexical',
            top_k=top_k,
            chunk_size=chunk_size,
            overlap=overlap,
            run_name=f'{suite.suite_name}-{case.case_id}-lexical',
            settings_snapshot=settings_snapshot,
        )
        vector_result = run_benchmark(
            note,
            dataset,
            connection=connection,
            strategy='vector',
            top_k=top_k,
            chunk_size=chunk_size,
            overlap=overlap,
            run_name=f'{suite.suite_name}-{case.case_id}-vector',
            vector_store=vector_store,
            embedder=embedder,
            settings_snapshot=settings_snapshot,
        )
        hybrid_result = run_benchmark(
            note,
            dataset,
            connection=connection,
            strategy='hybrid',
            top_k=top_k,
            chunk_size=chunk_size,
            overlap=overlap,
            run_name=f'{suite.suite_name}-{case.case_id}-hybrid',
            vector_store=vector_store,
            embedder=embedder,
            hybrid_rank_constant=hybrid_rank_constant,
            hybrid_lexical_weight=hybrid_lexical_weight,
            hybrid_vector_weight=hybrid_vector_weight,
            hybrid_lexical_pool=hybrid_lexical_pool,
            hybrid_vector_pool=hybrid_vector_pool,
            settings_snapshot=settings_snapshot,
        )

        lexical_runs.append(lexical_result)
        vector_runs.append(vector_result)
        hybrid_runs.append(hybrid_result)
        case_results.append(
            BenchmarkCaseComparisonResult(
                case_id=case.case_id,
                document_path=str(case.document_path),
                dataset_path=str(case.dataset_path),
                note_id=note.note_id,
                note_title=note.title,
                lexical=lexical_result,
                vector=vector_result,
                hybrid=hybrid_result,
            )
        )

    finished_at = datetime.now(UTC)
    duration_ms = int((perf_counter() - started_perf) * 1000)
    return BenchmarkComparisonResult(
        comparison_id=f'cmp-{uuid4().hex[:12]}',
        suite_name=suite.suite_name,
        embedding_model=embedder.model_name,
        top_k=top_k,
        chunk_size=chunk_size,
        overlap=overlap,
        hybrid_config={
            'rank_constant': hybrid_rank_constant,
            'lexical_weight': hybrid_lexical_weight,
            'vector_weight': hybrid_vector_weight,
            'lexical_pool': hybrid_lexical_pool or max(top_k * 3, top_k),
            'vector_pool': hybrid_vector_pool or max(top_k * 8, 24),
        },
        settings_snapshot=settings_snapshot,
        summaries={
            'lexical': _summarize_strategy('lexical', lexical_runs),
            'vector': _summarize_strategy('vector', vector_runs),
            'hybrid': _summarize_strategy('hybrid', hybrid_runs),
        },
        cases=case_results,
        started_at=started_at,
        finished_at=finished_at,
        duration_ms=duration_ms,
    )


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
