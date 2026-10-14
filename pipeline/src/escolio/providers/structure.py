from typing import Protocol

from escolio.ingest.models import IngestedDocument
from escolio.notes.schemas import Note


class StructurerProvider(Protocol):
    def structure(self, document: IngestedDocument) -> Note:
        """Converte entrada bruta em nota estruturada."""
