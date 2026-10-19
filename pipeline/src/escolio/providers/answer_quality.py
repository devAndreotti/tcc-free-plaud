"""Qualidade da resposta gerativa: sentinela de abstenção fora do começo e título copiado do contexto."""

import re

from escolio.retrieval.search import TOKEN_PATTERN, _strip_accents

# Token da sentinela NAO_ENCONTRADO sem acento e em minúsculas: NAO_ENCONTRADOS não casa.
NO_ANSWER_WORD = 'nao_encontrado'
ECHOED_TITLE_MAX_WORDS = 10
# Linha de título do contexto: "title: X" do cabeçalho ou "# X" de um trecho. Claims ficam de fora: são frases da nota.
# ponytail: só "title:" e headings "#". Rótulo de seção sem "#" (ex.: "DECISÕES TOMADAS") escapa; incluir linhas curtas
# quando a medição com qchat mostrar cópias sem rejeitar respostas legítimas.
TITLE_LINE_PATTERN = re.compile(r'^[ \t]*(?:#{1,6}[ \t]+|title:[ \t]*)(.+)$', re.IGNORECASE | re.MULTILINE)
ANSWER_LABEL_PATTERN = re.compile(r'^\s*(?:t[ií]tulo|title)\s*:', re.IGNORECASE)


def _tokens(text: str) -> list[str]:
    return [_strip_accents(token).casefold() for token in TOKEN_PATTERN.findall(text)]


def contains_token_sequence(tokens: list[str], sequence: list[str]) -> bool:
    if not sequence or len(sequence) > len(tokens):
        return False
    width = len(sequence)
    return any(tokens[index : index + width] == sequence for index in range(len(tokens) - width + 1))


def is_no_answer_sentinel(answer: str, contexts: list[str]) -> bool:
    """NAO_ENCONTRADO no começo é abstenção; no meio, só é abstenção se os contextos não tiverem a palavra."""
    tokens = _tokens(answer)
    if NO_ANSWER_WORD not in tokens:
        return False
    if tokens[0] == NO_ANSWER_WORD:
        return True
    return NO_ANSWER_WORD not in _tokens('\n'.join(contexts))


def is_echoed_title(answer: str, contexts: list[str]) -> bool:
    """Resposta curta que só copia um título ou cabeçalho de algum contexto, sem responder à pergunta."""
    words = _tokens(ANSWER_LABEL_PATTERN.sub('', answer, count=1))
    if not 0 < len(words) <= ECHOED_TITLE_MAX_WORDS:
        return False
    answer_words = set(words)
    single_line = '\n' not in answer.strip()
    for line in TITLE_LINE_PATTERN.findall('\n'.join(contexts)):
        title = _tokens(line)
        if not title:
            continue
        # Trecho contínuo que cobre metade do título ou mais; uma palavra só conta se for o título inteiro.
        if (
            contains_token_sequence(title, words)
            and 2 * len(words) >= len(title)
            and (len(words) >= 2 or len(words) == len(title))
        ):
            return True
        # Linha única com quase as mesmas palavras do título, em outra ordem ou com uma a mais.
        shared = len(answer_words & set(title))
        if single_line and shared >= 0.8 * len(answer_words) and shared >= 0.8 * len(set(title)):
            return True
    return False
