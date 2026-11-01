"""Span da resposta: com IA, a resposta só sai se o modelo copiar dos trechos um span que exista neles.

O modelo pequeno (3B) erra muito ao julgar "o texto fala disso?", mas acerta ao copiar o trecho que responde
ou escrever NAO. A cópia é conferida contra o texto do trecho, então a decisão final continua determinística.
Medido em 16 pares (6 paráfrases, 10 negativas): 15 acertos com qchat; o erro foi uma negativa com o mesmo
vocabulário do trecho ("orçamento do projeto de migração" contra o orçamento de outro projeto).
"""

import re
import unicodedata
from dataclasses import dataclass
from typing import Literal

from escolio.corpus.ask_claims import _citation_from_corpus_hit
from escolio.notes.schemas import Note
from escolio.retrieval.models import AnswerClaim, SearchHit
from escolio.retrieval.rag import (
    SENTENCE_SPLIT_PATTERN,
    _question_needs_multiple_claims,
)
from escolio.retrieval.search import match_terms_in_text

# (motivo da recusa, limitações exibidas ao usuário), como em ask_grounding.
Rejection = tuple[str, list[str]]
SpanStatus = Literal["verified", "not_found", "unavailable"]

SPAN_CONTEXT_HITS = 3
SPAN_SYSTEM_PROMPT = "Voce extrai respostas de um texto. Nunca invente. Se a informacao pedida nao estiver no texto, responda NAO."
SPAN_INSTRUCTION = (
    "Responda copiando o trecho exato do TEXTO que contem a informacao pedida. "
    "Se o TEXTO tratar de outro assunto ou nao trouxer exatamente a informacao pedida, escreva NAO."
)
SPAN_LABEL_PATTERN = re.compile(r"^\s*(?:resposta|trecho)\s*:\s*", re.IGNORECASE)
SPAN_NOT_FOUND: Rejection = (
    "no_supported_span",
    ["A IA não encontrou nos trechos recuperados a informação pedida pela pergunta."],
)


@dataclass(frozen=True)
class VerifiedSpan:
    text: str
    hit: SearchHit
    sentence: str


def _normalize(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text.lower())
    without_accents = "".join(
        char for char in decomposed if not unicodedata.combining(char)
    )
    return " ".join(re.findall(r"[a-z0-9]+", without_accents))


def _sentences(text: str) -> list[str]:
    return [
        part.strip()
        for part in SENTENCE_SPLIT_PATTERN.split(text)
        if part and part.strip()
    ]


def _sentence_containing(text: str, normalized_span: str) -> str:
    """Menor janela de até 3 frases seguidas que contém o span; o próprio texto se não achar."""
    sentences = _sentences(text)
    for size in range(1, 4):
        for start in range(len(sentences) - size + 1):
            window = " ".join(sentences[start : start + size])
            if normalized_span in _normalize(window):
                return window
    return text.strip()


def supports_span_check(provider: object | None) -> bool:
    return provider is not None and callable(getattr(provider, "complete", None))


def span_check_messages(question: str, texts: list[str]) -> list[dict[str, str]]:
    joined = "\n\n".join(texts)
    return [
        {"role": "system", "content": SPAN_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": f"TEXTO:\n{joined}\n\nPERGUNTA: {question}\n\n{SPAN_INSTRUCTION}",
        },
    ]


def _ask_span(provider: object, question: str, hits: list[SearchHit]) -> str:
    messages = span_check_messages(question, [hit.chunk.chunk_text for hit in hits])
    return provider.complete(messages, temperature=0)  # type: ignore[attr-defined]


def _is_no_marker(part: str) -> bool:
    words = part.split()
    return bool(words) and words[0] == "nao" and len(words) <= 3


def _span_parts(raw: str) -> tuple[str, list[str]]:
    span = SPAN_LABEL_PATTERN.sub("", raw.strip()).strip(" \"'.")
    parts = [
        part for part in (_normalize(sentence) for sentence in _sentences(span)) if part
    ]
    return span, list(dict.fromkeys(parts))


def _is_no_answer(raw: str) -> bool:
    _, parts = _span_parts(raw)
    return all(_is_no_marker(part) for part in parts)


