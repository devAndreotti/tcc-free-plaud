import csv
import json
from pathlib import Path

from free_plaud.benchmark.runners import BenchmarkRunResult


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
    ]
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
                }
            )
    return path
