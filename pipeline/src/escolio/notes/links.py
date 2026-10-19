"""Ligações [[...]] entre notas do vault (wikilinks do Obsidian), resolvidas para note_id.

Lê o Markdown original (raw_text) e liga cada nota às notas que ela cita. Só o grafo usa essas
arestas: nada é gravado no banco.
"""

import re
import sqlite3
from pathlib import PurePosixPath

# [[Alvo]], [[Alvo|apelido]], [[Alvo#Seção]], [[Alvo#^bloco]] e [[Alvo^bloco]]: o alvo é o grupo 1.
# O ! do embed fica fora do padrão, então ![[Nota]] casa como um link comum.
_WIKILINK = re.compile(r'\[\[([^\[\]\n|#^]+)(?:[|#^][^\[\]\n]*)?\]\]')
# Bloco cercado por ``` ou ~~~; sem fecho, vai até o fim do texto (como no CommonMark).
_FENCED_CODE = re.compile(r'^ {0,3}(`{3,}|~{3,})[^\n]*\n.*?(?:^ {0,3}\1[`~]*[ \t]*$|\Z)', re.MULTILINE | re.DOTALL)
_INLINE_CODE = re.compile(r'(`+)[^\n]*?\1')
# Anexos que nunca são nota: ![[foto.png]] não vira aresta
_ATTACHMENT_EXTENSIONS = frozenset({
    '.png', '.jpg', '.jpeg', '.gif', '.webp', '.svg', '.bmp',
    '.pdf', '.mp3', '.wav', '.ogg', '.m4a', '.mp4', '.mov', '.webm',
    '.canvas', '.base',
})


def extract_wikilinks(markdown: str) -> list[str]:
    """Alvos dos [[links]] do Markdown, na ordem em que aparecem (sem deduplicar).

    Ignora código cercado, código inline e embeds de anexos.
    """
    text = _INLINE_CODE.sub(' ', _FENCED_CODE.sub(' ', markdown))
    targets: list[str] = []
    for match in _WIKILINK.finditer(text):
        # \| dentro de tabela deixa a barra colada no alvo: [[Nota\|apelido]]
        target = match.group(1).rstrip('\\').strip()
        if target and PurePosixPath(target).suffix.lower() not in _ATTACHMENT_EXTENSIONS:
            targets.append(target)
    return targets


def _path_parts(source_path: str) -> list[str]:
    """Trechos do caminho sem extensão, em minúsculas; o último é o nome do arquivo."""
    stem = PurePosixPath(source_path.replace('\\', '/')).with_suffix('')
    return [part.lower() for part in stem.parts if part != '/']


def note_link_edges(connection: sqlite3.Connection) -> list[dict[str, str]]:
    """Arestas {'source': note_id, 'target': note_id} de cada link que cai em outra nota do banco.

    Resolve sem diferenciar maiúsculas, nesta ordem: caminho relativo sem extensão (o alvo casa o
    fim do source_path, e o último trecho cobre o nome do arquivo) e depois o título da nota.
    Não resolvidos, autolinks e arestas repetidas são descartados.
    """
    rows = connection.execute(
        'SELECT note_id, title, source_path, raw_text FROM notes ORDER BY source_path, note_id'
    ).fetchall()

    # ponytail: nome repetido em pastas diferentes fica com a 1ª nota em ordem de caminho; upgrade: escolher pelo caminho mais curto
    by_path: dict[str, str] = {}  # 'pasta/alvo' e 'alvo' para cada nota; a primeira vence
    by_title: dict[str, str] = {}
    for note_id, title, source_path, _raw in rows:
        parts = _path_parts(source_path)
        for start in range(len(parts)):
            by_path.setdefault('/'.join(parts[start:]), note_id)
        by_title.setdefault(title.strip().lower(), note_id)

    edges: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for note_id, _title, _source_path, raw_text in rows:
        for target in extract_wikilinks(raw_text):
            key = target.lower().removesuffix('.md')  # [[Nota.md]] é o mesmo link de [[Nota]]
            dest = by_path.get(key) or by_title.get(key)
            if dest is None or dest == note_id or (note_id, dest) in seen:
                continue
            seen.add((note_id, dest))
            edges.append({'source': note_id, 'target': dest})
    return edges
