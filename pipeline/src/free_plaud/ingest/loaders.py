from pathlib import Path

from pypdf import PdfReader
from pypdf.errors import PyPdfError

from free_plaud.ingest.models import IngestedDocument
from free_plaud.ingest.validators import AUDIO_EXTENSIONS, validate_source_path

PDF_PARSE_FAILED = "PDF_PARSE_FAILED"


def _extract_pdf_text(path: Path) -> str:
    try:
        reader = PdfReader(str(path))
    except (PyPdfError, OSError) as exc:
        raise ValueError(PDF_PARSE_FAILED) from exc

    chunks: list[str] = []

    try:
        for page in reader.pages:
            page_text = page.extract_text() or ""
            normalized = page_text.strip()
            if normalized:
                chunks.append(normalized)
    except PyPdfError as exc:
        raise ValueError(PDF_PARSE_FAILED) from exc

    return "\n\n".join(chunks).strip()


def load_document(path: Path) -> IngestedDocument:
    """Carrega o conteúdo textual básico do artefato de entrada.

    Nesta fase textual, `.txt` e `.md` são lidos diretamente e `.pdf`
    utiliza extração local baseada em `pypdf`.
    """
    validated = validate_source_path(path)
    suffix = validated.suffix.lower()

    if suffix in AUDIO_EXTENSIONS:
        from free_plaud.app.audio_service import audio_options, audio_runtime

        result = audio_runtime().transcribe_result(validated, audio_options())
        return IngestedDocument(
            source_path=validated,
            source_type=suffix.removeprefix("."),
            raw_text=result.raw_text,
            cleaned_text=result.text,
            transcription_path=result.artifact_path,
        )
    elif suffix in {".txt", ".md"}:
        raw_text = validated.read_text(encoding="utf-8")
    else:
        raw_text = _extract_pdf_text(validated)

    return IngestedDocument(
        source_path=validated,
        source_type=suffix.removeprefix("."),
        raw_text=raw_text.strip(),
    )
