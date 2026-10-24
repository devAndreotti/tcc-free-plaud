import re
from collections.abc import Sequence
from dataclasses import dataclass
from hashlib import sha256

from escolio.providers.audio_models import TranscriptSegment
from escolio.retrieval.models import Chunk

PIPELINE_VERSION = 'pipeline-0.4.1'
DEFAULT_STRATEGY = 'fixed_char_window'
SEGMENT_STRATEGY = 'audio_segments'
SEGMENT_SEPARATOR = ' '
_SENTENCE_BREAK = re.compile(r'(?<=[.!?…])\s+')


def stable_chunk_id(
    note_id: str,
    note_version: int,
    char_start: int,
    char_end: int,
    strategy: str,
    normalized_text_sha256: str,
) -> str:
    """Gera um ID determinístico a partir da proveniência do chunk."""
    raw = f'{note_id}|{note_version}|{char_start}|{char_end}|{strategy}|{normalized_text_sha256}'
    digest = sha256(raw.encode('utf-8')).hexdigest()[:10]
    return f'{note_id}::v{note_version}::ofs-{char_start:06d}-{char_end:06d}::{digest}'


def chunk_text(
    note_id: str,
    note_version: int,
    text: str,
    *,
    chunk_size: int = 800,
    overlap: int = 120,
    normalized_text_sha256: str,
    strategy: str = DEFAULT_STRATEGY,
    pipeline_version: str = PIPELINE_VERSION,
) -> list[Chunk]:
    """Faz chunking determinístico por janela deslizante com offsets absolutos."""
    if chunk_size <= 0:
        raise ValueError('chunk_size deve ser positivo')
    if overlap < 0:
        raise ValueError('overlap não pode ser negativo')
    if overlap >= chunk_size:
        raise ValueError('overlap deve ser menor que chunk_size')

    normalized_text = text.strip()
    if not normalized_text:
        return []

    chunks: list[Chunk] = []
    start = 0
    chunk_index = 0
    step = chunk_size - overlap

    while start < len(normalized_text):
        end = min(start + chunk_size, len(normalized_text))
        piece = normalized_text[start:end]
        if piece.strip():
            chunks.append(
                Chunk(
                    chunk_id=stable_chunk_id(
                        note_id=note_id,
                        note_version=note_version,
                        char_start=start,
                        char_end=end,
                        strategy=strategy,
                        normalized_text_sha256=normalized_text_sha256,
                    ),
                    note_id=note_id,
                    note_version=note_version,
                    chunk_index=chunk_index,
                    char_start=start,
                    char_end=end,
                    chunk_size=chunk_size,
                    overlap=overlap,
                    chunk_text=piece,
                    token_count=len(piece.split()),
                    strategy=strategy,
                    normalized_text_sha256=normalized_text_sha256,
                    text_sha256=sha256(piece.encode('utf-8')).hexdigest(),
                    pipeline_version=pipeline_version,
                )
            )
        if end == len(normalized_text):
            break
        start += step
        chunk_index += 1

    return chunks


def build_segment_text(segments: Sequence[TranscriptSegment]) -> str:
    """Texto canônico de uma transcrição: segmentos com texto, aparados e unidos por espaço.

    É o `normalized_text` da nota de áudio. Não passa por `normalize_text`, porque ele funde
    fragmentos e remove linhas repetidas, e isso quebraria o mapeamento segmento -> offsets.
    """
    return SEGMENT_SEPARATOR.join(text for text in (segment.text.strip() for segment in segments) if text)


@dataclass(frozen=True)
class _Unit:
    """Pedaço de fala com offsets absolutos no texto canônico e tempo estimado."""

    start: int
    end: int
    t_start: float
    t_end: float


def _sentence_spans(text: str) -> list[tuple[int, int]]:
    spans: list[tuple[int, int]] = []
    cursor = 0
    for match in _SENTENCE_BREAK.finditer(text):
        spans.append((cursor, match.start()))
        cursor = match.end()
    spans.append((cursor, len(text)))
    return spans


def _hard_split(text: str, start: int, end: int, max_chars: int) -> list[tuple[int, int]]:
    """Corta um trecho sem pontuação em janelas <= max_chars, preferindo quebrar em espaço."""
    spans: list[tuple[int, int]] = []
    position = start
    while end - position > max_chars:
        cut = text.rfind(' ', position + 1, position + max_chars + 1)
        if cut <= position:
            cut = position + max_chars
        spans.append((position, cut))
        position = cut
        while position < end and text[position].isspace():
            position += 1
    if position < end:
        spans.append((position, end))
    return spans


