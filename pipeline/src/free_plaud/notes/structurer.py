from hashlib import sha256
import re

from free_plaud.ingest.models import IngestedDocument
from free_plaud.notes.markdown import render_note_markdown
from free_plaud.notes.metadata import build_note_id
from free_plaud.notes.normalizer import normalize_text
from free_plaud.notes.schemas import Note


def _normalize_title(raw_title: str, fallback: str) -> str:
    title = raw_title.lstrip('#').strip()
    return title or fallback


def _is_heading_block(block: str) -> bool:
    lines = [line.strip() for line in block.splitlines() if line.strip()]
    return bool(lines) and all(line.startswith('#') for line in lines)


def _is_table_block(block: str) -> bool:
    lines = [line.strip() for line in block.splitlines() if line.strip()]
    return bool(lines) and all(line.startswith('|') for line in lines)


def _is_bullet_block(block: str) -> bool:
    lines = [line.strip() for line in block.splitlines() if line.strip()]
    return bool(lines) and all(line.startswith(('- ', '* ', '+ ')) for line in lines)


def _extract_summary(normalized_text: str, has_markdown_title: bool) -> str:
    blocks = [block.strip() for block in re.split(r'\n\s*\n', normalized_text) if block.strip()]
    if has_markdown_title:
        for block in blocks:
            if _is_heading_block(block) or _is_table_block(block) or _is_bullet_block(block):
                continue
            return block.splitlines()[0][:240]

    lines = [line.strip() for line in normalized_text.splitlines() if line.strip()]
    if len(lines) > 1:
        return lines[1][:240]
    if lines:
        return lines[0][:240]
    return ""


def structure_document(document: IngestedDocument) -> Note:
    """Transforma um documento bruto em uma nota estruturada mínima.

    Este comportamento é determinístico e serve como placeholder para a futura
    etapa de estruturação assistida por LLM.
    """
    normalized_text = normalize_text(document.raw_text)
    lines = [line.strip() for line in normalized_text.splitlines() if line.strip()]
    first_line = lines[0] if lines else ""
    has_markdown_title = first_line.startswith('#')
    title = _normalize_title(first_line, document.source_path.stem)[:80] if lines else document.source_path.stem
    summary = _extract_summary(normalized_text, has_markdown_title)
    note = Note(
        note_id=build_note_id(document.source_path),
        source_type=document.source_type,
        source_path=document.source_path,
        source_name=document.source_path.name,
        title=title,
        summary=summary,
        topics=[],
        tasks=[],
        tags=[document.source_type],
        raw_text=document.raw_text,
        normalized_text=normalized_text,
        structured_markdown="",
        content_hash=sha256(normalized_text.encode('utf-8')).hexdigest(),
    )
    note.structured_markdown = render_note_markdown(note)
    return note
