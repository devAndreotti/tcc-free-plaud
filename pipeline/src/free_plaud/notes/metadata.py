from pathlib import Path
import re
import unicodedata


def build_note_id(path: Path) -> str:
    """Gera um identificador simples e estável a partir do nome do arquivo."""
    normalized = unicodedata.normalize('NFKD', path.stem)
    ascii_only = normalized.encode('ascii', 'ignore').decode('ascii')
    slug = re.sub(r'[^a-zA-Z0-9]+', '-', ascii_only.lower())
    return slug.strip('-') or 'note'
