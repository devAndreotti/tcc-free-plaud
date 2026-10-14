import json
from pathlib import Path

import typer
from rich.console import Console

from escolio.app.cli_paths import compose_path
from escolio.app.config import get_settings
from escolio.app.paths import ensure_runtime_dirs
from escolio.benchmark.datasets import (
    demo_dataset,
    load_benchmark_dataset,
    load_benchmark_suite,
)
from escolio.benchmark.grounded import evaluate_grounded_answers
from escolio.benchmark.reports import (
    export_benchmark_comparison_csv,
    export_benchmark_comparison_json,
    export_benchmark_csv,
    export_benchmark_json,
)
from escolio.benchmark.runners import (
    benchmark_compare_dir,
    compare_benchmark_suite,
    run_benchmark,
)
from escolio.benchmark.service import build_settings_snapshot
from escolio.ingest.loaders import load_document
from escolio.notes.structurer import structure_document
from escolio.providers.embed import (
    EmbeddingConfigurationError,
    get_embedder,
    validate_runtime_embedding_model,
)
from escolio.retrieval.search import (
    DEFAULT_HYBRID_LEXICAL_WEIGHT,
    DEFAULT_HYBRID_RANK_CONSTANT,
    DEFAULT_HYBRID_VECTOR_WEIGHT,
)
from escolio.storage.sqlite import init_sqlite
from escolio.storage.vector import LocalVectorStore

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
    strategy: str = typer.Option('lexical', '--strategy', '-s', help="Estrategia: lexical, vector ou hybrid."),
    top_k: int = typer.Option(3, '--top-k', min=1),
    chunk_size: int = typer.Option(800, '--chunk-size', min=1),
    overlap: int = typer.Option(120, '--overlap', min=0),
    run_name: str = typer.Option('benchmark', '--run-name'),
    embedding_model: str | None = typer.Option(None, '--embedding-model', help="Override do embedding model para strategy=vector ou strategy=hybrid."),
    hybrid_rank_constant: int = typer.Option(DEFAULT_HYBRID_RANK_CONSTANT, '--hybrid-rank-constant', min=1, help='Constante da rank fusion quando strategy=hybrid.'),
    hybrid_lexical_weight: float = typer.Option(DEFAULT_HYBRID_LEXICAL_WEIGHT, '--hybrid-lexical-weight', min=0.0, help='Peso do ranking lexical quando strategy=hybrid.'),
    hybrid_vector_weight: float = typer.Option(DEFAULT_HYBRID_VECTOR_WEIGHT, '--hybrid-vector-weight', min=0.0, help='Peso do ranking vetorial quando strategy=hybrid.'),
    hybrid_lexical_pool: int | None = typer.Option(None, '--hybrid-lexical-pool', min=1, help='Pool lexical candidato quando strategy=hybrid.'),
    hybrid_vector_pool: int | None = typer.Option(None, '--hybrid-vector-pool', min=1, help='Pool vetorial candidato quando strategy=hybrid.'),
    export: bool = typer.Option(False, '--export', help="Exporta JSON e CSV em data/results."),
) -> None:
    """Executa benchmark reproduzível e persiste a execução em SQLite."""
    if strategy not in {'lexical', 'vector', 'hybrid'}:
        raise typer.BadParameter("strategy deve ser 'lexical', 'vector' ou 'hybrid'.")

    settings = get_settings()
    ensure_runtime_dirs(settings)
    note = structure_document(load_document(compose_path(path_parts)))
    dataset = load_benchmark_dataset(dataset_path)
    resolved_embedding_model = embedding_model or settings.embedding_model
    if strategy in {'vector', 'hybrid'}:
        try:
            validate_runtime_embedding_model(resolved_embedding_model)
        except EmbeddingConfigurationError as exc:
            typer.echo(str(exc), err=True)
            raise typer.Exit(code=1) from None
    connection = init_sqlite(settings.sqlite_path)
    vector_store = None
    embedder = None
    if strategy in {'vector', 'hybrid'}:
        vector_store = LocalVectorStore(settings.vector_store_dir, collection_name=settings.vector_collection_name)
        embedder = get_embedder(resolved_embedding_model, device=settings.embedding_device)

    try:
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
            hybrid_rank_constant=hybrid_rank_constant,
            hybrid_lexical_weight=hybrid_lexical_weight,
            hybrid_vector_weight=hybrid_vector_weight,
            hybrid_lexical_pool=hybrid_lexical_pool,
            hybrid_vector_pool=hybrid_vector_pool,
            settings_snapshot=build_settings_snapshot(settings),
        )
        payload = result.model_dump(mode='json')
        if export:
            output_base = settings.results_dir / result.benchmark_run_id
            json_path = export_benchmark_json(result, output_base.with_suffix('.json'))
            csv_path = export_benchmark_csv(result, output_base.with_suffix('.csv'))
            payload['json_report_path'] = str(json_path)
            payload['csv_report_path'] = str(csv_path)
        typer.echo(json.dumps(payload, ensure_ascii=True, indent=2))
    finally:
        connection.close()


