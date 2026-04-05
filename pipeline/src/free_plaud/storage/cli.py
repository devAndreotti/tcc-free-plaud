import typer
from rich.console import Console

from free_plaud.app.config import get_settings
from free_plaud.app.paths import ensure_runtime_dirs
from free_plaud.storage.vector import LocalVectorStore

app = typer.Typer(help="Comandos de persistência local.", no_args_is_help=True)
console = Console()


@app.command("init")
def init() -> None:
    """Inicializa diretórios locais usados pelo backend."""
    settings = get_settings()
    ensure_runtime_dirs(settings)
    vector_store = LocalVectorStore(settings.vector_store_dir)
    console.print(f"sqlite: {settings.sqlite_path}")
    console.print(f"vector_store_ok: {vector_store.healthcheck()}")
