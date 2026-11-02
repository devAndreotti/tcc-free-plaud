import itertools
import re

CONNECTOR_WORDS = {
    'a',
    'as',
    'o',
    'os',
    'e',
    'de',
    'da',
    'das',
    'do',
    'dos',
    'em',
    'na',
    'nas',
    'no',
    'nos',
    'para',
    'por',
    'com',
    'sem',
    'ou',
    'que',
    'um',
    'uma',
    'uns',
    'umas',
    'ao',
    'aos',
    'se',
    'eh',
    'é',
}


# Numeral romano em CAIXA ALTA (ANEXO II) não é pedaço de palavra.
_ROMAN_NUMERAL = re.compile(r'[IVXLCDM]+')
# Versão: 2 .1 / 14 /fev / Data : 14
_OCR_SPACING = re.compile(r'\d[ \t]+[.,/]\d|\d[ \t]+/\w|\w[ \t]+:[ \t]+\d')
# ponytail: heurística sem dicionário; ainda junta nomes longos (SQL SERVER) em documento já marcado como OCR,
# e texto misto de OCR ("relat ório") fica como veio. Trocar por dicionário se aparecer OCR de verdade no corpus.
MIN_MERGED_LENGTH = 8
MIN_FRAGMENTED_LINES = 3


def _is_visual_noise_line(line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return False
    if re.fullmatch(r'[\u2500-\u257f\s]+', stripped):
        return True
    normalized = stripped.lower()
    if ('pag.' in normalized or 'pág.' in normalized) and '|' in stripped:
        return True
    tokens = stripped.split()
    if len(tokens) < 8:
        return False
    one_char_tokens = [
        token for token in tokens if re.fullmatch(r'[A-Za-zÀ-ÿ]', token) is not None
    ]
    return len(one_char_tokens) / len(tokens) >= 0.6


def _is_word_fragment(token: str) -> bool:
    return re.fullmatch(r'[A-Za-zÀ-ÿ]+', token) is not None


def _should_merge_tokens(left: str, right: str) -> bool:
    """Pedaços de uma palavra em CAIXA ALTA: RELA TÓRIO, OBJ ETIVO.

    Só em maiúsculas: sem dicionário, em texto misto não dá para separar "relat ório" de "The user" ou "Não há".
    """
    if not (_is_word_fragment(left) and _is_word_fragment(right)):
        return False
    if left.lower() in CONNECTOR_WORDS or right.lower() in CONNECTOR_WORDS:
        return False
    if not (left.isupper() and right.isupper()):
        return False
    # ANEXO II, II GUERRA: numeral romano é palavra inteira.
    if _ROMAN_NUMERAL.fullmatch(left) or _ROMAN_NUMERAL.fullmatch(right):
        return False
    # O mínimo deixa siglas de fora: API REST, TCP IP.
    return len(left) <= 5 and len(right) <= 12 and len(left) + len(right) >= MIN_MERGED_LENGTH


def _has_fragmented_words(line: str) -> bool:
    tokens = line.split()
    words = [token for token in tokens if _is_word_fragment(token)]
    if not words or sum(1 for word in words if word.isupper()) / len(words) < 0.7:
        return False
    return any(_should_merge_tokens(left, right) for left, right in itertools.pairwise(tokens))


def looks_like_fragmented_ocr(text: str) -> bool:
    """Documento com palavras partidas em várias linhas e o espaço típico de OCR no meio de número ou antes de ":".

    Caixa alta sozinha não basta: licença e SQL em maiúsculas têm o mesmo jeito ("NOT CREATE", "ON UPDATE").
    """
    if _OCR_SPACING.search(text) is None:
        return False
    fragmented = sum(1 for line in text.splitlines() if _has_fragmented_words(line))
    return fragmented >= MIN_FRAGMENTED_LINES


def _repair_fragmented_ocr_line(line: str) -> str:
    if not _has_fragmented_words(line):
        return line

    tokens = line.split()
    repaired: list[str] = []
    index = 0
    while index < len(tokens):
        current = tokens[index]
        if index + 1 < len(tokens) and _should_merge_tokens(current, tokens[index + 1]):
            current += tokens[index + 1]
            index += 1
        repaired.append(current)
        index += 1

    return ' '.join(repaired)


def _should_merge_summary_tokens(left: str, right: str) -> bool:
    if not (_is_word_fragment(left) and _is_word_fragment(right)):
        return False
    if left.lower() in CONNECTOR_WORDS or right.lower() in CONNECTOR_WORDS:
        return False
    if left.istitle() and right.islower() and len(left) >= 4 and len(right) >= 4:
        return False
    if left.istitle() and right.istitle():
        return False
    if left.islower() and right.istitle():
        return False
    if left.isupper() and right.isupper() and len(left) <= 5 and len(right) <= 12:
        return True
    if len(left) <= 3 or len(right) <= 3:
        return True
    return bool(len(left) <= 5 and len(right) <= 5)


def repair_ocr_summary_text(text: str) -> str:
    """Aplica um reparo mais agressivo apenas quando o resumo parece OCR fragmentado."""
    tokens = text.split()
    suspicious_pairs = [
        (left, right)
        for left, right in itertools.pairwise(tokens)
        if _should_merge_summary_tokens(left, right)
    ]
    if len(suspicious_pairs) < 4:
        return text

    repaired: list[str] = []
    index = 0
    while index < len(tokens):
        current = tokens[index]
        if index + 1 < len(tokens) and _should_merge_summary_tokens(current, tokens[index + 1]):
            current += tokens[index + 1]
            index += 1
        repaired.append(current)
        index += 1

    merged_text = ' '.join(repaired)
    merged_text = re.sub(r'\s+([,.;:!?/])', r'\1', merged_text)
    merged_text = re.sub(r'(\d)\s+\.\s+(\d)', r'\1.\2', merged_text)
    return merged_text


def normalize_text(raw_text: str) -> str:
    """Normaliza texto de forma determinística sem reescrever o conteúdo.

    Juntar palavras e tirar espaço antes de pontuação só vale em documento com OCR fragmentado:
    em nota comum isso cola palavras ("Nãohá") e estraga código e " / ".
    """
    normalized = raw_text.replace('\r\n', '\n').replace('\r', '\n')
    lines = [line.rstrip() for line in normalized.split('\n')]
    is_ocr = looks_like_fragmented_ocr('\n'.join(lines))

    cleaned_lines: list[str] = []
    previous_nonempty = ''
    for line in lines:
        if _is_visual_noise_line(line):
            continue
        repaired_line = _repair_fragmented_ocr_line(line) if is_ocr else line
        if repaired_line.strip() and repaired_line.strip() == previous_nonempty:
            continue
        cleaned_lines.append(repaired_line)
        if repaired_line.strip():
            previous_nonempty = repaired_line.strip()

    normalized = '\n'.join(cleaned_lines)
    normalized = re.sub(r'\n{3,}', '\n\n', normalized)
    if is_ocr:
        normalized = re.sub(r'(\d)[ \t]+\.[ \t]+(\d)', r'\1.\2', normalized)
        normalized = re.sub(r'[ \t]+([,.;:!?/])', r'\1', normalized)
    return normalized.strip()
