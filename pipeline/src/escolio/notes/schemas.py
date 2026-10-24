from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from escolio.providers.audio_models import TranscriptSegment


class Note(BaseModel):
    """Representa a unidade primária de conhecimento do sistema."""

    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
    )

    note_id: str
    note_version: int = 1
    source_type: str
    source_path: Path
    source_name: str
    title: str
    summary: str
    topics: list[str] = Field(default_factory=list)
    tasks: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    raw_text: str
    normalized_text: str
    structured_markdown: str
    content_hash: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    provider: str = "local"
    model: str = "rule-based"
    # Segmentos de fala (áudio) só vivem na memória durante a indexação: não são persistidos nem serializados.
    # Quando presentes, normalized_text é exatamente o texto concatenado dos segmentos (ver chunking.py).
    segments: list[TranscriptSegment] | None = Field(default=None, exclude=True)
