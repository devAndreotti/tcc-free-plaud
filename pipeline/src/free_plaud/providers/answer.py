from typing import Protocol


class AnswerProvider(Protocol):
    def answer(self, question: str, contexts: list[str]) -> str:
        """Gera resposta a partir de contextos recuperados."""
