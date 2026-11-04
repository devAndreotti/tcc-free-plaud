"""Visão de todas as vaults para o grafo: contagens, pastas de 1º nível e notas, sem abrir nem migrar nenhum banco."""

import sqlite3
from collections import Counter
from pathlib import Path, PurePosixPath

from escolio.app.config import Settings, base_settings, settings_for_vault
from escolio.app.vaults import load_registry

NOTE_LIMIT = 5000


def _posix(path: str) -> str:
    return path.replace('\\', '/').rstrip('/')


def _top_folder(source_path: str, roots: list[str]) -> str:
    """Pasta de 1º nível da nota dentro da raiz indexada; '' quando ela está na própria raiz."""
    path = _posix(source_path)
    for root in roots:
        if path.lower().startswith(root.lower() + '/'):
            parts = PurePosixPath(path[len(root) + 1:]).parts
            return parts[0] if len(parts) > 1 else ''
    return ''


def _read_vault(db_path: Path) -> dict:
    empty = {'note_count': 0, 'chunk_count': 0, 'folders': [], 'notes': []}
    if not db_path.exists():
        return empty
    try:
        connection = sqlite3.connect(f'file:{db_path.as_posix()}?mode=ro', uri=True)
    except sqlite3.Error:
        return empty
    try:
        rows = connection.execute('SELECT note_id, title, source_path FROM notes ORDER BY title').fetchall()
        chunks = int(connection.execute('SELECT COUNT(*) FROM chunks').fetchone()[0])
        try:
            roots = [_posix(str(row[0])) for row in connection.execute('SELECT root FROM corpus_roots')]
        except sqlite3.Error:  # banco de antes da tabela corpus_roots
            roots = []
    except sqlite3.Error:  # banco vazio ou corrompido: a vault aparece sem notas
        return empty
    finally:
        connection.close()
    roots.sort(key=len, reverse=True)
    notes = [
        {'id': note_id, 'title': title, 'folder': _top_folder(source_path, roots)}
        for note_id, title, source_path in rows
    ]
    folders = Counter(note['folder'] for note in notes)
    return {
        'note_count': len(notes),
        'chunk_count': chunks,
        'folders': [{'name': name, 'count': count} for name, count in folders.most_common()],
        'notes': notes[:NOTE_LIMIT],
    }


def vaults_overview(base: Settings | None = None) -> dict:
    """Vaults cadastradas com pastas e notas, lidas em modo somente leitura."""
    resolved = base or base_settings()
    registry = load_registry(resolved)
    vaults = []
    for vault in registry.vaults:
        data = _read_vault(settings_for_vault(vault, resolved).sqlite_path)
        vaults.append({'id': vault.id, 'name': vault.name, 'icon': vault.icon, 'color': vault.color, **data})
    return {'active': registry.active, 'vaults': vaults}
