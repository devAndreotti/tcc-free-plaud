"""Span da resposta: segunda chance, com IA, da pergunta que cita um termo ausente do corpus.

A regra de vocabulário recusa paráfrases ("coordenar" quando a nota diz "responsável"). Com IA, essa pergunta
só passa se o modelo tirar dos trechos a informação pedida. O modelo pequeno (3B) erra muito ao julgar "o texto
fala disso?", mas acerta ao copiar o trecho que responde ou escrever NAO. A cópia é conferida contra o texto: as
palavras que a resposta acrescenta à pergunta precisam estar no mesmo trecho. A decisão final continua
determinística, e um valor inventado não passa.

Também mora aqui o recorte da resposta extrativa (a frase que responde, não o trecho inteiro).
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
from escolio.retrieval.search import STOPWORDS, match_terms_in_text

# (motivo da recusa, limitações exibidas ao usuário), como em ask_grounding.
Rejection = tuple[str, list[str]]
SpanStatus = Literal['verified', 'not_found', 'unavailable']

SPAN_CONTEXT_HITS = 3
SPAN_SYSTEM_PROMPT = 'Voce extrai respostas de um texto. Nunca invente. Se a informacao pedida nao estiver no texto, responda NAO.'
SPAN_INSTRUCTION = (
    'Responda copiando o trecho exato do TEXTO que contem a informacao pedida. '
    'Se o TEXTO tratar de outro assunto ou nao trouxer exatamente a informacao pedida, escreva NAO.'
)
# Rótulo e numeração que o modelo põe em volta da cópia ("Resposta encontrada no texto:", "1.").
SPAN_LABEL_LINE = re.compile(r'^[^\n:]{0,40}\b(?:resposta|trecho)\b[^\n:]{0,40}:\s*', re.IGNORECASE | re.MULTILINE)
LIST_MARKER = re.compile(r'^\s*(?:\d+[.)]|[-*•])\s+', re.MULTILINE)
# Palavras que ligam a resposta à pergunta sem trazer conteúdo do trecho.
FILLER_TOKENS = frozenset(
    {'e', 'foi', 'foram', 'sao', 'era', 'ser', 'esta', 'estao', 'tem', 'ha', 'pelo', 'pela', 'pelos', 'pelas', 'sobre', 'entre'}
    | {'resposta', 'encontrada', 'encontrado', 'texto', 'trecho', 'pergunta', 'informacao', 'pedida', 'exato', 'exata'}
)
# Mesma raiz com outra terminação (adotado / adotar): 5 letras iniciais em comum, só em palavras de 6 ou mais.
PREFIX_LENGTH = 5


@dataclass(frozen=True)
class VerifiedSpan:
    text: str
    hit: SearchHit
    sentence: str


def _normalize(text: str) -> str:
    decomposed = unicodedata.normalize('NFKD', text.lower())
    without_accents = ''.join(char for char in decomposed if not unicodedata.combining(char))
    return ' '.join(re.findall(r'[a-z0-9]+', without_accents))


IGNORED_TOKENS = FILLER_TOKENS | {_normalize(word) for word in STOPWORDS}


def _sentences(text: str) -> list[str]:
    return [part.strip() for part in SENTENCE_SPLIT_PATTERN.split(text) if part and part.strip()]


def _has_token(token: str, tokens: set[str]) -> bool:
    if token in tokens:
        return True
    if token.isdigit() or len(token) < PREFIX_LENGTH + 1:
        return False
    return any(candidate.startswith(token[:PREFIX_LENGTH]) for candidate in tokens)


def _covers(text: str, content: list[str]) -> bool:
    tokens = set(_normalize(text).split())
    return all(_has_token(token, tokens) for token in content)


def _window_with(text: str, content: list[str]) -> str:
    """Menor janela de até 3 frases seguidas com todas as palavras do span; o próprio texto se não houver."""
    sentences = _sentences(text)
    for size in range(1, 4):
        for start in range(len(sentences) - size + 1):
            window = ' '.join(sentences[start : start + size])
            if _covers(window, content):
                return window
    return text.strip()


def supports_span_check(provider: object | None) -> bool:
    return provider is not None and callable(getattr(provider, 'complete', None))


def span_check_messages(question: str, texts: list[str]) -> list[dict[str, str]]:
    joined = '\n\n'.join(texts)
    return [
        {'role': 'system', 'content': SPAN_SYSTEM_PROMPT},
        {'role': 'user', 'content': f'TEXTO:\n{joined}\n\nPERGUNTA: {question}\n\n{SPAN_INSTRUCTION}'},
    ]


def _ask_span(provider: object, question: str, hits: list[SearchHit]) -> str:
    messages = span_check_messages(question, [hit.chunk.chunk_text for hit in hits])
    return provider.complete(messages, temperature=0)  # type: ignore[attr-defined]


def _clean_span(raw: str) -> str:
    """Tira eco da instrução, rótulo e numeração em volta da cópia."""
    text = raw
    for sentence in _sentences(SPAN_INSTRUCTION):
        text = text.replace(sentence, ' ')
    text = LIST_MARKER.sub('', SPAN_LABEL_LINE.sub('', text))
    return text.strip().strip(' "\'.')


def _span_parts(span: str) -> list[str]:
    return list(dict.fromkeys(part for part in (_normalize(sentence) for sentence in _sentences(span)) if part))


def _is_no_marker(part: str) -> bool:
    words = part.split()
    return bool(words) and words[0] == 'nao' and len(words) <= 3


def _is_no_answer(raw: str) -> bool:
    parts = _span_parts(_clean_span(raw))
    return bool(parts) and all(_is_no_marker(part) for part in parts)


def _verified(raw: str, question: str, hits: list[SearchHit]) -> VerifiedSpan | None:
    """As palavras que o span acrescenta à pergunta precisam estar no mesmo trecho, em qualquer ordem.

    Um "NAO" ao lado de frases copiadas vale para outro trecho e é ignorado. Span feito só de palavras da
    pergunta (eco) não responde nada.
    """
    span = _clean_span(raw)
    parts = [part for part in _span_parts(span) if not _is_no_marker(part)]
    question_tokens = set(_normalize(question).split())
    content = [
        token
        for token in dict.fromkeys(' '.join(parts).split())
        if token not in question_tokens and token not in IGNORED_TOKENS and (len(token) > 1 or token.isdigit())
    ]
    if not content:
        return None
    for hit in hits:
        if _covers(hit.chunk.chunk_text, content):
            return VerifiedSpan(span, hit, _window_with(hit.chunk.chunk_text, content))
    return None


def verify_answer_span(provider: object, question: str, hits: list[SearchHit]) -> tuple[SpanStatus, VerifiedSpan | None]:
    """Pede ao modelo o span que responde e confere se ele está em um dos trechos."""
    candidates = hits[:SPAN_CONTEXT_HITS]
    if not candidates:
        return 'not_found', None
    try:
        raw = _ask_span(provider, question, candidates)
        if _is_no_answer(raw):
            # Com vários trechos longos o modelo diz NAO demais; o primeiro trecho sozinho tem uma segunda chance.
            first = candidates[:1]
            verified = _verified(_ask_span(provider, question, first), question, first) if len(candidates) > 1 else None
            return ('verified', verified) if verified is not None else ('not_found', None)
        verified = _verified(raw, question, candidates)
        if verified is not None:
            return 'verified', verified
        # Eco da instrução ou paráfrase sem as palavras do trecho: um trecho por vez o modelo costuma copiar.
        for hit in candidates:
            verified = _verified(_ask_span(provider, question, [hit]), question, [hit])
            if verified is not None:
                return 'verified', verified
    except Exception:
        return 'unavailable', None
    return 'not_found', None


def span_gate(
    provider: object, question: str, hits: list[SearchHit], vocabulary: Rejection
) -> tuple[Rejection | None, VerifiedSpan | None]:
    """Segunda chance da pergunta que o vocabulário recusaria: passa só com span verificado.

    Aplicar o portão a toda resposta foi medido e piorou: com qchat, positivas respondidas caíram de 35/39
    para 24/39 e negativas de 6/34 para 0/34 (o modelo diz NAO demais em trecho técnico longo).
    """
    status, verified = verify_answer_span(provider, question, hits)
    return (None, verified) if status == 'verified' else (vocabulary, None)


def claim_from_verified_span(verified: VerifiedSpan, note_lookup: dict[str, Note]) -> AnswerClaim:
    return AnswerClaim(
        text=verified.sentence,
        citations=[_citation_from_corpus_hit(verified.hit, note_lookup, verified.sentence)],
        support_level='partial',
    )


def _has_new_information(sentence: str, question_tokens: set[str]) -> bool:
    """Número ou nome próprio (maiúscula fora do início) que a pergunta não trouxe."""
    for index, word in enumerate(re.findall(r'[0-9A-Za-zÀ-ÖØ-öø-ÿ][0-9A-Za-zÀ-ÖØ-öø-ÿ.-]*', sentence)):
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
    informative = [sentence for sentence in sentences if _has_new_information(sentence, question_tokens)]
    if not informative:
        return answer
    best = max(
        informative,
        key=lambda sentence: (len(match_terms_in_text(query_terms, sentence)[0]), -sentences.index(sentence)),
    )
    return best if match_terms_in_text(query_terms, best)[0] else answer


def final_extractive_answer(question: str, query_terms: list[str], answer: str, verified: VerifiedSpan | None) -> str:
    """Resposta mostrada quando não há texto gerado: a frase do span verificado ou o recorte heurístico."""
    if verified is not None and not _question_needs_multiple_claims(question):
        return verified.sentence
    return focus_extractive_answer(question, query_terms, answer)
