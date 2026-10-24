import re
import unicodedata
from hashlib import sha256
from pathlib import Path

from escolio.ingest.models import IngestedDocument
from escolio.notes.markdown import render_note_markdown
from escolio.notes.metadata import build_note_id
from escolio.notes.normalizer import normalize_text, repair_ocr_summary_text
from escolio.notes.readable import strip_frontmatter
from escolio.notes.schemas import Note
from escolio.retrieval.chunking import build_segment_text

GENERIC_TITLE_TERMS = {
    "todo",
    "requisitos",
    "documento",
    "notas",
    "rascunho",
    "sumario",
    "visao geral",
    "checklist",
    "resumo rapido",
    "conceito chave",
    "introducao",
    "objetivo",
}

PREFERRED_SUMMARY_HEADINGS = {
    "resumo",
    "resumo profissional",
    "sumario executivo",
    "sumario",
    "visao geral",
    "contexto",
    "introducao",
    "objetivo",
    "objetivo da reuniao",
    "objetivo da sessao",
    "do objeto",
    "objeto",
}

KNOWN_METADATA_LABELS = {
    "versao",
    "tipo",
    "autor",
    "autores",
    "data",
    "horario",
    "local",
    "facilitador",
    "participantes",
    "afiliacao",
    "evento",
    "area",
    "projeto",
    "confidencialidade",
    "aprovacao",
    "comeco",
    "contato",
    "telefone",
    "celular",
    "email",
    "linkedin",
    "github",
    "portfolio",
}


def _normalize_title(raw_title: str, fallback: str) -> str:
    title = raw_title.lstrip("#").strip()
    return title or fallback


def _strip_inline_markdown(text: str) -> str:
    cleaned = re.sub(r"^\s*#{1,6}\s*", "", text.strip())
    cleaned = re.sub(r"^\s*>\s*", "", cleaned)
    cleaned = re.sub(r"^\s*\[![^\]]+\]\s*", "", cleaned)
    cleaned = re.sub(r"^\s*[-*+]\s+\[[ xX]\]\s*", "", cleaned)
    cleaned = cleaned.replace("**", "").replace("__", "").replace("`", "")
    return re.sub(r"\s+", " ", cleaned).strip()


def _normalize_for_match(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", _strip_inline_markdown(text))
    ascii_only = normalized.encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-zA-Z0-9]+", " ", ascii_only.lower()).strip()


def _humanize_fallback_title(fallback: str) -> str:
    candidate = re.sub(r"[-_]+", " ", fallback.strip())
    return re.sub(r"\s+", " ", candidate).strip() or "note"


def _is_markdown_h1_line(line: str) -> bool:
    return re.match(r"^\s*#\s+\S", line.strip()) is not None


