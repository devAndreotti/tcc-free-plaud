from pathlib import Path


def discover_files(directory: Path) -> list[Path]:
    """Descobre arquivos em um diretório sem recursão profunda.

    Este helper serve como ponto inicial para um futuro monitor de pasta.
    """
    if not directory.exists():
        return []
    return [path for path in sorted(directory.iterdir()) if path.is_file()]
