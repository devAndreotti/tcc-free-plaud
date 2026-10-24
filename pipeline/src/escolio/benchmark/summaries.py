"""Sumarização das métricas de retrieval e da resposta do chat (MRR, Recall@k, nDCG, latência, IC)."""

from collections import Counter
from statistics import quantiles

from escolio.benchmark.metrics import (
    bootstrap_ci,
    mean_reciprocal_rank,
    ndcg_at_k,
    recall_at_k_from_ranks,
)
from escolio.benchmark.runner_models import (
    BenchmarkAnswerMetrics,
    BenchmarkQueryResult,
    BenchmarkRunResult,
    BenchmarkStrategySummary,
)


def _percentile(values: list[int], percent: int) -> float:
    if len(values) < 2:
        return float(values[0]) if values else 0.0
    return quantiles(values, n=100, method='inclusive')[percent - 1]


def _ci(values: list[float]) -> list[float]:
    interval = bootstrap_ci(values)
    return [interval['lower'], interval['upper']]


def _summarize_queries(
    strategy: str,
    queries: list[BenchmarkQueryResult],
    *,
    case_count: int,
    duration_ms: int,
) -> BenchmarkStrategySummary:
    ranks = [query.relevant_rank for query in queries]
    latencies = [query.latency_ms for query in queries]
    return BenchmarkStrategySummary(
        strategy=strategy,
        case_count=case_count,
        query_count=len(ranks),
        mrr=mean_reciprocal_rank(ranks),
        recall_at_3=recall_at_k_from_ranks(ranks, 3),
        recall_at_5=recall_at_k_from_ranks(ranks, 5),
        recall_at_10=recall_at_k_from_ranks(ranks, 10),
        ndcg_at_10=ndcg_at_k(ranks, 10),
        duration_ms=duration_ms,
        avg_query_latency_ms=(sum(latencies) / len(latencies)) if latencies else 0.0,
        p50_query_latency_ms=_percentile(latencies, 50),
        p95_query_latency_ms=_percentile(latencies, 95),
        mrr_ci=_ci([query.reciprocal_rank for query in queries]),
        recall_at_5_ci=_ci([1.0 if rank is not None and rank <= 5 else 0.0 for rank in ranks]),
    )


def _summarize_strategy(strategy: str, runs: list[BenchmarkRunResult]) -> BenchmarkStrategySummary:
    return _summarize_queries(
        strategy,
        [query for run in runs for query in run.queries],
        case_count=len(runs),
        duration_ms=sum(run.duration_ms for run in runs),
    )

def _summarize_answer_metrics(rows: list[BenchmarkQueryResult], *, has_provider: bool) -> BenchmarkAnswerMetrics:
    """Taxa de aceite sobre as respostas `answer`; latência p50/p95 da pergunta inteira."""
    answer_count = sum(1 for row in rows if row.answered)
    accepted_count = sum(1 for row in rows if row.generated)
    latencies = [row.question_latency_ms for row in rows if row.question_latency_ms is not None]
    return BenchmarkAnswerMetrics(
        answer_count=answer_count,
        accepted_count=accepted_count,
        accepted_rate=accepted_count / answer_count if has_provider and answer_count else None,
        discard_reasons=dict(sorted(Counter(row.discard_reason for row in rows if row.discard_reason).items())),
        question_p50_ms=_percentile(latencies, 50),
        question_p95_ms=_percentile(latencies, 95),
    )
