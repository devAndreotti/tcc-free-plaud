from pydantic import BaseModel


class Chunk(BaseModel):
    """Representa um segmento indexável de uma nota."""

    chunk_id: str
    note_id: str
    note_version: int
    chunk_index: int
    char_start: int
    char_end: int
    chunk_size: int
    overlap: int
    chunk_text: str
    token_count: int
    strategy: str
    normalized_text_sha256: str
    text_sha256: str
    pipeline_version: str
