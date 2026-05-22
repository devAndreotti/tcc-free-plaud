from pathlib import Path

import typer
from rich.console import Console

from free_plaud.app.config import Settings, get_settings
from free_plaud.app.paths import ensure_runtime_dirs
from free_plaud.benchmark.cli import app as benchmark_app
from free_plaud.corpus.cli import app as corpus_app
from free_plaud.ingest.cli import app as ingest_app
from free_plaud.notes.cli import app as notes_app
from free_plaud.retrieval.cli import app as retrieval_app
from free_plaud.storage.cli import app as storage_app
from free_plaud.terminal_menu import run_terminal_menu

app = typer.Typer(
    help="CLI principal do backend experimental free-plaud.",
    no_args_is_help=True,
    pretty_exceptions_enable=False,
)
console = Console()

app.add_typer(ingest_app, name="ingest")
app.add_typer(notes_app, name="notes")
app.add_typer(retrieval_app, name="retrieval")
app.add_typer(benchmark_app, name="benchmark")
app.add_typer(storage_app, name="storage")
app.add_typer(corpus_app, name="corpus")


@app.command("doctor")
def doctor() -> None:
    """Exibe um resumo do ambiente local configurado para o backend."""
    settings = get_settings()
    ensure_runtime_dirs(settings)
    rows = {
        "environment": settings.environment,
        "workspace_dir": str(settings.workspace_dir),
        "data_dir": str(settings.data_dir),
        "notes_dir": str(settings.notes_dir),
        "datasets_dir": str(settings.datasets_dir),
        "results_dir": str(settings.results_dir),
        "vector_store_dir": str(settings.vector_store_dir),
        "vector_collection_name": settings.vector_collection_name,
        "embedding_model": settings.embedding_model,
        "sqlite_path": str(settings.sqlite_path),
        "default_chunk_size": str(settings.default_chunk_size),
        "default_chunk_overlap": str(settings.default_chunk_overlap),
    }
    for key, value in rows.items():
        console.print(f"[bold]{key}[/bold]: {value}")


@app.command("tree")
def tree(base: Path | None = None) -> None:
    """Mostra os diretórios principais usados pelo backend."""
    settings = get_settings()
    target = base or settings.workspace_dir
    console.print(f"[bold]workspace[/bold]: {target}")
    for child in sorted(target.iterdir()):
        console.print(f"- {child.name}")


@app.command("menu")
def menu() -> None:
    """Abre um menu numerado para operar corpus, ask e benchmark no terminal."""
    run_terminal_menu()
