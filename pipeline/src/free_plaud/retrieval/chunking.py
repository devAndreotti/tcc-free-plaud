from hashlib import sha256

from free_plaud.retrieval.models import Chunk

PIPELINE_VERSION = 'pipeline-0.4.1'
DEFAULT_STRATEGY = 'fixed_char_window'


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
        piece = normalized_text[start:end].strip()
        if piece:
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
