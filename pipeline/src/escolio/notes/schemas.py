from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from escolio.providers.audio_models import TranscriptSegment


class ActionItem(BaseModel):
    """Tarefa extraída da nota; owner e due só existem quando a nota os informa."""

    model_config = ConfigDict(str_strip_whitespace=True)

    text: str = Field(min_length=1)
    owner: str | None = None
    due: str | None = None

    def label(self) -> str:
        """Texto humano usado em listas (frontmatter `tasks` e seção '## Ações')."""
        details = []
        if self.owner:
            details.append(f'responsável: {self.owner}')
        if self.due:
            details.append(f'prazo: {self.due}')
        return f'{self.text} ({"; ".join(details)})' if details else self.text


class Decision(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    text: str = Field(min_length=1)


class NoteExtraction(BaseModel):
    """Saída estruturada opcional do LLM para uma nota.

    `discarded` conta itens removidos pela guarda anti-alucinação (ou inválidos
    no schema); `warnings` registra falhas não fatais, como JSON ilegível.
    """

    topics: list[str] = Field(default_factory=list)
    decisions: list[Decision] = Field(default_factory=list)
    action_items: list[ActionItem] = Field(default_factory=list)
    discarded: int = 0
    warnings: list[str] = Field(default_factory=list)

    def is_empty(self) -> bool:
        return not (self.topics or self.decisions or self.action_items)


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
    # Extração opcional via LLM (ver notes/extraction.py); vazia por padrão.
    extraction: NoteExtraction = Field(default_factory=NoteExtraction)
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
