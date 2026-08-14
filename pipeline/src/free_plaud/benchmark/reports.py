import csv
import json
from pathlib import Path

from free_plaud.benchmark.runners import BenchmarkComparisonResult, BenchmarkRunResult

SETTINGS_SNAPSHOT_FIELDS = [
    'embedding_model',
    'embedding_device',
    'default_ask_strategy',
    'retrieval_top_k',
    'default_chunk_size',
    'default_chunk_overlap',
    'answer_provider',
    'settings_created_at',
]


def _settings_snapshot_row(result: BenchmarkRunResult | BenchmarkComparisonResult) -> dict[str, object]:
    if result.settings_snapshot is None:
        return {field: '' for field in SETTINGS_SNAPSHOT_FIELDS}
    payload = result.settings_snapshot.model_dump(mode='json')
    payload['settings_created_at'] = payload.pop('created_at')
    return payload


def export_benchmark_json(result: BenchmarkRunResult, path: Path) -> Path:
    """Exporta o resultado completo do benchmark para JSON."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(result.model_dump(mode='json'), ensure_ascii=False, indent=2),
        encoding='utf-8',
    )
    return path


def export_benchmark_csv(result: BenchmarkRunResult, path: Path) -> Path:
    """Exporta uma linha por pergunta avaliada para CSV."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        'benchmark_run_id',
        'dataset_name',
        'sample_id',
        'question',
        'hit_at_k',
        'reciprocal_rank',
        'latency_ms',
        'relevant_rank',
        *SETTINGS_SNAPSHOT_FIELDS,
    ]
    settings_snapshot = _settings_snapshot_row(result)
    with path.open('w', encoding='utf-8', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for query in result.queries:
            writer.writerow(
                {
                    'benchmark_run_id': result.benchmark_run_id,
                    'dataset_name': result.dataset_name,
                    'sample_id': query.sample_id,
                    'question': query.question,
                    'hit_at_k': query.hit_at_k,
                    'reciprocal_rank': query.reciprocal_rank,
                    'latency_ms': query.latency_ms,
                    'relevant_rank': query.relevant_rank,
                    **settings_snapshot,
                }
            )
    return path


def export_benchmark_comparison_json(result: BenchmarkComparisonResult, path: Path) -> Path:
    """Exporta comparação de estratégias para JSON."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(result.model_dump(mode='json'), ensure_ascii=False, indent=2),
        encoding='utf-8',
    )
    return path


def export_benchmark_comparison_csv(result: BenchmarkComparisonResult, path: Path) -> Path:
    """Exporta uma linha por caso e estratégia na comparação."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        'comparison_id',
        'suite_name',
        'case_id',
        'document_path',
        'dataset_path',
        'note_id',
        'strategy',
        'benchmark_run_id',
        'query_count',
        'mrr',
        'recall_at_3',
        'recall_at_5',
        'recall_at_10',
        'ndcg_at_10',
        'duration_ms',
        'avg_query_latency_ms',
        *SETTINGS_SNAPSHOT_FIELDS,
    ]
    settings_snapshot = _settings_snapshot_row(result)
    with path.open('w', encoding='utf-8', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for case in result.cases:
            for strategy in ('lexical', 'vector', 'hybrid'):
                run = getattr(case, strategy)
                writer.writerow(
                    {
                        'comparison_id': result.comparison_id,
                        'suite_name': result.suite_name,
                        'case_id': case.case_id,
                        'document_path': case.document_path,
                        'dataset_path': case.dataset_path,
                        'note_id': case.note_id,
                        'strategy': strategy,
                        'benchmark_run_id': run.benchmark_run_id,
                        'query_count': run.metrics['query_count'],
                        'mrr': run.metrics['mrr'],
                        'recall_at_3': run.metrics['recall_at_3'],
                        'recall_at_5': run.metrics['recall_at_5'],
                        'recall_at_10': run.metrics['recall_at_10'],
                        'ndcg_at_10': run.metrics['ndcg_at_10'],
                        'duration_ms': run.duration_ms,
                        'avg_query_latency_ms': run.metrics['avg_latency_ms'],
                        **settings_snapshot,
                    }
                )
    return path
