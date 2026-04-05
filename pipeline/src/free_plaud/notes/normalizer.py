import re


def normalize_text(raw_text: str) -> str:
    """Normaliza texto de forma determinística sem reescrever o conteúdo."""
    normalized = raw_text.replace('\r\n', '\n').replace('\r', '\n')
    normalized = '\n'.join(line.rstrip() for line in normalized.split('\n'))
    normalized = re.sub(r'\n{3,}', '\n\n', normalized)
    return normalized.strip()
