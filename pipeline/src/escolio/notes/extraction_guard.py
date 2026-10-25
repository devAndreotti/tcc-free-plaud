"""Guardas determinísticas da extração estruturada: conferem a saída do LLM contra a nota.

Ordem de aplicação (usada por `extraction.py`):

1. Decisões e ações: entidades (nomes próprios, siglas, números com unidade e
   datas) precisam aparecer na nota; depois entra o limiar lexical.
2. Owner e due: owner precisa aparecer na nota; due com data ou dia da semana
   precisa bater com um deles. Sem suporte, o campo vira None e o item fica.
3. Tópicos: pelo menos um termo de conteúdo precisa estar na nota.

Limites conhecidos (docs/experimentos/19, item 6):

- Datas são comparadas literalmente: '09/09/2025' não bate com 'nove de setembro'.
- Número com unidade só é confrontado com a unidade da nota quando a nota traz uma
  (nota com '1500' aceita 'R$ 1.500'; nota com '1500 dias' rejeita 'R$ 1.500').
- Toda palavra capitalizada do item é checada, inclusive a primeira (que é o
  sujeito: 'Maria aprova...'). Um verbo no início do item que não aparece na nota
  em nenhuma caixa é descartado como se fosse entidade.
"""

import re
import unicodedata
from dataclasses import dataclass
from decimal import Decimal

from escolio.text_tokens import STOPWORDS_PT, content_tokens, lexical_groundedness

REJECT_ENTITY = 'entity'
REJECT_LEXICAL = 'lexical'

# Os padrões rodam sobre texto dobrado (sem acento, minúsculas), ver `_fold`.
_NUM = r'(?:\d{1,3}(?:\.\d{3})+(?:,\d+)?|\d+(?:,\d+)?(?:\.\d+)?)'
_UNIT = (
    r'%|por cento|dias?|horas?|h|minutos?|min|semanas?|meses|mes|anos?|reais|real'
    r'|kg|km|gb|mb|pessoas?|vezes|paginas?|capitulos?'
)
_MONTH = 'janeiro|fevereiro|marco|abril|maio|junho|julho|agosto|setembro|outubro|novembro|dezembro'
_CURRENCY = re.compile(rf'r\$\s*({_NUM})(?![\w/-])')
_NUMBER_UNIT = re.compile(rf'(?<![\w/.,-])({_NUM})\s*({_UNIT})(?![a-z])')
_BARE_NUMBER = re.compile(rf'(?<![\w/.,-])({_NUM})(?![\w/-])')
_NUMERIC_DATE = re.compile(r'(?<![\d/])(\d{1,2})[/-](\d{1,2})(?:[/-](\d{4}|\d{2}))?(?![\d/])')
_TEXTUAL_DATE = re.compile(rf'(?<!\w)\d{{1,2}}\s+de\s+(?:{_MONTH})(?:\s+de\s+\d{{4}})?(?!\w)')
_FOLDED_WORD = re.compile(r'[a-z0-9]+')
_ENTITY_TOKEN = re.compile(r'[^\W\d_][^\W_]*')
_RELATIVE_DAYS = frozenset(
    {'segunda', 'terca', 'quarta', 'quinta', 'sexta', 'sabado', 'domingo', 'amanha', 'hoje', 'ontem'}
)
_UNIT_CANON = {'%': '%', 'por cento': '%', 'h': 'hora', 'min': 'minuto', 'meses': 'mes', 'real': 'reais'}


def _fold(text: str) -> str:
    """Dobra caixa e acentos caractere a caractere, preservando o comprimento do texto."""
    chars = []
    for char in text:
        base = unicodedata.normalize('NFKD', char).encode('ascii', 'ignore').decode('ascii').lower()
        chars.append(base[:1] or char)
    return ''.join(chars)


def _canon_unit(raw: str) -> str:
    if raw in _UNIT_CANON:
        return _UNIT_CANON[raw]
    return raw.removesuffix('s')


def _parse_number(raw: str) -> Decimal:
    """'1.500' e '1.500,50' são pt-BR (ponto de milhar); '1,5' é decimal."""
    if re.fullmatch(r'\d{1,3}(?:\.\d{3})+(?:,\d+)?', raw):
        raw = raw.replace('.', '')
    return Decimal(raw.replace(',', '.'))


def _full_year(raw: str | None) -> int | None:
    if raw is None:
        return None
    return int(raw) if len(raw) == 4 else 2000 + int(raw)


@dataclass(frozen=True)
class _Scan:
    # (valor, unidade canônica ou None). Números sem unidade só existem na nota.
    numbers: tuple[tuple[Decimal, str | None], ...]
    # (dia, mês, ano ou None), já normalizados.
    numeric_dates: tuple[tuple[int, int, int | None], ...]
    # Datas por extenso, literais e sem espaços duplos ('9 de setembro de 2025').
    textual_dates: tuple[str, ...]
    # Trechos com número+unidade, moeda ou data: são verificados pela guarda de entidades.
    checked_spans: tuple[tuple[int, int], ...]


