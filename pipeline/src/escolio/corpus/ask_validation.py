"""Validação da resposta gerativa do corpus: decide se ela substitui a extrativa.

Extraída de corpus/ask.py. A busca e o fluxo de resposta continuam em ask.py, que reexporta
validate_generated_answer e GeneratedAnswerValidation.
"""

import re
from typing import Literal

from pydantic import BaseModel, Field

from escolio.providers.answer_quality import (
    ANSWER_MARKER_PATTERN,
    has_source_marker,
    is_echoed_question,
    is_echoed_title,
    is_no_answer_sentinel,
)
from escolio.retrieval.models import AnswerClaim
from escolio.retrieval.search import match_terms_in_text, normalize_query_terms

CONTEXT_METADATA_KEYS = ('source_path:', 'note_id:', 'chunk_id:', 'claim_extrativo:')
# Unidade só conta quando é conhecida ("2.1 foi" é 2.1 e uma palavra). ponytail: R$ fica de fora; incluir aqui se a comparação precisar.
GENERATED_NUMBER_PATTERN = re.compile(r'\b\d+(?:[.,]\d+)?(?:\s*(?:%|(?:kb|mb|gb|tb|dias?|m[êe]s(?:es)?|anos?|horas?|minutos?|semanas?)\b))?', re.IGNORECASE)
GENERATED_ANCHOR_PATTERN = re.compile(r'\b[A-ZÀ-Ö][A-Za-zÀ-ÖØ-öø-ÿ0-9_-]{2,}\b')
GENERIC_NO_ANSWER_MARKERS = (
    'nao consegui recuperar',
    'não consegui recuperar',
    'nao encontrei',
    'não encontrei',
    'nao foi possivel encontrar',
    'não foi possível encontrar',
)
GENERIC_SUGGESTION_MARKERS = ('documentacao', 'documentação', 'verificar', 'consulte', 'pesquise', 'tente')
IGNORED_GENERATED_ANCHORS = {
    'Nao',
    'Não',
    'Voce',
    'Você',
    'Resposta',
    'Pergunta',
    'Contextos',
    'Contexto',
}


class GeneratedAnswerValidation(BaseModel):
    action: Literal['accept', 'no_answer', 'fallback_extractive']
    reason: str | None = None
    limitations: list[str] = Field(default_factory=list)

def _without_answer_markers(text: str) -> str:
    return ANSWER_MARKER_PATTERN.sub('', text)

def _normalized_support_text(contexts: list[str], claims: list[AnswerClaim]) -> str:
    return '\n'.join([*(context.split('trecho:\n', 1)[-1] for context in contexts), *(claim.text for claim in claims)]).casefold()

def _unsupported_generated_numbers(answer: str, support_text: str) -> list[str]:
    unsupported: list[str] = []
    for raw_number in GENERATED_NUMBER_PATTERN.findall(answer):
        normalized = ' '.join(raw_number.split()).casefold()
        if normalized and normalized not in support_text and normalized not in unsupported:
            unsupported.append(normalized)
    return unsupported

def _starts_sentence(text: str, start: int) -> bool:
    before = text[:start].rstrip(' \t*->"“(')
    return not before or before[-1] in '.!?:\n'

def _unsupported_generated_anchors(answer: str, support_text: str) -> list[str]:
    unsupported: list[str] = []
    for match in GENERATED_ANCHOR_PATTERN.finditer(answer):
        anchor = match.group()
        if anchor in IGNORED_GENERATED_ANCHORS:
            continue
        # Maiúscula no início da frase não indica nome ("Inicialmente,"); sigla em caixa alta, sim.
        if not anchor.isupper() and _starts_sentence(answer, match.start()):
            continue
        normalized = anchor.casefold()
        if normalized and normalized not in support_text and normalized not in unsupported:
            unsupported.append(normalized)
    return unsupported

def _is_generic_generated_no_answer(answer: str) -> bool:
    lowered = answer.casefold()
    return (len(lowered.split()) <= 12 and lowered.startswith(GENERIC_NO_ANSWER_MARKERS)) or (
        any(marker in lowered for marker in GENERIC_NO_ANSWER_MARKERS) and any(marker in lowered for marker in GENERIC_SUGGESTION_MARKERS)
    )

