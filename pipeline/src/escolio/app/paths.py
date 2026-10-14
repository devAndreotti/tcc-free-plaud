from pathlib import Path

from escolio.app.config import Settings


def ensure_runtime_dirs(settings: Settings) -> None:
    """Cria a estrutura mínima de diretórios usada pelo backend."""
    required_dirs: tuple[Path, ...] = (
        settings.data_dir,
        settings.notes_dir,
        settings.datasets_dir,
        settings.results_dir,
        settings.vector_store_dir,
    )
    for directory in required_dirs:
        directory.mkdir(parents=True, exist_ok=True)
