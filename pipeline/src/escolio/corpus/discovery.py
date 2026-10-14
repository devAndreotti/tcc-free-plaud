from pathlib import Path

from escolio.corpus.models import CorpusDiscoveryResult, CorpusSkippedPath
from escolio.ingest.validators import SUPPORTED_EXTENSIONS

IGNORED_DIR_NAMES = {'.git', '.venv', '__pycache__', 'node_modules'}
IGNORED_PATH_SUFFIXES = {
    ('data', 'results', 'vector_store'),
}


def _is_ignored_dir(path: Path) -> bool:
    if path.name in IGNORED_DIR_NAMES:
        return True
    parts = tuple(part.lower() for part in path.parts)
    return any(parts[-len(suffix) :] == suffix for suffix in IGNORED_PATH_SUFFIXES if len(parts) >= len(suffix))


def _skip(path: Path, reason: str) -> CorpusSkippedPath:
    return CorpusSkippedPath(path=str(path), reason=reason)


def discover_corpus_files(directory: Path | str, *, recursive: bool = False) -> CorpusDiscoveryResult:
    """Descobre arquivos suportados em uma pasta de forma deterministica."""
    root = Path(directory).expanduser()
    files: list[Path] = []
    skipped: list[CorpusSkippedPath] = []

    if not root.exists() or not root.is_dir():
        return CorpusDiscoveryResult(root_path=str(root), recursive=recursive, skipped=[_skip(root, 'directory_not_found')])

    if not recursive:
        for child in sorted(root.iterdir(), key=lambda item: str(item).lower()):
            if child.is_dir():
                skipped.append(_skip(child, 'directory_requires_recursive'))
            elif child.suffix.lower() in SUPPORTED_EXTENSIONS:
                files.append(child)
            else:
                skipped.append(_skip(child, 'unsupported_extension'))
        return CorpusDiscoveryResult(root_path=str(root), recursive=recursive, files=files, skipped=skipped)

    pending = [root]
    while pending:
        current = pending.pop(0)
        for child in sorted(current.iterdir(), key=lambda item: str(item).lower()):
            if child.is_dir():
                if _is_ignored_dir(child):
                    skipped.append(_skip(child, 'ignored_directory'))
                else:
                    pending.append(child)
                continue
            if child.suffix.lower() in SUPPORTED_EXTENSIONS:
                files.append(child)
            else:
                skipped.append(_skip(child, 'unsupported_extension'))

    return CorpusDiscoveryResult(root_path=str(root), recursive=recursive, files=files, skipped=skipped)