def _verified(raw: str, question: str, hits: list[SearchHit]) -> VerifiedSpan | None:
    """Cada frase do span precisa existir no mesmo trecho; a ordem não importa (o modelo às vezes inverte).

    Um "NAO" ao lado de frases copiadas vale para outro trecho e é ignorado.
    """
    span, parts = _span_parts(raw)
    parts = [part for part in parts if not _is_no_marker(part)]
    if not parts:
        return None
    # Span feito só de palavras da pergunta não responde nada (eco da pergunta).
    if set(" ".join(parts).split()) <= set(_normalize(question).split()):
        return None
    for hit in hits:
        text = _normalize(hit.chunk.chunk_text)
        if all(part in text for part in parts):
            sentence = " ".join(
                dict.fromkeys(
                    _sentence_containing(hit.chunk.chunk_text, part) for part in parts
                )
            )
            return VerifiedSpan(span, hit, sentence)
    return None


def verify_answer_span(
    provider: object, question: str, hits: list[SearchHit]
) -> tuple[SpanStatus, VerifiedSpan | None]:
    """Pede ao modelo o span que responde e confere se ele existe em um dos trechos."""
    candidates = hits[:SPAN_CONTEXT_HITS]
    if not candidates:
        return "not_found", None
    try:
        raw = _ask_span(provider, question, candidates)
        if _is_no_answer(raw):
            return "not_found", None
        verified = _verified(raw, question, candidates)
        if verified is not None:
            return "verified", verified
        # Eco da instrução ou paráfrase em vez de cópia: com um trecho por vez o modelo costuma copiar.
        for hit in candidates:
            verified = _verified(_ask_span(provider, question, [hit]), question, [hit])
            if verified is not None:
                return "verified", verified
    except Exception:
        return "unavailable", None
    return "not_found", None


def span_gate(
    provider: object, question: str, hits: list[SearchHit], vocabulary: Rejection | None
) -> tuple[Rejection | None, VerifiedSpan | None]:
    """Com IA, sem span verificado não há resposta; IA fora do ar mantém a regra do modo extrativo."""
    status, verified = verify_answer_span(provider, question, hits)
    if status == "verified":
        return None, verified
    if status == "not_found":
        return vocabulary or SPAN_NOT_FOUND, None
    return vocabulary, None


def claim_from_verified_span(
    verified: VerifiedSpan, note_lookup: dict[str, Note]
) -> AnswerClaim:
    return AnswerClaim(
        text=verified.sentence,
        citations=[
            _citation_from_corpus_hit(verified.hit, note_lookup, verified.sentence)
        ],
        support_level="partial",
    )


def _has_new_information(sentence: str, question_tokens: set[str]) -> bool:
    """Número ou nome próprio (maiúscula fora do início) que a pergunta não trouxe."""
    for index, word in enumerate(
        re.findall(r"[0-9A-Za-zÀ-ÖØ-öø-ÿ][0-9A-Za-zÀ-ÖØ-öø-ÿ.-]*", sentence)
    ):
        normalized = _normalize(word)
        if not normalized or normalized in question_tokens:
            continue
        if any(char.isdigit() for char in word) or (index > 0 and word[0].isupper()):
            return True
    return False


def focus_extractive_answer(question: str, query_terms: list[str], answer: str) -> str:
    """Resposta de uma pergunta só: fica a frase que traz informação nova e mais termos da pergunta.

    ponytail: heurística de tipo de resposta (número ou nome próprio); sem esse sinal, a resposta não muda.
    """
    sentences = _sentences(answer)
    if len(sentences) < 2 or _question_needs_multiple_claims(question):
        return answer
    question_tokens = set(_normalize(question).split())
    informative = [
        sentence
        for sentence in sentences
        if _has_new_information(sentence, question_tokens)
    ]
    if not informative:
        return answer
    best = max(
        informative,
        key=lambda sentence: (
            len(match_terms_in_text(query_terms, sentence)[0]),
            -sentences.index(sentence),
        ),
    )
    return best if match_terms_in_text(query_terms, best)[0] else answer


def final_extractive_answer(
    question: str, query_terms: list[str], answer: str, verified: VerifiedSpan | None
) -> str:
    """Resposta mostrada quando não há texto gerado: a frase do span verificado ou o recorte heurístico."""
    if verified is not None and not _question_needs_multiple_claims(question):
        return verified.sentence
    return focus_extractive_answer(question, query_terms, answer)
