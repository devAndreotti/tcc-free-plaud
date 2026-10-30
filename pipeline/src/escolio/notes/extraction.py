"""Extração estruturada opcional (decisões, ações, tópicos) via LLM.

Passo extra sobre a nota determinística: `structure_document` continua igual.
Ligado pela flag `extract_structure` (desligada por padrão). Toda decisão ou
ação devolvida pelo modelo passa pela guarda de entidades (nomes, números com
unidade, datas) e pelo limiar lexical; owner e due sem suporte viram None;
tópicos sem termo de conteúdo na nota são descartados. Regras em
`extraction_guard.py`.
"""

import json
from collections import Counter
from collections.abc import Callable
from typing import Any

from pydantic import ValidationError

from escolio.app.config import Settings, get_settings
from escolio.notes.extraction_guard import (
    REJECT_ENTITY,
    REJECT_LEXICAL,
    ExtractionGuard,
)
from escolio.notes.markdown import render_note_markdown
from escolio.notes.schemas import ActionItem, Decision, Note, NoteExtraction
from escolio.providers.answer import OpenAICompatibleAnswerProvider, get_answer_provider

LLMCallable = Callable[[str], str]

DEFAULT_MIN_OVERLAP = 0.5
MAX_TOPICS = 8
LEXICAL_WARNING = 'Guarda lexical: {count} item(ns) descartado(s) por pouca sobreposição com a nota.'
ENTITY_WARNING = (
    'Guarda de entidades: {count} item(ns) descartado(s) porque nome, número ou data não aparece na nota.'
)
TOPIC_WARNING = 'Guarda de tópicos: {count} tópico(s) descartado(s) sem termo de conteúdo na nota.'
EXTRACTION_UNAVAILABLE_WARNING = (
    'Extração indisponível: o provider de resposta não aceita chamadas de extração '
    '(use openai-compatible, ollama ou lmstudio).'
)
NO_JSON_WARNING = 'Extração ignorada: a resposta do LLM não tem um objeto JSON válido.'
NULL_STRINGS = {'', 'null', 'none', 'n/a', 'nenhum', 'nenhuma'}

EXTRACTION_INSTRUCTIONS = (
    'Você extrai informações estruturadas de uma nota em português brasileiro. '
    'Responda SOMENTE com um objeto JSON válido, sem texto antes ou depois e sem cercas de código, '
    'no formato: '
    '{"topics": ["tema"], "decisions": [{"text": "..."}], '
    '"action_items": [{"text": "...", "owner": "pessoa ou null", "due": "prazo ou null"}]}. '
    'Regras: use somente o que está escrito na NOTA e não invente nomes, datas ou responsáveis. '
    'decisions são decisões tomadas explicitamente na nota. '
    'action_items são tarefas com ação clara; owner e due só quando a nota disser, caso contrário null. '
    f'topics são até {MAX_TOPICS} temas centrais, curtos. '
    'Se uma categoria não tiver itens, use lista vazia.'
)

_DECODER = json.JSONDecoder()


def build_extraction_prompt(text: str) -> str:
    return f'{EXTRACTION_INSTRUCTIONS}\n\nNOTA:\n<<<\n{text}\n>>>'


def _first_json_object(raw: str) -> dict[str, Any] | None:
    """Primeiro objeto JSON do texto; ignora cercas ```json e ruído antes ou depois."""
    index = raw.find('{')
    while index != -1:
        try:
            value, _ = _DECODER.raw_decode(raw, index)
        except json.JSONDecodeError:
            value = None
        if isinstance(value, dict):
            return value
        index = raw.find('{', index + 1)
    return None


def _as_items(raw: object) -> list[object]:
    return raw if isinstance(raw, list) else []


def _parse_topics(raw: object) -> list[str]:
    """Tópicos únicos e não vazios; o corte em MAX_TOPICS fica depois da guarda."""
    topics: list[str] = []
    for item in _as_items(raw):
        if isinstance(item, str) and item.strip() and item.strip() not in topics:
            topics.append(item.strip())
    return topics


def _parse_items[ItemT: (Decision, ActionItem)](
    raw: object, model: type[ItemT]
) -> tuple[list[ItemT], int]:
    """Valida cada item isoladamente; devolve (válidos, quantidade inválida)."""
    valid: list[ItemT] = []
    invalid = 0
    for item in _as_items(raw):
        candidate = {'text': item} if isinstance(item, str) else item
        try:
            valid.append(model.model_validate(candidate))
        except ValidationError:
            invalid += 1
    return valid, invalid


