import typer
from rich.console import Console

from free_plaud.app.cli_paths import compose_path
from free_plaud.ingest.loaders import load_document
from free_plaud.notes.structurer import structure_document

app = typer.Typer(help="Comandos para estruturação de notas.", no_args_is_help=True)
console = Console()


@app.command("build")
def build(path_parts: list[str] = typer.Argument(..., metavar="PATH")) -> None:
    """Gera uma nota estruturada a partir de um arquivo."""
    path = compose_path(path_parts)
    document = load_document(path)
    note = structure_document(document)
    console.print(note.structured_markdown)
