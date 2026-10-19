"""Motivo do descarte da resposta gerativa do chat, lido do AskResponse da passada no corpus."""

from escolio.retrieval.models import AskResponse

# Abstenções que vêm da validação da resposta gerativa, não da recuperação.
GENERATION_ABSTAIN_REASONS = frozenset({'generated_no_answer_sentinel', 'generated_generic_no_answer'})
PROVIDER_ERROR_REASON = 'provider_error'
UNKNOWN_REASON = 'desconhecido'

# ponytail: o código sai do texto da limitação, porque a validação não expõe o reason quando troca a
# resposta gerativa pela extrativa. Se o AskResponse passar a carregar esse reason, trocar esta tabela por ele.
_LIMITATION_MARKERS: tuple[tuple[str, str], ...] = (
    ('só marcações de fonte', 'empty_generated_answer'),
    ('unsupported_number:', 'unsupported_number'),
    ('unsupported_anchor:', 'unsupported_anchor'),
    ('repetiu os metadados', 'echoed_context_metadata'),
    ('baixa sobreposicao com claims', 'low_claim_overlap'),
    ('Provider de resposta falhou', PROVIDER_ERROR_REASON),
)


def limitation_code(limitations: list[str]) -> str:
    """Código do motivo de troca pela extrativa, a partir das limitações da resposta."""
    for limitation in limitations:
        for marker, code in _LIMITATION_MARKERS:
            if marker in limitation:
                return code
    return UNKNOWN_REASON


def generation_discard_reason(response: AskResponse, *, has_provider: bool) -> str | None:
    """Código do motivo pelo qual o texto gerativo foi descartado; None se foi aceito ou não houve geração."""
    if not has_provider or response.generated:
        return None
    if response.no_answer:
        return response.reason_for_no_answer if response.reason_for_no_answer in GENERATION_ABSTAIN_REASONS else None
    return limitation_code(response.limitations)
