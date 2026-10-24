from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from escolio.providers.audio_models import TranscriptSegment


class IngestedDocument(BaseModel):
    """Representa um artefato bruto aceito pelo pipeline."""

    source_path: Path
    source_type: str = Field(description="Tipo lógico da origem, como txt, md ou pdf.")
    raw_text: str
    cleaned_text: str | None = None
    transcription_path: Path | None = None
    # Só áudio transcrito preenche: segmentos com start/end usados no chunking por fala.
    segments: list[TranscriptSegment] | None = None


class IngestionResult(BaseModel):
    """Representa o resultado operacional de uma ingestão rastreável."""

    ingestion_id: str
    correlation_id: str
    source_path: Path
    source_type: str | None = None
    detected_media_type: str | None = None
    status: Literal["success", "failed"]
    size_bytes: int = 0
    content_sha256: str | None = None
    raw_text: str = ""
    error_code: str | None = None
    message: str | None = None
    warnings: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
