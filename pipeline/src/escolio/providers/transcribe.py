from typing import Protocol


class Transcriber(Protocol):
    def transcribe(self, source_path: str) -> str:
        """Transcreve um artefato de áudio para texto."""
