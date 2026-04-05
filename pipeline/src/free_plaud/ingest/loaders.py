from pathlib import Path

from pypdf import PdfReader

from free_plaud.ingest.models import IngestedDocument
from free_plaud.ingest.validators import validate_source_path


def _extract_pdf_text(path: Path) -> str:
    reader = PdfReader(str(path))
    chunks: list[str] = []

    for page in reader.pages:
        page_text = page.extract_text() or ""
        normalized = page_text.strip()
        if normalized:
            chunks.append(normalized)

    return "\n\n".join(chunks).strip()


def load_document(path: Path) -> IngestedDocument:
    """Carrega o conteúdo textual básico do artefato de entrada.

    Nesta fase textual, `.txt` e `.md` são lidos diretamente e `.pdf`
    utiliza extração local baseada em `pypdf`.
    """
    validated = validate_source_path(path)
    suffix = validated.suffix.lower()

    if suffix in {".txt", ".md"}:
        raw_text = validated.read_text(encoding="utf-8")
    else:
        raw_text = _extract_pdf_text(validated)

    return IngestedDocument(
        source_path=validated,
        source_type=suffix.removeprefix('.'),
        raw_text=raw_text.strip(),
    )
