from pathlib import Path

SUPPORTED_EXTENSIONS = {".txt", ".md", ".pdf"}


def validate_source_path(path: Path) -> Path:
    """Valida se o arquivo existe e se a extensão é suportada na fase textual."""
    if not path.exists() or not path.is_file():
        raise FileNotFoundError(f"Arquivo não encontrado: {path}")
    if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
        raise ValueError(f"Extensão não suportada nesta fase: {path.suffix}")
    return path
