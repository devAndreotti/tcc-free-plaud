import typer
from rich.console import Console

from escolio.app.cli_paths import compose_path
from escolio.app.config import get_settings
from escolio.app.paths import ensure_runtime_dirs
from escolio.ingest.loaders import load_document
from escolio.notes.repository import save_note_locally
from escolio.notes.structurer import structure_document

app = typer.Typer(help="Comandos para estruturação de notas.", no_args_is_help=True)
console = Console()


@app.command("build")
def build(path_parts: list[str] = typer.Argument(..., metavar="PATH")) -> None:
    """Gera uma nota estruturada a partir de um arquivo."""
    path = compose_path(path_parts)
    document = load_document(path)
    note = structure_document(document)
    console.print(note.structured_markdown)


@app.command("save")
def save(path_parts: list[str] = typer.Argument(..., metavar="PATH")) -> None:
    """Gera uma nota estruturada e persiste os artefatos localmente."""
    settings = get_settings()
    ensure_runtime_dirs(settings)
    path = compose_path(path_parts)
    document = load_document(path)
    note = structure_document(document)
    artifact = save_note_locally(note, settings.notes_dir)
    console.print(f"[bold]note_id[/bold]: {note.note_id}")
    console.print(f"[bold]note_path[/bold]: {artifact.note_path}")
    console.print(f"[bold]meta_path[/bold]: {artifact.meta_path}")