def _clean_optional(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    cleaned = value.strip()
    return None if cleaned.lower() in NULL_STRINGS else cleaned


def _scrub_action(item: ActionItem, guard: ExtractionGuard) -> ActionItem:
    """Owner e due sem suporte na nota viram None; a tarefa em si continua."""
    owner = _clean_optional(item.owner)
    due = _clean_optional(item.due)
    if owner and not guard.owner_supported(owner):
        owner = None
    if due and not guard.due_supported(due):
        due = None
    return item.model_copy(update={'owner': owner, 'due': due})


def _rejection_warnings(rejections: Counter[str], rejected_topics: int) -> list[str]:
    """Um aviso agregado por motivo; nunca inclui o texto do item."""
    warnings: list[str] = []
    if rejections[REJECT_LEXICAL]:
        warnings.append(LEXICAL_WARNING.format(count=rejections[REJECT_LEXICAL]))
    if rejections[REJECT_ENTITY]:
        warnings.append(ENTITY_WARNING.format(count=rejections[REJECT_ENTITY]))
    if rejected_topics:
        warnings.append(TOPIC_WARNING.format(count=rejected_topics))
    return warnings


def extract_structure(
    text: str,
    llm: LLMCallable,
    *,
    min_overlap: float = DEFAULT_MIN_OVERLAP,
    strict_entities: bool = True,
) -> NoteExtraction:
    """Extrai decisões, ações e tópicos da nota usando `llm` (prompt -> texto).

    `min_overlap` é o limiar lexical (segundo critério). `strict_entities=False`
    desliga só a checagem de nomes, números e datas; a checagem de tópicos e o
    limiar lexical continuam ativos.

    Nunca levanta por causa do modelo: falha de transporte ou JSON ilegível
    devolve extração vazia com aviso em `warnings`.
    """
    try:
        raw_output = llm(build_extraction_prompt(text))
    except Exception as exc:
        return NoteExtraction(warnings=[f'Extração indisponível: {exc}'])

    payload = _first_json_object(raw_output) if isinstance(raw_output, str) else None
    if payload is None:
        return NoteExtraction(warnings=[NO_JSON_WARNING])

    guard = ExtractionGuard(text, min_overlap=min_overlap, strict_entities=strict_entities)
    decisions, invalid_decisions = _parse_items(payload.get('decisions'), Decision)
    actions, invalid_actions = _parse_items(payload.get('action_items'), ActionItem)
    rejections: Counter[str] = Counter()
    kept_decisions: list[Decision] = []
    for decision in decisions:
        reason = guard.item_rejection(decision.text)
        if reason is None:
            kept_decisions.append(decision)
        else:
            rejections[reason] += 1
    kept_actions: list[ActionItem] = []
    for action in actions:
        reason = guard.item_rejection(action.text)
        if reason is None:
            kept_actions.append(_scrub_action(action, guard))
        else:
            rejections[reason] += 1
    raw_topics = _parse_topics(payload.get('topics'))
    topics = [topic for topic in raw_topics if guard.topic_supported(topic)]
    rejected_topics = len(raw_topics) - len(topics)
    return NoteExtraction(
        topics=topics[:MAX_TOPICS],
        decisions=kept_decisions,
        action_items=kept_actions,
        discarded=(
            invalid_decisions
            + invalid_actions
            + sum(rejections.values())
            + rejected_topics
        ),
        warnings=_rejection_warnings(rejections, rejected_topics),
    )


def make_provider_llm(settings: Settings | None = None) -> LLMCallable | None:
    """Callable de prompt sobre o provider de resposta já configurado.

    Retorna None quando o provider é 'extractive' (não há LLM para chamar).
    Reutiliza o endpoint, chave e timeout de `answer_*`, sem HTTP duplicado.
    """
    resolved = settings or get_settings()
    provider = get_answer_provider(
        resolved.answer_provider,
        model=resolved.answer_model,
        base_url=resolved.answer_base_url,
        api_key=resolved.answer_api_key,
        temperature=resolved.answer_temperature,
        max_tokens=resolved.answer_max_tokens,
        timeout_seconds=resolved.answer_timeout_seconds,
    )
    if not isinstance(provider, OpenAICompatibleAnswerProvider):
        return None

    def llm(prompt: str) -> str:
        return provider.complete([{'role': 'user', 'content': prompt}], temperature=0.0)

    return llm


def apply_extraction(note: Note, extraction: NoteExtraction) -> Note:
    """Anexa a extração à nota e re-renderiza o Markdown.

    Com extração vazia, o Markdown fica idêntico ao determinístico.
    """
    note.extraction = extraction
    if not extraction.is_empty():
        note.topics = list(extraction.topics)
        note.tasks = [item.label() for item in extraction.action_items]
    note.structured_markdown = render_note_markdown(note)
    return note


def enrich_note(note: Note, settings: Settings | None = None) -> Note:
    """Aplica a extração LLM só quando `extract_structure` está ligada."""
    resolved = settings or get_settings()
    if not resolved.extract_structure:
        return note
    llm = make_provider_llm(resolved)
    if llm is None:
        return apply_extraction(note, NoteExtraction(warnings=[EXTRACTION_UNAVAILABLE_WARNING]))
    return apply_extraction(note, extract_structure(note.normalized_text, llm))
