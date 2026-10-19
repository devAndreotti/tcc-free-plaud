"""Texto legível de notas Obsidian: sem frontmatter, marcadores de callout, colchetes de wikilink e blocos Dataview.

Serve para título, snippet da citação, claims e contexto da IA. O texto indexado (chunks, FTS, embeddings) não muda.
"""

import re

# Linha que o YAML do frontmatter aceita: chave: valor, item de lista, comentário, continuação indentada ou em branco.
_YAML_KEY = r'["\']?\w[\w.\-/]*["\']?'
_YAML_LINE = (
    r'(?:[ \t]*\r?\n'
    rf'|[ \t]*{_YAML_KEY}[ \t]*:(?:[ \t][^\r\n]*)?\r?\n'
    r'|[ \t]*-(?:[ \t][^\r\n]*)?\r?\n'
    r'|[ \t]*#[^\r\n]*\r?\n'
    r'|[ \t]+\S[^\r\n]*\r?\n)'
)

# Frontmatter completo, com "---" de abertura. Só vale se todas as linhas forem YAML: "---" de régua depois de prosa não conta.
# ponytail: trecho que começa no meio de um frontmatter maior que o chunk (raro, >680 caracteres) mantém o fim do YAML;
# tirar "linhas que parecem YAML até um ---" apagaria listas e "Status: ..." reais antes de uma régua.
FRONTMATTER_PATTERN = re.compile(rf'\A\s*---[ \t]*\r?\n(?:{_YAML_LINE})*?---[ \t]*(?:\r?\n|\Z)')
# Bloco ```dataviewjs inteiro; se o trecho cortou no meio, vai até o fim.
DATAVIEW_BLOCK_PATTERN = re.compile(r'```[ \t]*dataview(?:js)?\b.*?(?:```|\Z)', re.DOTALL | re.IGNORECASE)
BLOCKQUOTE_MARKER_PATTERN = re.compile(r'^[ \t]*(?:>[ \t]?)+', re.MULTILINE)
CALLOUT_MARKER_PATTERN = re.compile(r'^[ \t]*\[![^\]\r\n]+\][+-]?[ \t]*', re.MULTILINE)
# [[Alvo]], [[Alvo#Seção]], [[Alvo|apelido]] e o embed ![[...]].
WIKILINK_PATTERN = re.compile(r'!?\[\[([^\[\]|#\r\n]*)(?:#([^\[\]|\r\n]*))?(?:\|([^\[\]\r\n]*))?\]\]')


def _wikilink_label(match: re.Match[str]) -> str:
    # Embed ![[...]] some do texto; senão apelido, alvo ou seção: [[Alvo|apelido]] -> apelido, [[Alvo#Seção]] -> Alvo.
    if match.group(0).startswith('!'):
        return ''
    for group in (match.group(3), match.group(1), match.group(2)):
        if group and group.strip():
            return group.strip()
    return ''


def strip_frontmatter(text: str) -> tuple[str, bool]:
    """Tira o frontmatter YAML do início da nota; devolve o corpo e se o frontmatter existia."""
    match = FRONTMATTER_PATTERN.match(text)
    if match is None:
        return text, False
    return text[match.end() :], True


def readable_chunk_text(text: str) -> str:
    """Versão legível de um trecho: remove frontmatter, Dataview e marcadores; o resto do texto fica como está."""
    cleaned = FRONTMATTER_PATTERN.sub('', text, count=1)
    cleaned = DATAVIEW_BLOCK_PATTERN.sub('', cleaned)
    cleaned = BLOCKQUOTE_MARKER_PATTERN.sub('', cleaned)
    cleaned = CALLOUT_MARKER_PATTERN.sub('', cleaned)
    cleaned = WIKILINK_PATTERN.sub(_wikilink_label, cleaned)
    return re.sub(r'\n{3,}', '\n\n', cleaned).strip()
