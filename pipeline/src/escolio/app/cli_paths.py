from pathlib import Path

import typer


def compose_path(path_parts: list[str]) -> Path:
    """Recompõe um único caminho a partir dos argumentos posicionais."""
    candidate = " ".join(path_parts).strip()
    if not candidate:
        raise typer.BadParameter("PATH vazio.")
    return Path(candidate)
