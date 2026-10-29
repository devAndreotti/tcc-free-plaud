"""Motivo do descarte da resposta gerativa do chat, lido do AskResponse da passada no corpus."""

from escolio.retrieval.models import AskResponse


def generation_discard_reason(response: AskResponse, *, has_provider: bool) -> str | None:
    """Motivo pelo qual o texto gerativo foi descartado; None se foi aceito ou não houve provedor."""
    return response.answer_discard_reason if has_provider else None
