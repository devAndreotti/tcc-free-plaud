from pathlib import Path

import typer
from rich.console import Console

from escolio.app.config import get_settings
from escolio.app.doctor import run_doctor
from escolio.app.doctor_format import doctor_report_lines
from escolio.app.paths import ensure_runtime_dirs
from escolio.benchmark.cli import app as benchmark_app
from escolio.config_cli import app as config_app
from escolio.corpus.cli import app as corpus_app
from escolio.ingest.cli import app as ingest_app
from escolio.notes.cli import app as notes_app
from escolio.providers.cli import app as provider_app
from escolio.retrieval.cli import app as retrieval_app
from escolio.storage.cli import app as storage_app
from escolio.terminal_menu import run_terminal_menu
from escolio.vault_cli import app as vault_app

app = typer.Typer(
    help="CLI principal do backend experimental Escólio.",
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
app.add_typer(config_app, name="config")
app.add_typer(vault_app, name="vault")
app.add_typer(provider_app, name="provider")


@app.command("doctor")
def doctor(
    fix: bool = typer.Option(False, "--fix", help="Aplica auto-fix com preset cpu_rapido se embedding_model for fake-hash."),
) -> None:
    """Exibe diagnostico estruturado do ambiente local."""
    settings = get_settings()
    ensure_runtime_dirs(settings)
    if fix and settings.embedding_model == "fake-hash":
        from escolio.app.settings_presets import apply_settings_preset
        apply_settings_preset("cpu_rapido", settings=settings)
        console.print("[green][OK][/green] Preset [bold]cpu_rapido[/bold] aplicado com sucesso.")
        settings = get_settings()
    report = run_doctor(settings=settings)
    for line in doctor_report_lines(report):
        console.print(line)


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


@app.command("tui")
def tui() -> None:
    """Abre a TUI Textual do Escólio."""
    from escolio.tui.app import main as run_tui

    run_tui()



if __name__ == "__main__":
    app()
