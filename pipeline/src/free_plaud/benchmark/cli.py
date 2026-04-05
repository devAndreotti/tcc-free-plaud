from pathlib import Path

import typer
from rich.console import Console

from free_plaud.benchmark.datasets import demo_dataset
from free_plaud.benchmark.runners import run_demo_benchmark
from free_plaud.ingest.loaders import load_document
from free_plaud.notes.structurer import structure_document

app = typer.Typer(help="Comandos de benchmark experimental.", no_args_is_help=True)
console = Console()


@app.command("run-demo")
def run_demo(path: Path) -> None:
    """Executa um benchmark mínimo em cima de um único documento."""
    document = load_document(path)
    note = structure_document(document)
    results = run_demo_benchmark(note, demo_dataset())
    for row in results:
        console.print(row)
