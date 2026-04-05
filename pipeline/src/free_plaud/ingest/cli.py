from pathlib import Path

import typer
from rich.console import Console

from free_plaud.ingest.loaders import load_document

app = typer.Typer(help="Comandos de ingestão de artefatos locais.", no_args_is_help=True)
console = Console()


@app.command("show")
def show(path: Path) -> None:
    """Carrega um documento e mostra um resumo da entrada bruta."""
    document = load_document(path)
    console.print(f"[bold]source[/bold]: {document.source_path}")
    console.print(f"[bold]type[/bold]: {document.source_type}")
    console.print(f"[bold]chars[/bold]: {len(document.raw_text)}")
    preview = document.raw_text[:300] or "<vazio>"
    console.print(f"[bold]preview[/bold]: {preview}")
