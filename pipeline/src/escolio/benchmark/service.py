from pathlib import Path

from escolio.app.config import Settings, get_settings
from escolio.app.paths import ensure_runtime_dirs
from escolio.benchmark.compare_flags import executar_compare_com_flags
from escolio.benchmark.datasets import load_benchmark_suite
from escolio.benchmark.json_merge import mesclar_chaves_json
from escolio.benchmark.reports import (
    export_benchmark_comparison_csv,
    export_benchmark_comparison_json,
)
from escolio.benchmark.runners import (
    BenchmarkComparisonResult,
    BenchmarkSettingsSnapshot,
    benchmark_compare_dir,
    compare_benchmark_suite,
)
from escolio.corpus.runtime import CorpusRuntime
from escolio.providers.embed import get_embedder
from escolio.retrieval.rerank import reranker_from_settings
from escolio.storage.sqlite import init_sqlite
from escolio.storage.vector import LocalVectorStore


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
    compare_dir = benchmark_compare_dir(resolved_settings.results_dir, suite.suite_name)
    connection = init_sqlite(compare_dir / 'benchmark.sqlite3')
    try:
        vector_store = LocalVectorStore(compare_dir, collection_name=f'{suite.suite_name}_compare')
        embedder = runtime.get_embedder() if runtime is not None else get_embedder(
            resolved_settings.embedding_model,
            device=resolved_settings.embedding_device,
        )
        # Sem `rerank_model` nada muda: uma passada só, como antes. Com ele, a UI recebe baseline + reranker
        # e a cobertura entre trechos (campos opcionais do painel de Benchmark).
        rerank_model = resolved_settings.rerank_model.strip()
        reranker = reranker_from_settings(resolved_settings)
        result, extras = executar_compare_com_flags(
            suite,
            comparar=compare_benchmark_suite,
            reranker=reranker,
            rerank_model=rerank_model or None,
            com_baseline=reranker is not None,
            ks=(3, 5, 10) if reranker is not None else None,
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
        if extras:
            mesclar_chaves_json(json_path, extras)
        payload = benchmark_comparison_payload(result, json_path, csv_path)
        payload.update(extras)
        return payload
    finally:
        connection.close()
