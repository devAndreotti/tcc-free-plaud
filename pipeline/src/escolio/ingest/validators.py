from pathlib import Path

from escolio.ingest.models import IngestedDocument
from escolio.ingest.obsidian_cleaner import extract_frontmatter

AUDIO_EXTENSIONS = {".wav", ".mp3", ".m4a", ".ogg"}
SUPPORTED_EXTENSIONS = {".txt", ".md", ".pdf"} | AUDIO_EXTENSIONS


def has_indexable_content(document: IngestedDocument) -> bool:
    """Indica se o documento tem texto útil. Em Markdown, o frontmatter YAML não conta."""
    text = document.raw_text
    if document.source_path.suffix.lower() == ".md":
        _, text = extract_frontmatter(text)
    return bool(text.strip())


def validate_source_path(path: Path) -> Path:
    """Valida se o arquivo existe e se a extensão é suportada na fase textual."""
    if not path.exists() or not path.is_file():
        raise FileNotFoundError(f"Arquivo não encontrado: {path}")
    if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
        raise ValueError(f"Extensão não suportada nesta fase: {path.suffix}")
    return path
