from typing import Protocol

from free_plaud.ingest.models import IngestedDocument
from free_plaud.notes.schemas import Note


class StructurerProvider(Protocol):
    def structure(self, document: IngestedDocument) -> Note:
        """Converte entrada bruta em nota estruturada."""
