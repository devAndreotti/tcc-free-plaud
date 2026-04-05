from pathlib import Path

from pydantic import BaseModel, Field


class IngestedDocument(BaseModel):
    """Representa um artefato bruto aceito pelo pipeline."""

    source_path: Path
    source_type: str = Field(description="Tipo lógico da origem, como txt, md ou pdf.")
    raw_text: str
