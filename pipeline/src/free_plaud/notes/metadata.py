from pathlib import Path
from hashlib import sha256
import re
import unicodedata


def _slug_from_stem(path: Path) -> str:
    normalized = unicodedata.normalize('NFKD', path.stem)
    ascii_only = normalized.encode('ascii', 'ignore').decode('ascii')
    slug = re.sub(r'[^a-zA-Z0-9]+', '-', ascii_only.lower())
    return slug.strip('-') or 'note'


def _relative_path_key(path: Path, root_path: Path) -> str:
    resolved_path = path.resolve()
    resolved_root = root_path.resolve()
    try:
        relative_path = resolved_path.relative_to(resolved_root)
    except ValueError:
        relative_path = resolved_path
    normalized = unicodedata.normalize('NFKC', relative_path.as_posix()).lower()
    return re.sub(r'/+', '/', normalized)


def build_note_id(path: Path, *, root_path: Path | None = None) -> str:
    """Gera ID de nota estavel; em corpus usa caminho relativo para evitar colisao."""
    slug = _slug_from_stem(path)
    if root_path is None:
        return slug
    path_hash = sha256(_relative_path_key(path, root_path).encode('utf-8')).hexdigest()[:10]
    return f'{slug}--{path_hash}'
