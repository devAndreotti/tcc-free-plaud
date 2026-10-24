"""Fachada da execução de benchmark. A implementação está dividida em módulos irmãos:

- runner_models: modelos de resultado e constantes da versão do pipeline;
- query_scoring: relevância do trecho e ranking de uma consulta;
- summaries: sumarização de métricas (MRR, Recall@k, nDCG, latência, IC);
- run_single: benchmark de uma nota, com persistência;
- run_corpus: passada no corpus, no mesmo caminho de busca do chat;
- compare: comparação de uma suite inteira.

Este módulo mantém `escolio.benchmark.runners` como ponto de entrada estável.
"""

from escolio.benchmark.compare import benchmark_compare_dir, compare_benchmark_suite
from escolio.benchmark.query_scoring import (
    _contains_expected_terms,
    _is_relevant,
    _retrieved_payload,
    _run_query,
)
from escolio.benchmark.run_corpus import run_corpus_benchmark
from escolio.benchmark.run_single import (
    _persist_benchmark_result,
    run_benchmark,
    run_demo_benchmark,
)
from escolio.benchmark.runner_models import (
    CORPUS_RETRIEVAL_DEPTH,
    PIPELINE_VERSION,
    STRATEGIES,
    BenchmarkAnswerMetrics,
    BenchmarkCaseComparisonResult,
    BenchmarkComparisonResult,
    BenchmarkCorpusResult,
    BenchmarkQueryResult,
    BenchmarkRunResult,
    BenchmarkSettingsSnapshot,
    BenchmarkStrategySummary,
)
from escolio.benchmark.summaries import (
    _ci,
    _percentile,
    _summarize_answer_metrics,
    _summarize_queries,
    _summarize_strategy,
)

__all__ = [
    'CORPUS_RETRIEVAL_DEPTH',
    'PIPELINE_VERSION',
    'STRATEGIES',
    'BenchmarkAnswerMetrics',
    'BenchmarkCaseComparisonResult',
    'BenchmarkComparisonResult',
    'BenchmarkCorpusResult',
    'BenchmarkQueryResult',
    'BenchmarkRunResult',
    'BenchmarkSettingsSnapshot',
    'BenchmarkStrategySummary',
    '_ci',
    '_contains_expected_terms',
    '_is_relevant',
    '_percentile',
    '_persist_benchmark_result',
    '_retrieved_payload',
    '_run_query',
    '_summarize_answer_metrics',
    '_summarize_queries',
    '_summarize_strategy',
    'benchmark_compare_dir',
    'compare_benchmark_suite',
    'run_benchmark',
    'run_corpus_benchmark',
    'run_demo_benchmark',
]
