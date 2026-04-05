from free_plaud.ingest.models import IngestedDocument
from free_plaud.notes.markdown import render_note_markdown
from free_plaud.notes.metadata import build_note_id
from free_plaud.notes.schemas import Note


def _normalize_title(raw_title: str, fallback: str) -> str:
    title = raw_title.lstrip('#').strip()
    return title or fallback


def structure_document(document: IngestedDocument) -> Note:
    """Transforma um documento bruto em uma nota estruturada mínima.

    Este comportamento é determinístico e serve como placeholder para a futura
    etapa de estruturação assistida por LLM.
    """
    lines = [line.strip() for line in document.raw_text.splitlines() if line.strip()]
    title = _normalize_title(lines[0], document.source_path.stem)[:80] if lines else document.source_path.stem
    summary = lines[1][:240] if len(lines) > 1 else (lines[0][:240] if lines else "")
    note = Note(
        note_id=build_note_id(document.source_path),
        source_type=document.source_type,
        source_path=document.source_path,
        title=title,
        summary=summary,
        topics=[],
        tasks=[],
        tags=[document.source_type],
        raw_text=document.raw_text,
        structured_markdown="",
    )
    note.structured_markdown = render_note_markdown(note)
    return note
