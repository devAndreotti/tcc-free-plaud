from escolio.notes.schemas import Note


def _extraction_sections(note: Note) -> list[str]:
    """Seções '## Decisões' e '## Ações'; vazio quando não há extração."""
    extraction = note.extraction
    if extraction.is_empty():
        return []
    decisions = [f'- {item.text}' for item in extraction.decisions] or ['Nenhuma decisão identificada.']
    actions = [f'- {item.label()}' for item in extraction.action_items] or ['Nenhuma ação identificada.']
    return ['', '## Decisões', *decisions, '', '## Ações', *actions]


def render_note_markdown(note: Note) -> str:
    """Serializa a nota em Markdown com frontmatter simples."""
    topics = note.topics or []
    tasks = note.tasks or []
    tags = note.tags or []
    lines = [
        '---',
        f'note_id: {note.note_id}',
        f'note_version: {note.note_version}',
        f'source_type: {note.source_type}',
        f'source_path: {note.source_path}',
        f'source_name: {note.source_name}',
        f'title: {note.title}',
        f'content_hash: {note.content_hash}',
        f'provider: {note.provider}',
        f'model: {note.model}',
        'topics:',
        *[f'  - {item}' for item in topics],
        'tasks:',
        *[f'  - {item}' for item in tasks],
        'tags:',
        *[f'  - {item}' for item in tags],
        '---',
        '',
        f'# {note.title}',
        '',
        '## Summary',
        note.summary or 'Sem resumo inicial.',
        '',
        '## Normalized Text',
        note.normalized_text or 'Sem conteúdo normalizado.',
        '',
        '## Raw Text',
        note.raw_text or 'Sem conteúdo bruto.',
        '',
        *_extraction_sections(note),
    ]
    return '\n'.join(lines).strip() + '\n'