def _scan(folded: str) -> _Scan:
    spans: list[tuple[int, int]] = []
    checked: list[tuple[int, int]] = []
    numbers: list[tuple[Decimal, str | None]] = []
    numeric_dates: list[tuple[int, int, int | None]] = []
    textual_dates: list[str] = []

    def free(match: re.Match[str]) -> bool:
        return all(match.end() <= start or match.start() >= end for start, end in spans)

    for match in _NUMERIC_DATE.finditer(folded):
        numeric_dates.append((int(match[1]), int(match[2]), _full_year(match[3])))
        spans.append(match.span())
        checked.append(match.span())
    for match in _TEXTUAL_DATE.finditer(folded):
        textual_dates.append(' '.join(match[0].split()))
        spans.append(match.span())
        checked.append(match.span())
    for match in _CURRENCY.finditer(folded):
        if free(match):
            numbers.append((_parse_number(match[1]), 'reais'))
            spans.append(match.span())
            checked.append(match.span())
    for match in _NUMBER_UNIT.finditer(folded):
        if free(match):
            numbers.append((_parse_number(match[1]), _canon_unit(match[2])))
            spans.append(match.span())
            checked.append(match.span())
    for match in _BARE_NUMBER.finditer(folded):
        if free(match):
            numbers.append((_parse_number(match[1]), None))
            spans.append(match.span())
    return _Scan(
        numbers=tuple(numbers),
        numeric_dates=tuple(numeric_dates),
        textual_dates=tuple(textual_dates),
        checked_spans=tuple(checked),
    )


def _without_checked_spans(text: str) -> str:
    """Remove números com unidade, moedas e datas do texto (o lexical não deve contá-los duas vezes)."""
    spans = _scan(_fold(text)).checked_spans
    if not spans:
        return text
    chars = list(text)
    for start, end in spans:
        for index in range(start, end):
            chars[index] = ' '
    return ''.join(chars)


def _entity_tokens(text: str) -> list[str]:
    """Palavras capitalizadas (nomes e siglas), dobradas e sem stopwords."""
    tokens: list[str] = []
    for raw in _ENTITY_TOKEN.findall(text):
        if len(raw) < 2 or not raw[0].isupper():
            continue
        folded = _fold(raw)
        if folded not in STOPWORDS_PT:
            tokens.append(folded)
    return tokens


class ExtractionGuard:
    """Confere decisões, ações, owner, due e tópicos contra o texto da nota."""

    def __init__(self, note_text: str, *, min_overlap: float, strict_entities: bool) -> None:
        self._note_text = note_text
        self._min_overlap = min_overlap
        self._strict = strict_entities
        folded = _fold(note_text)
        self._words = frozenset(_FOLDED_WORD.findall(folded))
        self._collapsed = ' '.join(folded.split())
        note_scan = _scan(folded)
        self._numbers = note_scan.numbers
        self._numeric_dates = frozenset(note_scan.numeric_dates)
        self._note_content = content_tokens(note_text)

    def item_rejection(self, text: str) -> str | None:
        """Motivo para descartar uma decisão ou ação; None quando ela passa."""
        if not content_tokens(text):
            return REJECT_LEXICAL
        if self._strict and not self._entities_supported(text):
            return REJECT_ENTITY
        checked = _without_checked_spans(text) if self._strict else text
        if lexical_groundedness(checked, [self._note_text]) < self._min_overlap:
            return REJECT_LEXICAL
        return None

    def owner_supported(self, owner: str) -> bool:
        if self._strict and not all(token in self._words for token in _entity_tokens(owner)):
            return False
        return lexical_groundedness(owner, [self._note_text]) >= self._min_overlap

    def due_supported(self, due: str) -> bool:
        if self._strict and not self._due_entities_supported(due):
            return False
        return lexical_groundedness(due, [self._note_text]) >= self._min_overlap

    def topic_supported(self, topic: str) -> bool:
        return bool(content_tokens(topic) & self._note_content)

    def _entities_supported(self, text: str) -> bool:
        if not all(token in self._words for token in _entity_tokens(text)):
            return False
        return self._scan_supported(_scan(_fold(text)))

    def _due_entities_supported(self, due: str) -> bool:
        folded = _fold(due)
        if not self._scan_supported(_scan(folded)):
            return False
        return all(word in self._words for word in _FOLDED_WORD.findall(folded) if word in _RELATIVE_DAYS)

    def _scan_supported(self, scan: _Scan) -> bool:
        for value, unit in scan.numbers:
            if unit is not None and not self._has_number(value, unit):
                return False
        for day, month, year in scan.numeric_dates:
            if not any(
                note_day == day and note_month == month and (year is None or note_year == year)
                for note_day, note_month, note_year in self._numeric_dates
            ):
                return False
        return all(
            re.search(rf'(?<!\w){re.escape(literal)}(?!\w)', self._collapsed) is not None
            for literal in scan.textual_dates
        )

    def _has_number(self, value: Decimal, unit: str) -> bool:
        return any(
            note_value == value and (note_unit is None or note_unit == unit)
            for note_value, note_unit in self._numbers
        )
