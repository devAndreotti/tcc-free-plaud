from pydantic import BaseModel


class Chunk(BaseModel):
    """Representa um segmento indexável de uma nota."""

    chunk_id: str
    note_id: str
    chunk_index: int
    chunk_text: str
    token_count: int
