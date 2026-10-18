from __future__ import annotations

import ast
import html
import re
from html.parser import HTMLParser
from pathlib import Path

import typer

OBSIDIAN_VAULT_ROOT = Path(r'C:\Users\ricar\OneDrive\Documentos\Obsidian Vault\Obsidian-Core')
SEMANTIC_FRONTMATTER_KEYS = {
    'type',
    'area',
    'topic',
    'status',
    'created',
    'updated',
    'tags',
}
NOISE_FRONTMATTER_KEYS = {
    'banner',
    'icon',
    'banner-display',
    'cssclass',
}
OBSIDIAN_SIGNAL_PATTERNS = (
    '```dataviewjs',
    '[[',
    'dv.container',
    'createEl(',
    '.style.cssText',
    '=date(now)',
    'banner-display:',
)
OBJECT_CONTENT_KEYS = {
    'title',
    'name',
    'desc',
    'description',
    'full',
    'fullname',
    'items',
    'skills',
    'examples',
    'nota',
    'note',
    'motivacao',
    'nivel',
    'value',
    'alert',
}
OBJECT_SKIP_KEYS = {
    'icon',
    'color',
    'target',
    'page',
    'gradient',
    'shadow',
    'free',
}
TEXT_ASSIGNMENT_RE = re.compile(
    r'(?:textContent|innerText)\s*=\s*(?P<quote>[\'"`])(?P<value>.*?)(?P=quote)\s*;',
    re.DOTALL,
)
HTML_ASSIGNMENT_RE = re.compile(
    r'innerHTML\s*=\s*(?P<quote>[\'"`])(?P<value>.*?)(?P=quote)\s*;',
    re.DOTALL,
)
DATAVIEW_BLOCK_RE = re.compile(r'```dataviewjs\s*\n(?P<body>.*?)```', re.DOTALL | re.IGNORECASE)
WIKILINK_RE = re.compile(r'\[\[[^\]]+\]\]')

app = typer.Typer(help='Limpa notas Obsidian para ingestao local-first.', no_args_is_help=True)


