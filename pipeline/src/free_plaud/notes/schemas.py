from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field


class Note(BaseModel):
    """Representa a unidade primária de conhecimento do sistema."""

    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
    )

    note_id: str
    source_type: str
    source_path: Path
    title: str
    summary: str
    topics: list[str] = Field(default_factory=list)
    tasks: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    raw_text: str
    structured_markdown: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    provider: str = "local"
    model: str = "rule-based"
