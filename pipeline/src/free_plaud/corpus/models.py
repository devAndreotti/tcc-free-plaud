from typing import Literal

from pydantic import BaseModel


class CorpusIndexResult(BaseModel):
    """Resultado estavel de indexacao de um arquivo no corpus local."""

    source_path: str
    status: Literal['success', 'failed']
    note_id: str | None = None
    chunks_indexed: int = 0
    embedding_model: str | None = None
    vector_collection_name: str | None = None
    vector_entries_count: int = 0
    error_code: str | None = None
    message: str | None = None
