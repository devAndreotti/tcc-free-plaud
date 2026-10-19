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
    term_coverage: float = 0.0
    strategy: str = 'lexical'
    distance: float | None = None


class AskDebugHit(BaseModel):
    """Sinais de recuperacao usados para explicar uma resposta ask."""

    chunk_id: str
    note_id: str
    note_version: int
    source_path: str | None = None
    score: float
    strategy: str
    matched_terms: list[str] = Field(default_factory=list)
    term_coverage: float = 0.0
    distance: float | None = None
    snippet: str


class AskDebugTimings(BaseModel):
    """Tempos por etapa do Ask para diagnosticar gargalo sem vazar prompt."""

    retrieval_ms: int = 0
    claim_build_ms: int = 0
    context_build_ms: int = 0
    provider_ms: int = 0
    validation_ms: int = 0
    total_ms: int = 0


class AskDebug(BaseModel):
    """Debug opcional para tuning de retrieval sem poluir respostas normais."""

    strategy: str
    query_terms: list[str] = Field(default_factory=list)
    named_query_terms: list[str] = Field(default_factory=list)
    hits: list[AskDebugHit] = Field(default_factory=list)
    rejected_hits: list[AskDebugHit] = Field(default_factory=list)
    no_answer_reason: str | None = None
    stale_vector_hits_count: int = 0
    timings: AskDebugTimings | None = None
    answer_provider: str | None = None
    provider_model: str | None = None


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
    # True quando `answer` é o texto do provider generativo (validado); False é a junção dos claims.
    generated: bool = False
    claims: list[AnswerClaim] = Field(default_factory=list)
    citations: list[Citation] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    reason_for_no_answer: str | None = None
    used_sources: list[UsedSource] = Field(default_factory=list)
    latency_ms: int
    debug: AskDebug | None = None
