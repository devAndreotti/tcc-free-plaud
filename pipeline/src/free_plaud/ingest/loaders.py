from pathlib import Path

from free_plaud.ingest.models import IngestedDocument
from free_plaud.ingest.validators import validate_source_path


def load_document(path: Path) -> IngestedDocument:
    """Carrega o conteúdo textual básico do artefato de entrada.

    Nesta primeira base, `.txt` e `.md` são lidos diretamente.
    Para `.pdf`, o scaffold registra um placeholder para a futura extração.
    """
    validated = validate_source_path(path)
    suffix = validated.suffix.lower()

    if suffix in {".txt", ".md"}:
        raw_text = validated.read_text(encoding="utf-8")
    else:
        raw_text = f"[pdf-placeholder] Extração futura para: {validated.name}"

    return IngestedDocument(
        source_path=validated,
        source_type=suffix.removeprefix('.'),
        raw_text=raw_text.strip(),
    )
