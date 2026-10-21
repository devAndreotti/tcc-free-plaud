import re

from escolio.notes.readable import readable_chunk_text
from escolio.notes.schemas import Note
from escolio.retrieval.models import AnswerClaim, SearchHit

ANSWER_CONTEXT_TOTAL_CHAR_BUDGET = 6000
ANSWER_CONTEXT_MAX_CHARS = 1500
MULTI_MARKER_PATTERN = re.compile(r'\[(\d{1,2}(?:\s*,\s*\d{1,2})+)\]')


def normalize_answer_markers(text: str) -> str:
    """Troca '[1, 2]' por '[1] [2]': só o formato [n] vira fonte clicável no app."""
    return MULTI_MARKER_PATTERN.sub(lambda match: ' '.join(f'[{n}]' for n in re.findall(r'\d+', match.group(1))), text)


def _clip_context_text(text: str, max_chars: int) -> str:
    if max_chars <= 0:
        return ''
    if len(text) <= max_chars:
        return text
    marker = '\n...[truncado]'
    if max_chars <= len(marker):
        return text[:max_chars]
    return f'{text[: max_chars - len(marker)].rstrip()}{marker}'


def build_answer_context_items(
    claims: list[AnswerClaim],
    hits: list[SearchHit],
    note_lookup: dict[str, Note],
    *,
    max_total_chars: int = ANSWER_CONTEXT_TOTAL_CHAR_BUDGET,
    max_context_chars: int = ANSWER_CONTEXT_MAX_CHARS,
    include_hits: bool = True,
) -> list[tuple[str, str]]:
    """Contextos (texto, chunk_id principal): primeiro os claims, depois os outros trechos recuperados.

    O [n] de cada contexto é a posição na lista. Com include_hits=False, só os claims (como antes):
    com o qchat (3B), os trechos extras faziam o modelo recusar mais positivas (docs/experimentos/17).
    """
    hit_by_chunk_id = {hit.chunk.chunk_id: hit for hit in hits}
    blocks: list[tuple[str, list[str], str]] = []  # (cabeçalho sem [n], trechos, chunk_id principal)
    used_chunk_ids: set[str] = set()
    for claim in claims:
        citation = claim.citations[0] if claim.citations else None
        if citation is None:
            continue

        note = note_lookup.get(citation.note_id)
        source_path = str(note.source_path) if note else citation.source_path or ''
        title = note.title if note else ''
        chunk_ids = ', '.join(item.chunk_id for item in claim.citations)
        evidence_parts: list[str] = []
        for item in claim.citations:
            cited_hit = hit_by_chunk_id.get(item.chunk_id)
            raw_text = cited_hit.chunk.chunk_text if cited_hit else item.snippet
            evidence = readable_chunk_text(raw_text)
            if evidence:
                evidence_parts.append(evidence)
        body = (
            f'source_path: {source_path}\n'
            f'title: {title}\n'
            f'note_id: {citation.note_id}\n'
            f'chunk_id: {chunk_ids}\n'
            f'claim_extrativo: {claim.text}\n'
            'trecho:\n'
        )
        blocks.append((body, evidence_parts, citation.chunk_id))
        used_chunk_ids.update(item.chunk_id for item in claim.citations)

    if include_hits:
        for hit in hits:
            chunk_id = hit.chunk.chunk_id
            if chunk_id in used_chunk_ids:
                continue
            used_chunk_ids.add(chunk_id)
            note = note_lookup.get(hit.chunk.note_id)
            source_path = str(note.source_path) if note else ''
            title = note.title if note else ''
            body = (
                f'source_path: {source_path}\n'
                f'title: {title}\n'
                f'note_id: {hit.chunk.note_id}\n'
                f'chunk_id: {chunk_id}\n'
                'trecho:\n'
            )
            evidence = readable_chunk_text(hit.chunk.chunk_text)
            blocks.append((body, [evidence] if evidence else [], chunk_id))

    items: list[tuple[str, str]] = []
    total_chars = 0
    for body, evidence_parts, chunk_id in blocks:
        header = f'[{len(items) + 1}]\n{body}'
        allowed_context_chars = min(max_context_chars, max_total_chars - total_chars)
        if allowed_context_chars <= len(header):
            break
        evidence_text = _clip_context_text('\n\n'.join(evidence_parts), allowed_context_chars - len(header))
        context = f'{header}{evidence_text}'
        items.append((context, chunk_id))
        total_chars += len(context)
    return items


def build_answer_contexts(
    claims: list[AnswerClaim],
    hits: list[SearchHit],
    note_lookup: dict[str, Note],
    *,
    max_total_chars: int = ANSWER_CONTEXT_TOTAL_CHAR_BUDGET,
    max_context_chars: int = ANSWER_CONTEXT_MAX_CHARS,
    include_hits: bool = True,
) -> list[str]:
    """Monta contexto generativo com evidencia citavel real e budget fixo (só os textos)."""
    items = build_answer_context_items(
        claims,
        hits,
        note_lookup,
        max_total_chars=max_total_chars,
        max_context_chars=max_context_chars,
        include_hits=include_hits,
    )
    return [context for context, _ in items]