class _HTMLToMarkdown(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self.list_level = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {'p', 'div'}:
            self.parts.append('\n\n')
        elif tag in {'br'}:
            self.parts.append('\n')
        elif tag in {'h1', 'h2', 'h3', 'h4', 'h5', 'h6'}:
            level = int(tag[1])
            self.parts.append(f"\n\n{'#' * min(level, 6)} ")
        elif tag in {'ul', 'ol'}:
            self.list_level += 1
            self.parts.append('\n')
        elif tag == 'li':
            indent = '  ' * max(self.list_level - 1, 0)
            self.parts.append(f'\n{indent}- ')
        elif tag == 'code':
            self.parts.append('`')

    def handle_endtag(self, tag: str) -> None:
        if tag == 'code':
            self.parts.append('`')
        elif tag in {'ul', 'ol'}:
            self.list_level = max(0, self.list_level - 1)

    def handle_data(self, data: str) -> None:
        if data:
            self.parts.append(html.unescape(data))

    def to_markdown(self) -> str:
        text = ''.join(self.parts)
        text = re.sub(r'[ \t]+\n', '\n', text)
        text = re.sub(r'\n{3,}', '\n\n', text)
        return text.strip()


def has_obsidian_signals(text: str) -> bool:
    return any(signal in text for signal in OBSIDIAN_SIGNAL_PATTERNS)


def extract_frontmatter(text: str) -> tuple[dict[str, object], str]:
    if not text.startswith('---\n'):
        return {}, text

    lines = text.splitlines()
    try:
        end_index = lines[1:].index('---') + 1
    except ValueError:
        return {}, text

    frontmatter_lines = lines[1:end_index]
    body = '\n'.join(lines[end_index + 1 :]).lstrip('\n')
    parsed: dict[str, object] = {}
    current_list_key: str | None = None

    for raw_line in frontmatter_lines:
        line = raw_line.rstrip()
        if not line.strip():
            continue
        if current_list_key and line.lstrip().startswith('- '):
            value = line.split('- ', 1)[1].strip()
            parsed.setdefault(current_list_key, [])
            assert isinstance(parsed[current_list_key], list)
            parsed[current_list_key].append(value)
            continue
        current_list_key = None
        if ':' not in line:
            continue
        key, value = line.split(':', 1)
        key = key.strip()
        value = value.strip()
        if not value:
            if key == 'tags':
                parsed[key] = []
                current_list_key = key
            continue
        parsed[key] = value

    return parsed, body


def _render_frontmatter(frontmatter: dict[str, object]) -> str:
    filtered: dict[str, object] = {}
    for key, value in frontmatter.items():
        if key in NOISE_FRONTMATTER_KEYS:
            continue
        if key not in SEMANTIC_FRONTMATTER_KEYS:
            continue
        filtered[key] = value

    if not filtered:
        return ''

    lines = ['---']
    for key, value in filtered.items():
        if isinstance(value, list):
            lines.append(f'{key}:')
            for item in value:
                lines.append(f'  - {item}')
            continue
        lines.append(f'{key}: {value}')
    lines.append('---')
    return '\n'.join(lines)


def _normalize_whitespace(text: str) -> str:
    text = text.replace('\r\n', '\n').replace('\r', '\n')
    text = re.sub(r'[ \t]+\n', '\n', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def _strip_js_wrappers(text: str) -> str:
    text = re.sub(r'^[=:+\-\s\'"`]+', '', text.strip())
    text = re.sub(r'[\'"`;]+$', '', text)
    return text.strip()


def _convert_html_to_markdown(raw_html: str) -> str:
    raw_html = _replace_template_expressions(raw_html)
    parser = _HTMLToMarkdown()
    parser.feed(raw_html)
    return _normalize_whitespace(parser.to_markdown())


def _find_matching_bracket(text: str, start_index: int, open_char: str, close_char: str) -> int:
    depth = 0
    quote: str | None = None
    escape = False
    for index in range(start_index, len(text)):
        char = text[index]
        if quote:
            if escape:
                escape = False
            elif char == '\\':
                escape = True
            elif char == quote:
                quote = None
            continue
        if char in {'"', "'", '`'}:
            quote = char
            continue
        if char == open_char:
            depth += 1
        elif char == close_char:
            depth -= 1
            if depth == 0:
                return index
    return -1


def _extract_array_blocks(js_code: str) -> list[str]:
    blocks: list[str] = []
    for match in re.finditer(r'(?:const|let|var)\s+\w+\s*=\s*\[', js_code):
        start = match.end() - 1
        end = _find_matching_bracket(js_code, start, '[', ']')
        if end == -1:
            continue
        blocks.append(js_code[start : end + 1])
    return blocks


def _replace_template_expressions(text: str) -> str:
    result: list[str] = []
    index = 0
    while index < len(text):
        if text.startswith('${', index):
            end = _find_matching_bracket(text, index + 1, '{', '}')
            if end == -1:
                result.append(text[index:])
                break
            expression = text[index + 2 : end]
            string_literals = [
                match
                for match in re.findall(r'["\']([^"\']+)["\']', expression)
                if match.strip()
            ]
            if string_literals:
                replacement = ''.join(f'<li>{html.escape(item)}</li>' for item in string_literals)
                result.append(replacement)
            index = end + 1
            continue
        result.append(text[index])
        index += 1
    return ''.join(result)


def _js_array_to_python_literal(js_array: str) -> str:
    converted = re.sub(r'([,{]\s*)([A-Za-z_][A-Za-z0-9_]*)\s*:', r'\1"\2":', js_array)
    converted = re.sub(r',(\s*[}\]])', r'\1', converted)
    converted = converted.replace('true', 'True').replace('false', 'False').replace('null', 'None')
    return converted


def _render_object_entry(entry: dict[str, object]) -> str:
    if not any(key in entry for key in OBJECT_CONTENT_KEYS):
        return ''
    title = str(entry.get('title') or entry.get('name') or '').strip()
    scalar_lines: list[str] = []
    list_lines: list[str] = []
    paragraphs: list[str] = []

    for key, value in entry.items():
        if key in OBJECT_SKIP_KEYS:
            continue
        if value == '' or value is None:
            continue
        if key in {'title', 'name'}:
            continue
        if isinstance(value, list):
            for item in value:
                list_lines.append(f'- {item}')
            continue
        text = str(value).strip()
        if key in {'desc', 'description', 'nota', 'note', 'full', 'fullname'}:
            paragraphs.append(text)
            continue
        label = {
            'nivel': 'Nível',
            'motivacao': 'Motivação',
            'value': 'Valor',
            'alert': 'Alert',
        }.get(key, key.replace('_', ' ').capitalize())
        scalar_lines.append(f'- {label}: {text}')

    if not title and not scalar_lines and not list_lines and not paragraphs:
        return ''

    parts: list[str] = []
    if title:
        parts.append(f'## {title}')
    parts.extend(scalar_lines)
    parts.extend(paragraphs)
    parts.extend(list_lines)
    return _normalize_whitespace('\n'.join(parts))


def _extract_arrays_as_markdown(js_code: str) -> list[str]:
    rendered: list[str] = []
    for array_block in _extract_array_blocks(js_code):
        try:
            data = ast.literal_eval(_js_array_to_python_literal(array_block))
        except (ValueError, SyntaxError):
            continue
        if not isinstance(data, list):
            continue
        for item in data:
            if not isinstance(item, dict):
                continue
            block = _render_object_entry(item)
            if block:
                rendered.append(block)
    return rendered


def _looks_like_heading(text: str) -> bool:
    stripped = _strip_js_wrappers(text)
    words = stripped.split()
    return 1 <= len(words) <= 10 and not any(mark in stripped for mark in '.!?')


def _extract_dataview_block(js_code: str) -> str:
    pieces: list[str] = []

    for match in TEXT_ASSIGNMENT_RE.finditer(js_code):
        value = _strip_js_wrappers(match.group('value'))
        if not value:
            continue
        pieces.append(f'## {value}' if _looks_like_heading(value) else value)

    for match in HTML_ASSIGNMENT_RE.finditer(js_code):
        rendered = _convert_html_to_markdown(match.group('value'))
        if rendered:
            pieces.append(rendered)

    pieces.extend(_extract_arrays_as_markdown(js_code))

    deduped: list[str] = []
    seen: set[str] = set()
    for piece in pieces:
        normalized = re.sub(r'\s+', ' ', piece).strip().lower()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        deduped.append(piece.strip())

    return _normalize_whitespace('\n\n'.join(deduped))


def _clean_markdown_segment(text: str) -> str:
    cleaned_lines: list[str] = []
    for raw_line in text.splitlines():
        line = raw_line
        if '${' in line:
            continue
        if '=date(now)' in line:
            continue
        if WIKILINK_RE.search(line):
            line = WIKILINK_RE.sub('', line)
            if re.sub(r'[←→|📊🦠🏢🪟🌐🔐📜🎯\s\-–—_]+', '', line) == '':
                continue
        if '<' in line and '>' in line:
            line = re.sub(r'<[^>]+>', '', line)
        if re.sub(r'[\s⚠️💡📷🔗🛡️🏢🎯🪟📊🦠🌐🔐📜🔧🔥💻]+', '', line) == '':
            continue
        if line.strip() in {'---', '***', '___'}:
            cleaned_lines.append('---')
            continue
        cleaned_lines.append(line.rstrip())
    return _normalize_whitespace('\n'.join(cleaned_lines))


def clean_obsidian_text(raw_text: str) -> str:
    frontmatter, body = extract_frontmatter(raw_text)
    rendered_frontmatter = _render_frontmatter(frontmatter)

    pieces: list[str] = []
    last_end = 0
    for match in DATAVIEW_BLOCK_RE.finditer(body):
        plain = _clean_markdown_segment(body[last_end : match.start()])
        if plain:
            pieces.append(plain)
        extracted = _extract_dataview_block(match.group('body'))
        if extracted:
            pieces.append(extracted)
        last_end = match.end()

    tail = _clean_markdown_segment(body[last_end:])
    if tail:
        pieces.append(tail)

    body_text = _normalize_whitespace('\n\n'.join(piece for piece in pieces if piece))
    if rendered_frontmatter and body_text:
        return f'{rendered_frontmatter}\n\n{body_text}\n'
    if rendered_frontmatter:
        return f'{rendered_frontmatter}\n'
    return f'{body_text}\n' if body_text else ''


def _ensure_safe_destination(source: Path, dest: Path) -> None:
    source_resolved = source.resolve()
    dest_resolved = dest.resolve(strict=False)
    vault_root = OBSIDIAN_VAULT_ROOT.resolve(strict=False)

    if source_resolved == dest_resolved:
        raise ValueError('Destino nao pode ser o mesmo arquivo de origem.')
    if vault_root == dest_resolved or vault_root in dest_resolved.parents:
        raise ValueError('Destino dentro do vault nao e permitido.')


def clean_obsidian_md(source: Path, dest: Path) -> None:
    _ensure_safe_destination(source, dest)
    raw_text = source.read_text(encoding='utf-8')
    cleaned = clean_obsidian_text(raw_text)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(cleaned, encoding='utf-8')


def clean_obsidian_path(source: Path, dest: Path) -> list[Path]:
    source = source.expanduser()
    dest = dest.expanduser()
    if source.is_file():
        clean_obsidian_md(source, dest)
        return [dest]

    if not source.exists() or not source.is_dir():
        raise FileNotFoundError(f'Origem nao encontrada: {source}')

    written: list[Path] = []
    for file_path in sorted(source.rglob('*.md')):
        relative = file_path.relative_to(source)
        target = dest / relative
        clean_obsidian_md(file_path, target)
        written.append(target)
    return written


@app.command('clean')
def clean_command(source: str = typer.Argument(...), dest: str = typer.Argument(...)) -> None:
    written = clean_obsidian_path(Path(source), Path(dest))
    typer.echo(f'files_cleaned: {len(written)}')
    for path in written:
        typer.echo(str(path))


if __name__ == '__main__':
    app()