def _fitting_spans(text: str, max_chars: int) -> list[tuple[int, int]]:
    """Divide uma fala em pedaços <= max_chars, respeitando frases quando possível."""
    if len(text) <= max_chars:
        return [(0, len(text))]
    spans: list[tuple[int, int]] = []
    current: tuple[int, int] | None = None
    for start, end in _sentence_spans(text):
        if end - start > max_chars:
            if current is not None:
                spans.append(current)
                current = None
            spans.extend(_hard_split(text, start, end, max_chars))
            continue
        if current is None:
            current = (start, end)
        elif end - current[0] <= max_chars:
            current = (current[0], end)
        else:
            spans.append(current)
            current = (start, end)
    if current is not None:
        spans.append(current)
    return spans


def _units(segments: Sequence[TranscriptSegment], max_chars: int) -> list[_Unit]:
    units: list[_Unit] = []
    cursor = 0
    for segment in segments:
        text = segment.text.strip()
        if not text:
            continue
        if units:
            cursor += len(SEGMENT_SEPARATOR)
        spans = _fitting_spans(text, max_chars)
        duration = segment.end - segment.start
        for local_start, local_end in spans:
            # Segmento longo é dividido: o tempo de cada pedaço é estimado pela proporção de caracteres.
            t_start = segment.start + duration * local_start / len(text)
            t_end = segment.start + duration * local_end / len(text)
            if len(spans) == 1:
                t_start, t_end = segment.start, segment.end
            units.append(_Unit(cursor + local_start, cursor + local_end, t_start, t_end))
        cursor += len(text)
    return units


def chunk_segments(
    note_id: str,
    note_version: int,
    segments: Sequence[TranscriptSegment],
    *,
    normalized_text_sha256: str,
    chunk_size: int = 800,
    overlap: int = 120,
    target_chars: int = 800,
    max_chars: int = 1200,
    pause_seconds: float = 2.0,
    strategy: str = SEGMENT_STRATEGY,
    pipeline_version: str = PIPELINE_VERSION,
) -> list[Chunk]:
    """Agrupa falas consecutivas em chunks sem cortar uma fala no meio, com tempo e offsets.

    Fecha o chunk quando ele atinge `target_chars`, quando a pausa até a próxima fala passa de
    `pause_seconds` ou quando a próxima fala estouraria `max_chars`. Falas maiores que `max_chars`
    são divididas por sentença. Os offsets referem-se a `build_segment_text(segments)`.

    `chunk_size` e `overlap` são só o registro da configuração do índice (usado para decidir reuso
    de chunks já gravados); o tamanho real é controlado por `target_chars` e `max_chars`.
    """
    if target_chars <= 0 or max_chars < target_chars:
        raise ValueError('target_chars deve ser positivo e max_chars não pode ser menor que target_chars')
    if pause_seconds < 0:
        raise ValueError('pause_seconds não pode ser negativo')

    text = build_segment_text(segments)
    groups: list[list[_Unit]] = []
    current: list[_Unit] = []
    for unit in _units(segments, max_chars):
        if current:
            pause = unit.t_start - current[-1].t_end
            grown = unit.end - current[0].start
            reached_target = current[-1].end - current[0].start >= target_chars
            if pause > pause_seconds or grown > max_chars or reached_target:
                groups.append(current)
                current = []
        current.append(unit)
    if current:
        groups.append(current)

    chunks: list[Chunk] = []
    for chunk_index, group in enumerate(groups):
        char_start = group[0].start
        char_end = group[-1].end
        piece = text[char_start:char_end]
        chunks.append(
            Chunk(
                chunk_id=stable_chunk_id(
                    note_id=note_id,
                    note_version=note_version,
                    char_start=char_start,
                    char_end=char_end,
                    strategy=strategy,
                    normalized_text_sha256=normalized_text_sha256,
                ),
                note_id=note_id,
                note_version=note_version,
                chunk_index=chunk_index,
                char_start=char_start,
                char_end=char_end,
                chunk_size=chunk_size,
                overlap=overlap,
                chunk_text=piece,
                token_count=len(piece.split()),
                strategy=strategy,
                normalized_text_sha256=normalized_text_sha256,
                text_sha256=sha256(piece.encode('utf-8')).hexdigest(),
                pipeline_version=pipeline_version,
                t_start=group[0].t_start,
                t_end=group[-1].t_end,
            )
        )
    return chunks
