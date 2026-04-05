from pathlib import Path


def build_note_id(path: Path) -> str:
    """Gera um identificador simples e estável a partir do nome do arquivo."""
    return path.stem.lower().replace(' ', '-').replace('_', '-')
