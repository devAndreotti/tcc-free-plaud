from pathlib import Path

import typer
from rich.console import Console

from free_plaud.ingest.service import ingest_file

app = typer.Typer(help="Comandos de ingestão de artefatos locais.", no_args_is_help=True)
console = Console()


@app.command("show")
def show(path: Path) -> None:
    """Executa a ingestão e mostra um resumo rastreável do resultado."""
    result = ingest_file(path)
    console.print(f"[bold]ingestion_id[/bold]: {result.ingestion_id}")
    console.print(f"[bold]correlation_id[/bold]: {result.correlation_id}")
    console.print(f"[bold]source[/bold]: {result.source_path}")
    console.print(f"[bold]status[/bold]: {result.status}")
    console.print(f"[bold]source_type[/bold]: {result.source_type}")
    console.print(f"[bold]media_type[/bold]: {result.detected_media_type}")
    console.print(f"[bold]size_bytes[/bold]: {result.size_bytes}")
    console.print(f"[bold]content_sha256[/bold]: {result.content_sha256}")
    preview = result.raw_text[:300] or "<vazio>"
    console.print(f"[bold]preview[/bold]: {preview}")
    if result.status == 'failed':
        console.print(f"[bold red]error_code[/bold red]: {result.error_code}")
        raise typer.Exit(code=1)
