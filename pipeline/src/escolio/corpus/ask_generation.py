"""Geração da resposta pelo provider: a resposta gerada só substitui a extrativa se passar na validação."""

from collections.abc import Callable
from dataclasses import dataclass, field
from time import perf_counter

from escolio.corpus.answer_context import (
    build_answer_context_items,
    normalize_answer_markers,
)
from escolio.corpus.ask_claims import (
    _drop_unknown_answer_markers,
    _hits_for_citations,
    _summarize_corpus_sources,
    _with_cited_context_citations,
    _with_source_limitations,
)
from escolio.corpus.ask_grounding import Rejection
from escolio.corpus.ask_validation import GeneratedAnswerValidation
from escolio.notes.schemas import Note
from escolio.providers.answer import AnswerProvider, AnswerProviderError
from escolio.retrieval.models import (
    AnswerClaim,
    AskDebugTimings,
    Citation,
    SearchHit,
    UsedSource,
)

# Recebida por parâmetro: ask.py passa validate_generated_answer, para o monkeypatch dos testes valer.
ValidateAnswer = Callable[[str, str, list[str], list[AnswerClaim]], GeneratedAnswerValidation]


@dataclass
class GenerationOutcome:
    answer: str
    citations: list[Citation]
    cited_sources: list[UsedSource]
    limitations: list[str]
    generated: bool = False
    answer_sources: list[str] = field(default_factory=list)
    discard_reason: str | None = None
    rejection: Rejection | None = None


def _provider_failure_limitation(exc: Exception) -> str:
    detail = str(exc)[:200].rstrip('.') if isinstance(exc, AnswerProviderError) else type(exc).__name__
    return f'A IA falhou; usando resposta extrativa. Erro: {detail}.'


def elapsed_ms(stage_started_at: float) -> int:
    return int((perf_counter() - stage_started_at) * 1000)


def provider_identity(answer_provider: AnswerProvider | None) -> tuple[str | None, str | None]:
    """Nome e modelo do provider de resposta para o debug; (None, None) quando não há provider."""
    name = answer_provider.provider_name if answer_provider is not None else None
    model_value = getattr(answer_provider, 'model', None) if answer_provider is not None else None
    return name, (str(model_value) if model_value is not None else None)


def generate_answer(
    question: str,
    *,
    answer: str,
    claims: list[AnswerClaim],
    hits: list[SearchHit],
    citations: list[Citation],
    cited_sources: list[UsedSource],
    limitations: list[str],
    note_lookup: dict[str, Note],
    provider: AnswerProvider,
    on_answer_delta: Callable[[str], None] | None,
    validate: ValidateAnswer,
    stage_timings: AskDebugTimings,
) -> GenerationOutcome:
    """Pede a resposta ao provider; sem aceite, mantém a extrativa e registra o motivo.

    Erro do provider vira limitação; erro dentro da validação não é capturado e propaga.
    """
    context_started_at = perf_counter()
    context_items = build_answer_context_items(claims, hits, note_lookup)
    answer_contexts = [context for context, _ in context_items]
    stage_timings.context_build_ms = elapsed_ms(context_started_at)

    provider_started_at = perf_counter()
    try:
        if on_answer_delta is not None and hasattr(provider, 'answer_stream'):
            generated_answer = provider.answer_stream(question, answer_contexts, on_answer_delta)
        else:
            generated_answer = provider.answer(question, answer_contexts)
    except Exception as exc:
        stage_timings.provider_ms = elapsed_ms(provider_started_at)
        return GenerationOutcome(
            answer=answer,
            citations=citations,
            cited_sources=cited_sources,
            limitations=[*limitations, _provider_failure_limitation(exc)],
            discard_reason='provider_error',
        )
    stage_timings.provider_ms = elapsed_ms(provider_started_at)
    generated_answer = normalize_answer_markers(generated_answer)

    validation_started_at = perf_counter()
    validation = validate(question, generated_answer, answer_contexts, claims)
    stage_timings.validation_ms = elapsed_ms(validation_started_at)

    if validation.action == 'accept':
        answer = _drop_unknown_answer_markers(generated_answer, len(answer_contexts))
        answer_sources = [chunk_id for _, chunk_id in context_items]
        citations = _with_cited_context_citations(answer, answer_sources, citations, hits, note_lookup)
        cited_sources = _summarize_corpus_sources(_hits_for_citations(hits, citations), note_lookup)
        return GenerationOutcome(
            answer=answer,
            citations=citations,
            cited_sources=cited_sources,
            limitations=_with_source_limitations(limitations, citations, cited_sources),
            generated=True,
            answer_sources=answer_sources,
        )
    if validation.action == 'no_answer':
        return GenerationOutcome(
            answer=answer,
            citations=citations,
            cited_sources=cited_sources,
            limitations=limitations,
            rejection=(validation.reason or 'generated_answer_rejected', validation.limitations),
        )
    return GenerationOutcome(
        answer=answer,
        citations=citations,
        cited_sources=cited_sources,
        limitations=[*limitations, *validation.limitations],
        discard_reason=validation.reason,
    )
