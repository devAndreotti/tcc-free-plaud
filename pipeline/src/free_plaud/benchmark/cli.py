import json
from pathlib import Path

import typer
from rich.console import Console

from free_plaud.app.cli_paths import compose_path
from free_plaud.app.config import get_settings
from free_plaud.app.paths import ensure_runtime_dirs
from free_plaud.benchmark.datasets import demo_dataset, load_benchmark_dataset, load_benchmark_suite
from free_plaud.benchmark.reports import (
    export_benchmark_comparison_csv,
    export_benchmark_comparison_json,
    export_benchmark_csv,
    export_benchmark_json,
)
from free_plaud.benchmark.runners import compare_benchmark_suite, run_benchmark
from free_plaud.ingest.loaders import load_document
from free_plaud.notes.structurer import structure_document
from free_plaud.providers.embed import get_embedder
from free_plaud.storage.sqlite import init_sqlite
from free_plaud.storage.vector import LocalVectorStore

app = typer.Typer(help="Comandos de benchmark experimental.", no_args_is_help=True)
console = Console()


@app.command("run-demo")
def run_demo(path_parts: list[str] = typer.Argument(..., metavar="PATH")) -> None:
    """Executa um benchmark mínimo em cima de um único documento."""
    path = compose_path(path_parts)
    note = structure_document(load_document(path))
    result = run_benchmark(note, demo_dataset(), strategy='lexical', top_k=3)
    typer.echo(json.dumps(result.model_dump(mode='json'), ensure_ascii=True, indent=2))


@app.command("run")
def run(
    path_parts: list[str] = typer.Argument(..., metavar="PATH"),
    dataset_path: Path = typer.Option(..., '--dataset', '-d', help="Arquivo JSON com o dataset de benchmark."),
    strategy: str = typer.Option('lexical', '--strategy', '-s', help="Estrategia: lexical ou vector."),
    top_k: int = typer.Option(3, '--top-k', min=1),
    chunk_size: int = typer.Option(800, '--chunk-size', min=1),
    overlap: int = typer.Option(120, '--overlap', min=0),
    run_name: str = typer.Option('benchmark', '--run-name'),
    embedding_model: str | None = typer.Option(None, '--embedding-model', help="Override do embedding model para strategy=vector."),
    export: bool = typer.Option(False, '--export', help="Exporta JSON e CSV em data/results."),
) -> None:
    """Executa benchmark reproduzível e persiste a execução em SQLite."""
    if strategy not in {'lexical', 'vector'}:
        raise typer.BadParameter("strategy deve ser 'lexical' ou 'vector'.")

    settings = get_settings()
    ensure_runtime_dirs(settings)
    note = structure_document(load_document(compose_path(path_parts)))
    dataset = load_benchmark_dataset(dataset_path)
    connection = init_sqlite(settings.sqlite_path)
    vector_store = None
    embedder = None
    resolved_embedding_model = embedding_model or settings.embedding_model
    if strategy == 'vector':
        vector_store = LocalVectorStore(settings.vector_store_dir, collection_name=settings.vector_collection_name)
        embedder = get_embedder(resolved_embedding_model)

    result = run_benchmark(
        note,
        dataset,
        connection=connection,
        strategy=strategy,  # type: ignore[arg-type]
        top_k=top_k,
        chunk_size=chunk_size,
        overlap=overlap,
        run_name=run_name,
        vector_store=vector_store,
        embedder=embedder,
    )
    payload = result.model_dump(mode='json')
    if export:
        output_base = settings.results_dir / result.benchmark_run_id
        json_path = export_benchmark_json(result, output_base.with_suffix('.json'))
        csv_path = export_benchmark_csv(result, output_base.with_suffix('.csv'))
        payload['json_report_path'] = str(json_path)
        payload['csv_report_path'] = str(csv_path)
    typer.echo(json.dumps(payload, ensure_ascii=True, indent=2))


@app.command("compare")
def compare(
    suite_path: Path = typer.Option(..., '--suite', '-u', help="Manifesto JSON com casos de benchmark."),
    top_k: int = typer.Option(3, '--top-k', min=1),
    chunk_size: int = typer.Option(800, '--chunk-size', min=1),
    overlap: int = typer.Option(120, '--overlap', min=0),
    embedding_model: str | None = typer.Option(None, '--embedding-model', help="Override do embedding model para a comparacao vetorial."),
    export: bool = typer.Option(False, '--export', help="Exporta JSON e CSV em data/results."),
) -> None:
    """Compara lexical vs vector em uma suíte de documentos e datasets."""
    settings = get_settings()
    ensure_runtime_dirs(settings)
    suite = load_benchmark_suite(suite_path)
    connection = init_sqlite(settings.sqlite_path)
    vector_store = LocalVectorStore(
        settings.results_dir / 'benchmark_compare' / suite.suite_name,
        collection_name=f'{suite.suite_name}_compare',
    )
    resolved_embedding_model = embedding_model or settings.embedding_model
    embedder = get_embedder(resolved_embedding_model)

    result = compare_benchmark_suite(
        suite,
        workspace_dir=settings.workspace_dir,
        connection=connection,
        top_k=top_k,
        chunk_size=chunk_size,
        overlap=overlap,
        vector_store=vector_store,
        embedder=embedder,
    )
    payload = result.model_dump(mode='json')
    if export:
        output_base = settings.results_dir / result.comparison_id
        json_path = export_benchmark_comparison_json(result, output_base.with_suffix('.json'))
        csv_path = export_benchmark_comparison_csv(result, output_base.with_suffix('.csv'))
        payload['json_report_path'] = str(json_path)
        payload['csv_report_path'] = str(csv_path)
    typer.echo(json.dumps(payload, ensure_ascii=True, indent=2))