@app.command("answer-eval")
def answer_eval(
    path_parts: list[str] = typer.Argument(..., metavar="PATH"),
    dataset_path: Path = typer.Option(..., '--dataset', '-d', help="Dataset JSON com perguntas e categoria (direta/inferida/negativa)."),
    strategy: str = typer.Option('lexical', '--strategy', '-s', help="Estrategia: lexical, vector ou hybrid."),
    top_k: int = typer.Option(3, '--top-k', min=1),
    embedding_model: str | None = typer.Option(None, '--embedding-model', help="Override do embedding model para strategy=vector ou strategy=hybrid."),
) -> None:
    """Mede faithfulness (groundedness) e qualidade da abstenção do RAG."""
    if strategy not in {'lexical', 'vector', 'hybrid'}:
        raise typer.BadParameter("strategy deve ser 'lexical', 'vector' ou 'hybrid'.")

    settings = get_settings()
    ensure_runtime_dirs(settings)
    note = structure_document(load_document(compose_path(path_parts)))
    dataset = load_benchmark_dataset(dataset_path)

    vector_store = None
    embedder = None
    if strategy in {'vector', 'hybrid'}:
        resolved_embedding_model = embedding_model or settings.embedding_model
        try:
            validate_runtime_embedding_model(resolved_embedding_model)
        except EmbeddingConfigurationError as exc:
            typer.echo(str(exc), err=True)
            raise typer.Exit(code=1) from None
        # A avaliação indexa a nota no store; o Chroma do corpus ficaria com vetores sem nota no SQLite.
        vector_store = LocalVectorStore(benchmark_compare_dir(settings.results_dir, 'answer-eval'), collection_name='answer_eval')
        embedder = get_embedder(resolved_embedding_model, device=settings.embedding_device)

    report = evaluate_grounded_answers(
        note,
        dataset,
        strategy=strategy,  # type: ignore[arg-type]
        top_k=top_k,
        vector_store=vector_store,
        embedder=embedder,
    )
    typer.echo(json.dumps(report.model_dump(mode='json'), ensure_ascii=True, indent=2))


@app.command("compare")
def compare(
    suite_path: Path = typer.Option(..., '--suite', '-u', help="Manifesto JSON com casos de benchmark."),
    top_k: int = typer.Option(3, '--top-k', min=1),
    chunk_size: int = typer.Option(800, '--chunk-size', min=1),
    overlap: int = typer.Option(120, '--overlap', min=0),
    embedding_model: str | None = typer.Option(None, '--embedding-model', help="Override do embedding model para a comparacao vetorial."),
    hybrid_rank_constant: int = typer.Option(DEFAULT_HYBRID_RANK_CONSTANT, '--hybrid-rank-constant', min=1, help='Constante da rank fusion para strategy=hybrid.'),
    hybrid_lexical_weight: float = typer.Option(DEFAULT_HYBRID_LEXICAL_WEIGHT, '--hybrid-lexical-weight', min=0.0, help='Peso do ranking lexical para strategy=hybrid.'),
    hybrid_vector_weight: float = typer.Option(DEFAULT_HYBRID_VECTOR_WEIGHT, '--hybrid-vector-weight', min=0.0, help='Peso do ranking vetorial para strategy=hybrid.'),
    hybrid_lexical_pool: int | None = typer.Option(None, '--hybrid-lexical-pool', min=1, help='Pool lexical candidato para strategy=hybrid.'),
    hybrid_vector_pool: int | None = typer.Option(None, '--hybrid-vector-pool', min=1, help='Pool vetorial candidato para strategy=hybrid.'),
    export: bool = typer.Option(False, '--export', help="Exporta JSON e CSV em data/results."),
) -> None:
    """Compara lexical, vector e hybrid em uma suíte de documentos e datasets."""
    settings = get_settings()
    ensure_runtime_dirs(settings)
    suite = load_benchmark_suite(suite_path)
    resolved_embedding_model = embedding_model or settings.embedding_model
    try:
        validate_runtime_embedding_model(resolved_embedding_model)
    except EmbeddingConfigurationError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from None
    compare_dir = benchmark_compare_dir(settings.results_dir, suite.suite_name)
    connection = init_sqlite(compare_dir / 'benchmark.sqlite3')
    vector_store = LocalVectorStore(compare_dir, collection_name=f'{suite.suite_name}_compare')
    embedder = get_embedder(resolved_embedding_model, device=settings.embedding_device)

    try:
        result = compare_benchmark_suite(
            suite,
            workspace_dir=settings.workspace_dir,
            connection=connection,
            top_k=top_k,
            chunk_size=chunk_size,
            overlap=overlap,
            vector_store=vector_store,
            embedder=embedder,
            hybrid_rank_constant=hybrid_rank_constant,
            hybrid_lexical_weight=hybrid_lexical_weight,
            hybrid_vector_weight=hybrid_vector_weight,
            hybrid_lexical_pool=hybrid_lexical_pool,
            hybrid_vector_pool=hybrid_vector_pool,
            settings_snapshot=build_settings_snapshot(settings),
        )
        payload = result.model_dump(mode='json')
        if export:
            output_base = settings.results_dir / result.comparison_id
            json_path = export_benchmark_comparison_json(result, output_base.with_suffix('.json'))
            csv_path = export_benchmark_comparison_csv(result, output_base.with_suffix('.csv'))
            payload['json_report_path'] = str(json_path)
            payload['csv_report_path'] = str(csv_path)
        typer.echo(json.dumps(payload, ensure_ascii=True, indent=2))
    finally:
        connection.close()
