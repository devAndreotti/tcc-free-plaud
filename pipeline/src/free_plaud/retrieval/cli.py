from pathlib import Path

import typer
from rich.console import Console

from free_plaud.ingest.loaders import load_document
from free_plaud.notes.structurer import structure_document
from free_plaud.retrieval.indexer import index_note

app = typer.Typer(help="Comandos de chunking, indexação e recuperação.", no_args_is_help=True)
console = Console()


@app.command("chunks")
def chunks(path: Path, chunk_size: int = 800, overlap: int = 120) -> None:
    """Gera chunks a partir de um documento local."""
    document = load_document(path)
    note = structure_document(document)
    generated = index_note(note, chunk_size=chunk_size, overlap=overlap)
    for chunk in generated:
        console.print(f"[bold]{chunk.chunk_id}[/bold] ({chunk.token_count} tokens) -> {chunk.chunk_text[:120]}")
