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
    return len(left) <= 3


def _repair_fragmented_ocr_line(line: str) -> str:
    tokens = line.split()
    word_tokens = [token for token in tokens if _is_word_fragment(token)]
    suspicious_pairs = [
        (left, right)
        for left, right in itertools.pairwise(tokens)
        if _should_merge_tokens(left, right)
    ]
    strong_pairs = [
        (left, right)
        for left, right in suspicious_pairs
        if left.isupper() and right.isupper() or len(left) <= 3 or len(right) <= 3
    ]
    uppercase_ratio = (
        sum(1 for token in word_tokens if token.isupper()) / len(word_tokens)
        if word_tokens
        else 0.0
    )
    if not (
        (len(suspicious_pairs) >= 1 and uppercase_ratio >= 0.7)
        or (len(suspicious_pairs) >= 3 and len(strong_pairs) >= 1)
    ):
        return line

    repaired: list[str] = []
    index = 0
    while index < len(tokens):
        current = tokens[index]
        if index + 1 < len(tokens) and _should_merge_tokens(current, tokens[index + 1]):
            current += tokens[index + 1]
            index += 1
        repaired.append(current)
        index += 1

    merged_line = ' '.join(repaired)
    merged_line = re.sub(r'\s+([,.;:!?/])', r'\1', merged_line)
    merged_line = re.sub(r'(\d)\s+\.\s+(\d)', r'\1.\2', merged_line)
    return merged_line


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
    """Normaliza texto de forma determinística sem reescrever o conteúdo."""
    normalized = raw_text.replace('\r\n', '\n').replace('\r', '\n')
    lines = [line.rstrip() for line in normalized.split('\n')]

    cleaned_lines: list[str] = []
    previous_nonempty = ''
    for line in lines:
        if _is_visual_noise_line(line):
            continue
        repaired_line = _repair_fragmented_ocr_line(line)
        if repaired_line.strip() and repaired_line.strip() == previous_nonempty:
            continue
        cleaned_lines.append(repaired_line)
        if repaired_line.strip():
            previous_nonempty = repaired_line.strip()

    normalized = '\n'.join(cleaned_lines)
    normalized = re.sub(r'\n{3,}', '\n\n', normalized)
    normalized = re.sub(r'(\d)\s+\.\s+(\d)', r'\1.\2', normalized)
    normalized = re.sub(r'\s+([,.;:!?/])', r'\1', normalized)
    return normalized.strip()
