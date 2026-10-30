"""Comparação de uma suite inteira: lexical, vector e hybrid por caso, mais a passada no corpus."""

from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter
from uuid import uuid4

from escolio.benchmark.datasets import (
    BenchmarkDataset,
    BenchmarkSuite,
    load_benchmark_dataset,
)
from escolio.benchmark.run_corpus import run_corpus_benchmark
from escolio.benchmark.run_single import run_benchmark
from escolio.benchmark.runner_models import (
    BenchmarkCaseComparisonResult,
    BenchmarkComparisonResult,
    BenchmarkRunResult,
    BenchmarkSettingsSnapshot,
)
from escolio.benchmark.summaries import _summarize_strategy
from escolio.ingest.loaders import load_document
from escolio.notes.schemas import Note
from escolio.notes.structurer import structure_document
from escolio.providers.answer import AnswerProvider
from escolio.providers.embed import Embedder
from escolio.retrieval.rerank import Reranker
from escolio.retrieval.search import (
    DEFAULT_HYBRID_LEXICAL_WEIGHT,
    DEFAULT_HYBRID_RANK_CONSTANT,
    DEFAULT_HYBRID_VECTOR_WEIGHT,
)
from escolio.storage.vector import LocalVectorStore


def benchmark_compare_dir(results_dir: Path, suite_name: str) -> Path:
    """Pasta da comparação, com SQLite e Chroma próprios, separados do corpus do usuário.

    O histórico (benchmark_queries) referencia notes e chunks, então as notas da suite moram no
    mesmo banco do histórico. Usar o banco do corpus enchia Notas e o chat com os documentos da
    suite e deixava chunks no SQLite sem vetor no Chroma (o Doctor acusava corpus inconsistente).
    """
    return results_dir / 'benchmark_compare' / suite_name


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
    answer_provider: AnswerProvider | None = None,
    keep_answers: bool = False,
    reranker: Reranker | None = None,
) -> BenchmarkComparisonResult:
    """Compara lexical, vector e hybrid em múltiplos documentos de forma reproduzível."""
    started_at = datetime.now(UTC)
    started_perf = perf_counter()
    vector_store.reset()

    case_results: list[BenchmarkCaseComparisonResult] = []
    lexical_runs: list[BenchmarkRunResult] = []
    vector_runs: list[BenchmarkRunResult] = []
    hybrid_runs: list[BenchmarkRunResult] = []
    corpus_cases: list[tuple[Note, BenchmarkDataset]] = []

    for case in suite.cases:
        document_path = workspace_dir / case.document_path
        dataset_path = workspace_dir / case.dataset_path
        note = structure_document(load_document(document_path))
        dataset = load_benchmark_dataset(dataset_path)
        corpus_cases.append((note, dataset))

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
            reuse_vectors=True,  # a rodada vetorial acabou de gravar estes mesmos chunks
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

    corpus = None
    if connection is not None:  # as rodadas por nota acabaram de gravar todas as notas no SQLite e no Chroma
        negatives = (
            load_benchmark_dataset(workspace_dir / suite.negative_dataset_path).samples
            if suite.negative_dataset_path
            else []
        )
        corpus = run_corpus_benchmark(
            corpus_cases,
            negatives,
            connection=connection,
            vector_store=vector_store,
            embedder=embedder,
            top_k=top_k,
            answer_provider=answer_provider,
            keep_answers=keep_answers,
            reranker=reranker,
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
        corpus=corpus,
        answer_provider=answer_provider.provider_name if answer_provider is not None else 'extractive',
        answer_model=getattr(answer_provider, 'model', None),
        started_at=started_at,
        finished_at=finished_at,
        duration_ms=duration_ms,
    )
