from hashlib import sha256
import re
import unicodedata

from free_plaud.ingest.models import IngestedDocument
from free_plaud.notes.markdown import render_note_markdown
from free_plaud.notes.metadata import build_note_id
from free_plaud.notes.normalizer import normalize_text
from free_plaud.notes.schemas import Note

GENERIC_TITLE_TERMS = {
    'todo',
    'requisitos',
    'documento',
    'notas',
    'rascunho',
}

PREFERRED_SUMMARY_HEADINGS = {
    'resumo',
    'sumario executivo',
    'visao geral',
    'contexto',
    'introducao',
    'objetivo',
    'objetivo da reuniao',
}

KNOWN_METADATA_LABELS = {
    'versao',
    'tipo',
    'autor',
    'autores',
    'data',
    'horario',
    'local',
    'facilitador',
    'participantes',
    'afiliacao',
    'evento',
    'area',
    'projeto',
    'confidencialidade',
    'aprovacao',
    'comeco',
}


def _normalize_title(raw_title: str, fallback: str) -> str:
    title = raw_title.lstrip('#').strip()
    return title or fallback


def _strip_inline_markdown(text: str) -> str:
    cleaned = re.sub(r'^\s*#{1,6}\s*', '', text.strip())
    cleaned = re.sub(r'^\s*[-*+]\s+\[[ xX]\]\s*', '', cleaned)
    cleaned = cleaned.replace('**', '').replace('__', '').replace('`', '')
    return re.sub(r'\s+', ' ', cleaned).strip()


def _normalize_for_match(text: str) -> str:
    normalized = unicodedata.normalize('NFKD', _strip_inline_markdown(text))
    ascii_only = normalized.encode('ascii', 'ignore').decode('ascii')
    return re.sub(r'[^a-zA-Z0-9]+', ' ', ascii_only.lower()).strip()


def _humanize_fallback_title(fallback: str) -> str:
    candidate = re.sub(r'[-_]+', ' ', fallback.strip())
    return re.sub(r'\s+', ' ', candidate).strip() or 'note'


def _is_markdown_h1_line(line: str) -> bool:
    return re.match(r'^\s*#\s+\S', line.strip()) is not None


def _is_heading_line(line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return False
    if re.match(r'^\s*#{1,6}\s+\S', stripped):
        return True
    letters = re.sub(r'[^A-Za-zÀ-ÿ]+', '', stripped)
    return bool(letters) and len(stripped) <= 80 and stripped == stripped.upper() and ':' not in stripped


def _is_horizontal_rule_line(line: str) -> bool:
    return re.match(r'^\s*[-*_]{3,}\s*$', line.strip()) is not None


def _is_table_line(line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return False
    return stripped.startswith('|') or re.match(r'^\s*\|?[-: ]+\|[-|: ]*\s*$', stripped) is not None


def _is_bullet_line(line: str) -> bool:
    stripped = line.strip()
    return re.match(r'^([-*+]|\d+[.)])\s+', stripped) is not None or re.match(r'^[-*+]\s+\[[ xX]\]\s*', stripped) is not None


def _looks_like_metadata_line(line: str) -> bool:
    stripped = _strip_inline_markdown(line)
    if not stripped or len(stripped) > 120 or ':' not in stripped:
        return False
    label, value = stripped.split(':', 1)
    normalized_label = _normalize_for_match(label)
    if not normalized_label or not value.strip():
        return False
    if normalized_label in KNOWN_METADATA_LABELS:
        return True
    return len(stripped) <= 80 and len(normalized_label.split()) <= 4


def _looks_generic_title(title: str) -> bool:
    return _normalize_for_match(title) in GENERIC_TITLE_TERMS


def _finalize_title(candidate: str, fallback: str) -> str:
    stripped = candidate.strip()
    if (
        not stripped
        or _is_table_line(stripped)
        or _is_horizontal_rule_line(stripped)
        or _is_bullet_line(stripped)
        or (
            _looks_like_metadata_line(stripped)
            and not _is_heading_line(stripped)
            and not _is_markdown_h1_line(stripped)
        )
    ):
        return ""
    title = _normalize_title(_strip_inline_markdown(stripped), fallback)
    if _looks_generic_title(title):
        return fallback
    return title[:140]


def _choose_first_substantive_title(lines: list[str], fallback: str) -> tuple[int, str]:
    for index, line in enumerate(lines):
        stripped = line.strip()
        title = _finalize_title(stripped, fallback)
        if title:
            return index, title

    return -1, fallback


def _choose_title(lines: list[str], fallback: str, source_type: str) -> tuple[int, str]:
    if source_type == 'md':
        for index, line in enumerate(lines):
            if _is_markdown_h1_line(line):
                title = _finalize_title(line, fallback)
                if title:
                    return index, title

        for index, line in enumerate(lines):
            if _is_heading_line(line):
                title = _finalize_title(line, fallback)
                if title:
                    return index, title

        return _choose_first_substantive_title(lines, fallback)

    return _choose_first_substantive_title(lines, fallback)


def _heading_key(line: str) -> str:
    key = _normalize_for_match(line)
    return re.sub(r'^\d+(\s+\d+)*\s*', '', key).strip()


def _is_preferred_summary_heading(line: str) -> bool:
    key = _heading_key(line)
    return key in PREFERRED_SUMMARY_HEADINGS


def _is_useful_summary(candidate: str) -> bool:
    words = candidate.split()
    return len(candidate) >= 40 and len(words) >= 6


def _collect_candidate_paragraph(lines: list[str], start_index: int) -> str:
    fallback = ""
    index = max(start_index, 0)
    while index < len(lines):
        current = lines[index].strip()
        if not current:
            index += 1
            continue
        if (
            _is_heading_line(current)
            or _is_table_line(current)
            or _is_horizontal_rule_line(current)
            or _is_bullet_line(current)
            or _looks_like_metadata_line(current)
        ):
            index += 1
            continue

        paragraph_lines = [_strip_inline_markdown(current)]
        index += 1
        while index < len(lines):
            following = lines[index].strip()
            if not following:
                break
            if (
                _is_heading_line(following)
                or _is_table_line(following)
                or _is_horizontal_rule_line(following)
                or _is_bullet_line(following)
                or _looks_like_metadata_line(following)
            ):
                break
            paragraph_lines.append(_strip_inline_markdown(following))
            index += 1

        candidate = ' '.join(part for part in paragraph_lines if part).strip()
        if candidate and _is_useful_summary(candidate):
            return candidate[:240]
        if candidate and not fallback:
            fallback = candidate[:240]
        index += 1

    return fallback


def _extract_summary(lines: list[str], title_index: int) -> str:
    start_index = max(title_index + 1, 0)
    for index in range(start_index, len(lines)):
        line = lines[index].strip()
        if _is_heading_line(line) and _is_preferred_summary_heading(line):
            candidate = _collect_candidate_paragraph(lines, index + 1)
            if candidate:
                return candidate

    candidate = _collect_candidate_paragraph(lines, start_index)
    if candidate:
        return candidate

    return _collect_candidate_paragraph(lines, 0)


def structure_document(document: IngestedDocument) -> Note:
    """Transforma um documento bruto em uma nota estruturada mínima.

    Este comportamento é determinístico e serve como placeholder para a futura
    etapa de estruturação assistida por LLM.
    """
    normalized_text = normalize_text(document.raw_text)
    lines = normalized_text.splitlines()
    fallback_title = _humanize_fallback_title(document.source_path.stem)
    title_index, title = _choose_title(lines, fallback_title, document.source_type)
    summary = _extract_summary(lines, title_index)
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
