import typer

from escolio.app.config import base_settings
from escolio.app.vaults import VaultError, load_registry, set_active

app = typer.Typer(help="Vaults (corpora independentes): lista e troca a vault ativa.", no_args_is_help=True)


@app.command("list")
def list_vaults() -> None:
    registry = load_registry(base_settings())
    for vault in registry.vaults:
        marker = "*" if vault.id == registry.active else " "
        typer.echo(f"{marker} {vault.id}\t{vault.name}\t{vault.icon}\t{vault.color}")


@app.command("use")
def use_vault(vault_id: str = typer.Argument(..., help="Id da vault (ver `escolio vault list`).")) -> None:
    try:
        vault = set_active(vault_id, base_settings())
    except VaultError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(f"Vault ativa: {vault.id} ({vault.name})")