def validate_generated_answer(
    question: str,
    answer: str,
    contexts: list[str],
    claims: list[AnswerClaim],
) -> GeneratedAnswerValidation:
    """Valida se resposta gerativa pode substituir a resposta extrativa."""
    # Os [n] são só ponteiros para o contexto: número, anchor e sobreposição são checados sem eles.
    cleaned_answer = _without_answer_markers(answer).strip()
    # O qchat às vezes devolve só "[1]": sem os marcadores não sobra texto, e nada abaixo recusaria.
    if not any(char.isalnum() for char in cleaned_answer):
        return GeneratedAnswerValidation(
            action='fallback_extractive',
            reason='empty_generated_answer',
            limitations=['Resposta generativa ignorada: o modelo devolveu só marcações de fonte, sem texto.'],
        )
    if is_no_answer_sentinel(cleaned_answer, contexts):
        return GeneratedAnswerValidation(
            action='no_answer',
            reason='generated_no_answer_sentinel',
            limitations=['A IA declarou que os contextos não sustentam resposta.'],
        )
    if _is_generic_generated_no_answer(cleaned_answer):
        return GeneratedAnswerValidation(
            action='no_answer',
            reason='generated_generic_no_answer',
            limitations=['A IA respondeu com uma negativa genérica em vez de uma resposta sustentada.'],
        )
    # Trecho vazio (nota só com frontmatter) faz modelo pequeno copiar o cabeçalho do contexto.
    if any(key in cleaned_answer for key in CONTEXT_METADATA_KEYS):
        return GeneratedAnswerValidation(
            action='fallback_extractive',
            reason='echoed_context_metadata',
            limitations=['Resposta generativa ignorada: o modelo repetiu os metadados do contexto em vez de responder.'],
        )
    if is_echoed_title(cleaned_answer, contexts):
        return GeneratedAnswerValidation(
            action='fallback_extractive',
            reason='echoed_title',
            limitations=['Resposta generativa ignorada: o modelo copiou um título do contexto em vez de responder.'],
        )
    if is_echoed_question(question, cleaned_answer):
        return GeneratedAnswerValidation(
            action='fallback_extractive',
            reason='echoed_question',
            limitations=['Resposta generativa ignorada: o modelo repetiu a pergunta em vez de responder.'],
        )

    support_text = _normalized_support_text(contexts, claims)
    unsupported_numbers = _unsupported_generated_numbers(cleaned_answer, support_text)
    if unsupported_numbers:
        return GeneratedAnswerValidation(
            action='fallback_extractive',
            reason='unsupported_number',
            limitations=[f'Resposta generativa ignorada por número sem suporte: {", ".join(unsupported_numbers)}.'],
        )

    unsupported_anchors = _unsupported_generated_anchors(cleaned_answer, support_text)
    if unsupported_anchors:
        return GeneratedAnswerValidation(
            action='fallback_extractive',
            reason='unsupported_anchor',
            limitations=[f'Resposta generativa ignorada por nome citado sem suporte: {", ".join(unsupported_anchors)}.'],
        )

    # Sobreposição com os trechos entregues ao modelo, não só com o claim extraído: em nota
    # Markdown o claim costuma ser o título ("VLAN - [!note]") e derrubava respostas fiéis.
    answer_terms = normalize_query_terms(cleaned_answer)
    if len(answer_terms) >= 4:
        _, claim_coverage = match_terms_in_text(answer_terms, support_text)
        if claim_coverage < 0.35:
            return GeneratedAnswerValidation(
                action='fallback_extractive',
                reason='low_claim_overlap',
                limitations=['Resposta generativa ignorada por baixa sobreposição com os trechos e as frases extraídas.'],
            )
    if not has_source_marker(answer, len(contexts)):
        return GeneratedAnswerValidation(
            action='fallback_extractive', reason='no_source_marker',
            limitations=['Resposta generativa ignorada: o modelo não citou nenhum trecho com [n].'],
        )

    return GeneratedAnswerValidation(action='accept')
