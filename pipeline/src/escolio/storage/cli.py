import typer
from rich.console import Console

from escolio.app.config import get_settings
from escolio.app.paths import ensure_runtime_dirs
from escolio.storage.sqlite import init_sqlite
from escolio.storage.vector import LocalVectorStore

app = typer.Typer(help="Comandos de persistência local.", no_args_is_help=True)
console = Console()


@app.command("init")
def init() -> None:
    """Inicializa diretórios locais usados pelo backend."""
    settings = get_settings()
    ensure_runtime_dirs(settings)
    connection = init_sqlite(settings.sqlite_path)
    vector_store = LocalVectorStore(settings.vector_store_dir)
    console.print(f"sqlite: {settings.sqlite_path}")
    console.print(f"sqlite_ok: {settings.sqlite_path.exists()}")
    console.print(f"vector_store_ok: {vector_store.healthcheck()}")
    connection.close()
