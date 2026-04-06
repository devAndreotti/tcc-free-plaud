from typing import Literal

from pydantic import BaseModel, Field


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


class SearchHit(BaseModel):
    """Representa um chunk recuperado junto com sinais básicos de relevância."""

    chunk: Chunk
    score: float
    matched_terms: list[str] = Field(default_factory=list)
    term_coverage: float


class Citation(BaseModel):
    """Representa uma citação rastreável até um chunk persistível."""

    note_id: str
    note_version: int
    chunk_id: str
    snippet: str
    source_path: str | None = None
    char_start: int
    char_end: int


class AnswerClaim(BaseModel):
    """Representa uma afirmação sustentada por uma ou mais citações."""

    text: str
    citations: list[Citation] = Field(default_factory=list)
    support_level: Literal['direct', 'partial']


class UsedSource(BaseModel):
    """Resume quais fontes efetivamente sustentaram a resposta."""

    doc_id: str
    note_version: int
    source_path: str | None = None
    chunk_ids: list[str] = Field(default_factory=list)


class AskResponse(BaseModel):
    """Contrato estruturado para respostas do fluxo ask de RAG."""

    query: str
    status: Literal['answer', 'no_answer']
    no_answer: bool
    answer: str | None
    claims: list[AnswerClaim] = Field(default_factory=list)
    citations: list[Citation] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    reason_for_no_answer: str | None = None
    used_sources: list[UsedSource] = Field(default_factory=list)
    latency_ms: int
