from free_plaud.retrieval.models import Chunk


def chunk_text(note_id: str, text: str, chunk_size: int = 800, overlap: int = 120) -> list[Chunk]:
    """Faz chunking determinístico por janela deslizante de caracteres."""
    if not text.strip():
        return []
    if overlap >= chunk_size:
        raise ValueError('overlap deve ser menor que chunk_size')

    chunks: list[Chunk] = []
    start = 0
    index = 0
    step = chunk_size - overlap

    while start < len(text):
        piece = text[start:start + chunk_size].strip()
        if piece:
            chunks.append(
                Chunk(
                    chunk_id=f'{note_id}-{index}',
                    note_id=note_id,
                    chunk_index=index,
                    chunk_text=piece,
                    token_count=len(piece.split()),
                )
            )
        start += step
        index += 1

    return chunks
