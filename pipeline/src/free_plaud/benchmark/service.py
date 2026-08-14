from pathlib import Path

from free_plaud.app.config import Settings, get_settings
from free_plaud.app.paths import ensure_runtime_dirs
from free_plaud.benchmark.datasets import load_benchmark_suite
from free_plaud.benchmark.reports import (
    export_benchmark_comparison_csv,
    export_benchmark_comparison_json,
)
from free_plaud.benchmark.runners import (
    BenchmarkComparisonResult,
    BenchmarkSettingsSnapshot,
    compare_benchmark_suite,
)
from free_plaud.corpus.runtime import CorpusRuntime
from free_plaud.providers.embed import get_embedder
from free_plaud.storage.sqlite import init_sqlite
from free_plaud.storage.vector import LocalVectorStore


def build_settings_snapshot(settings: Settings) -> BenchmarkSettingsSnapshot:
    return BenchmarkSettingsSnapshot(
        embedding_model=settings.embedding_model,
        embedding_device=settings.embedding_device,
        default_ask_strategy=settings.default_ask_strategy,
        retrieval_top_k=settings.retrieval_top_k,
        default_chunk_size=settings.default_chunk_size,
        default_chunk_overlap=settings.default_chunk_overlap,
        answer_provider=settings.answer_provider,
    )


def benchmark_comparison_payload(result: BenchmarkComparisonResult, json_path: Path, csv_path: Path) -> dict:
    payload = result.model_dump(mode='json')
    payload.update(
        {
            'ok': True,
            'json_report_path': str(json_path),
            'csv_report_path': str(csv_path),
        }
    )
    return payload


def _resolve_suite_path(suite_path: Path, settings: Settings) -> Path:
    expanded = suite_path.expanduser()
    if expanded.is_absolute():
        return expanded
    return settings.workspace_dir / expanded


def run_benchmark_compare(
    suite_path: str | Path,
    *,
    runtime: CorpusRuntime | None = None,
    settings: Settings | None = None,
) -> dict:
    resolved_settings = settings or get_settings()
    ensure_runtime_dirs(resolved_settings)
    suite_file = _resolve_suite_path(Path(suite_path), resolved_settings)
    suite = load_benchmark_suite(suite_file)
    snapshot = build_settings_snapshot(resolved_settings)
    connection = init_sqlite(resolved_settings.sqlite_path)
    try:
        vector_store = LocalVectorStore(
            resolved_settings.results_dir / 'benchmark_compare' / suite.suite_name,
            collection_name=f'{suite.suite_name}_compare',
        )
        embedder = runtime.get_embedder() if runtime is not None else get_embedder(
            resolved_settings.embedding_model,
            device=resolved_settings.embedding_device,
        )
        result = compare_benchmark_suite(
            suite,
            workspace_dir=resolved_settings.workspace_dir,
            connection=connection,
            top_k=resolved_settings.retrieval_top_k,
            chunk_size=resolved_settings.default_chunk_size,
            overlap=resolved_settings.default_chunk_overlap,
            vector_store=vector_store,
            embedder=embedder,
            settings_snapshot=snapshot,
        )
        output_base = resolved_settings.results_dir / result.comparison_id
        json_path = export_benchmark_comparison_json(result, output_base.with_suffix('.json'))
        csv_path = export_benchmark_comparison_csv(result, output_base.with_suffix('.csv'))
        return benchmark_comparison_payload(result, json_path, csv_path)
    finally:
        connection.close()