def _is_heading_line(line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return False
    if re.match(r"^\s*#{1,6}\s+\S", stripped):
        return True
    letters = re.sub(r"[^A-Za-zÀ-ÿ]+", "", stripped)
    return (
        bool(letters)
        and len(stripped) <= 80
        and stripped == stripped.upper()
        and ":" not in stripped
    )


def _is_horizontal_rule_line(line: str) -> bool:
    return re.match(r"^\s*[-*_]{3,}\s*$", line.strip()) is not None


def _is_blockquote_line(line: str) -> bool:
    return line.strip().startswith(">")


def _is_table_line(line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return False
    return (
        stripped.startswith("|")
        or re.match(r"^\s*\|?[-: ]+\|[-|: ]*\s*$", stripped) is not None
    )


def _is_bullet_line(line: str) -> bool:
    stripped = line.strip()
    return (
        re.match(r"^([-*+]|\d+[.)])\s+", stripped) is not None
        or re.match(r"^[-*+]\s+\[[ xX]\]\s*", stripped) is not None
    )


def _looks_like_metadata_line(line: str) -> bool:
    stripped = _strip_inline_markdown(line)
    if not stripped or len(stripped) > 120 or ":" not in stripped:
        return False
    label, value = stripped.split(":", 1)
    normalized_label = _normalize_for_match(label)
    if not normalized_label or not value.strip():
        return False
    if normalized_label in KNOWN_METADATA_LABELS:
        return True
    return len(stripped) <= 80 and len(normalized_label.split()) <= 4


def _is_salutation_line(line: str) -> bool:
    normalized = _normalize_for_match(line)
    if not normalized:
        return False
    return normalized in {
        "ola",
        "ola equipe",
        "prezado",
        "prezados",
        "prezada",
        "prezadas",
        "caro",
        "caros",
        "cara",
        "caras",
        "atenciosamente",
        "cordialmente",
    }


def _looks_like_intro_fragment(line: str) -> bool:
    stripped = _strip_inline_markdown(line)
    if not stripped:
        return False
    words = stripped.split()
    return (
        stripped[:1].islower()
        and len(words) <= 4
        and not re.search(r"[.!?;,:]", stripped)
    )


def _looks_like_sentence_title(line: str) -> bool:
    stripped = _strip_inline_markdown(line)
    words = stripped.split()
    if len(words) >= 10:
        return True
    return len(words) >= 4 and re.search(r"[.!?,:]", stripped) is not None


def _looks_like_contact_line(line: str) -> bool:
    stripped = _strip_inline_markdown(line)
    normalized = _normalize_for_match(stripped)
    if not stripped:
        return False
    if "@" in stripped:
        return True
    if stripped.count("|") >= 1 and len(stripped) <= 80:
        return True
    if normalized.startswith(("linkedin", "github", "portfolio", "contato")):
        return True
    return re.search(r"\(?\d{2}\)?\s*\d{4,5}[- ]?\d{4}", stripped) is not None


def _looks_like_signature_line(line: str) -> bool:
    stripped = _strip_inline_markdown(line).strip()
    words = stripped.rstrip(".").split()
    if not stripped.endswith(".") or not 2 <= len(words) <= 5:
        return False
    return all(word[:1].isupper() for word in words if word)


def _looks_generic_title(title: str) -> bool:
    return _normalize_for_match(title) in GENERIC_TITLE_TERMS


def _is_bare_yaml_key(line: str) -> bool:
    # "tags:" sozinho é chave de frontmatter que escapou, não título.
    return re.fullmatch(r"[a-z][\w-]*:", line.strip()) is not None


def _finalize_title(
    candidate: str, fallback: str, allow_sentence_title: bool = True
) -> str:
    stripped = candidate.strip()
    if (
        not stripped
        or _is_blockquote_line(stripped)
        or _is_table_line(stripped)
        or _is_horizontal_rule_line(stripped)
        or _is_bullet_line(stripped)
        or _is_salutation_line(stripped)
        or _looks_like_contact_line(stripped)
        or _looks_like_signature_line(stripped)
        or _is_bare_yaml_key(stripped)
        or (
            _looks_like_metadata_line(stripped)
            and not _is_heading_line(stripped)
            and not _is_markdown_h1_line(stripped)
        )
    ):
        return ""
    if not allow_sentence_title and stripped[:1].islower():
        return ""
    if not allow_sentence_title and (
        _looks_like_intro_fragment(stripped) or _looks_like_sentence_title(stripped)
    ):
        return ""
    title = _normalize_title(_strip_inline_markdown(stripped), fallback)
    if _looks_generic_title(title):
        return fallback
    return title[:140]


def _choose_first_substantive_title(
    lines: list[str],
    fallback: str,
    allow_sentence_title: bool = True,
) -> tuple[int, str]:
    for index, line in enumerate(lines):
        stripped = line.strip()
        title = _finalize_title(
            stripped, fallback, allow_sentence_title=allow_sentence_title
        )
        if title:
            continuation: list[str] = []
            probe = index + 1
            while probe < len(lines):
                next_line = lines[probe].strip()
                if not next_line:
                    break
                if (
                    _looks_like_metadata_line(next_line)
                    or _is_table_line(next_line)
                    or _is_bullet_line(next_line)
                ):
                    break
                if not _is_heading_line(next_line):
                    break
                continuation_title = _finalize_title(
                    next_line,
                    fallback,
                    allow_sentence_title=allow_sentence_title,
                )
                if not continuation_title or continuation_title == fallback:
                    break
                continuation.append(continuation_title)
                probe += 1
            if continuation:
                title = " ".join([title, *continuation])[:140]
            return index, title

    return -1, fallback


def _has_substantive_content_before_heading(
    lines: list[str], heading_index: int
) -> bool:
    if heading_index <= 0:
        return False
    candidates = _collect_candidate_paragraphs(lines[:heading_index], 0)
    return bool(candidates)


def _choose_title(
    lines: list[str], fallback: str, source_type: str, has_frontmatter: bool = False
) -> tuple[int, str]:
    if has_frontmatter:
        # Com frontmatter, só vale um H1 do corpo; sem ele, o nome do arquivo.
        # ponytail: callout ou H2 que poderia ser título fica de fora; upgrade: primeiro título não genérico.
        for index, line in enumerate(lines):
            if _is_markdown_h1_line(line):
                title = _finalize_title(line, fallback)
                if title:
                    return index, title
        return -1, fallback

    if source_type == "md":
        for index, line in enumerate(lines):
            if _is_markdown_h1_line(line):
                title = _finalize_title(line, fallback)
                if title:
                    return index, title

        heading_indexes = [
            index for index, line in enumerate(lines) if _is_heading_line(line)
        ]
        if heading_indexes and _has_substantive_content_before_heading(
            lines, heading_indexes[0]
        ):
            return -1, fallback

        if heading_indexes:
            title = _finalize_title(lines[heading_indexes[0]], fallback)
            if title and title != fallback:
                return heading_indexes[0], title
            return -1, fallback

        return _choose_first_substantive_title(lines, fallback)

    return _choose_first_substantive_title(lines, fallback, allow_sentence_title=False)


def _heading_key(line: str) -> str:
    key = _normalize_for_match(line)
    return re.sub(r"^\d+(\s+\d+)*\s*", "", key).strip()


def _is_preferred_summary_heading(line: str) -> bool:
    key = _heading_key(line)
    return key in PREFERRED_SUMMARY_HEADINGS or any(
        key.endswith(term) for term in PREFERRED_SUMMARY_HEADINGS
    )


def _is_useful_summary(candidate: str) -> bool:
    words = candidate.split()
    return len(candidate) >= 40 and len(words) >= 6


def _find_next_heading_index(lines: list[str], start_index: int) -> int:
    for index in range(max(start_index, 0), len(lines)):
        if _is_heading_line(lines[index]):
            return index
    return len(lines)


def _collect_candidate_paragraphs(
    lines: list[str], start_index: int
) -> list[tuple[int, str, bool]]:
    candidates: list[tuple[int, str, bool]] = []
    index = max(start_index, 0)
    in_code_block = False
    while index < len(lines):
        current = lines[index].strip()
        if current.startswith("```"):
            in_code_block = not in_code_block
            index += 1
            continue
        if in_code_block:
            index += 1
            continue
        if not current:
            index += 1
            continue
        if (
            _is_heading_line(current)
            or _is_table_line(current)
            or _is_horizontal_rule_line(current)
            or _is_bullet_line(current)
            or _looks_like_metadata_line(current)
            or _is_salutation_line(current)
            or _looks_like_contact_line(current)
            or _looks_like_signature_line(current)
            or _looks_like_intro_fragment(current)
        ):
            index += 1
            continue

        start = index
        is_blockquote = _is_blockquote_line(current)
        paragraph_lines = [_strip_inline_markdown(current)]
        index += 1
        while index < len(lines):
            following = lines[index].strip()
            if following.startswith("```"):
                break
            if not following:
                break
            if (
                _is_heading_line(following)
                or _is_table_line(following)
                or _is_horizontal_rule_line(following)
                or _is_bullet_line(following)
                or _looks_like_metadata_line(following)
                or _is_salutation_line(following)
                or _looks_like_contact_line(following)
                or _looks_like_signature_line(following)
            ):
                break
            paragraph_lines.append(_strip_inline_markdown(following))
            index += 1

        candidate = " ".join(part for part in paragraph_lines if part).strip()
        if candidate:
            candidates.append((start, candidate[:240], is_blockquote))
        index += 1

    return candidates


def _score_summary_candidate(
    candidate: str, title: str, is_blockquote: bool
) -> tuple[int, int]:
    normalized_candidate = _normalize_for_match(candidate)
    word_count = len(candidate.split())
    punctuation_hits = len(re.findall(r"[.!?;]", candidate))
    sentence_like = 1 if punctuation_hits > 0 else 0
    score = min(len(candidate), 240)
    score += min(word_count * 3, 45)
    score += punctuation_hits * 20
    score += sentence_like * 40
    if _is_useful_summary(candidate):
        score += 40
    if normalized_candidate == _normalize_for_match(title):
        score -= 250
    if candidate.count(" - ") >= 2 or candidate.count(" — ") >= 2:
        score -= 80
    if "pag." in normalized_candidate or "confidencial" in normalized_candidate:
        score -= 160
    if "@" in candidate or candidate.count("|") >= 2:
        score -= 220
    if candidate.startswith(("```", "def ", "class ")):
        score -= 240
    if is_blockquote:
        score -= 120
    return score, len(candidate)


def _choose_best_summary(candidates: list[tuple[int, str, bool]], title: str) -> str:
    if not candidates:
        return ""
    ranked = sorted(
        candidates,
        key=lambda item: (_score_summary_candidate(item[1], title, item[2]), -item[0]),
        reverse=True,
    )
    return ranked[0][1]


def _extract_summary(lines: list[str], title_index: int, title: str) -> str:
    start_index = max(title_index + 1, 0)

    intro_window_end = _find_next_heading_index(lines, start_index)
    intro_candidates = _collect_candidate_paragraphs(
        lines[:intro_window_end], start_index
    )
    intro_candidate = _choose_best_summary(intro_candidates, title)
    if intro_candidate and _is_useful_summary(intro_candidate):
        return intro_candidate

    for index in range(start_index, len(lines)):
        line = lines[index].strip()
        if _is_heading_line(line) and _is_preferred_summary_heading(line):
            candidates = _collect_candidate_paragraphs(lines, index + 1)
            if candidates:
                candidate = candidates[0][1]
                return candidate

    candidate = _choose_best_summary(
        _collect_candidate_paragraphs(lines, start_index), title
    )
    if candidate:
        return candidate

    return _choose_best_summary(_collect_candidate_paragraphs(lines, 0), title)


def structure_document(
    document: IngestedDocument, *, source_root: Path | None = None, hash_unrooted: bool = False
) -> Note:
    """Transforma um documento bruto em uma nota estruturada mínima.

    Este comportamento é determinístico e serve como placeholder para a futura
    etapa de estruturação assistida por LLM.
    """
    # Áudio com segmentos usa o texto canônico dos segmentos, para os offsets do chunking por fala baterem.
    if document.segments:
        normalized_text = build_segment_text(document.segments)
    else:
        normalized_text = normalize_text(
            document.cleaned_text
            if document.cleaned_text is not None
            else document.raw_text
        )
    body_text, has_frontmatter = strip_frontmatter(normalized_text)
    lines = body_text.splitlines()
    fallback_title = _humanize_fallback_title(document.source_path.stem)
    title_index, title = _choose_title(lines, fallback_title, document.source_type, has_frontmatter)
    summary = repair_ocr_summary_text(_extract_summary(lines, title_index, title))
    note = Note(
        note_id=build_note_id(document.source_path, root_path=source_root, hash_unrooted=hash_unrooted),
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
        content_hash=sha256(normalized_text.encode("utf-8")).hexdigest(),
        segments=list(document.segments) if document.segments else None,
    )
    note.structured_markdown = render_note_markdown(note)
    return note
