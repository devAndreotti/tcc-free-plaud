from typing import Protocol


class VisionProvider(Protocol):
    def extract_text(self, source_path: str) -> str:
        """Extrai texto de imagem ou documento visual."""
