import json
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path

from escolio.notes.schemas import Note


@dataclass(slots=True)
class SavedNoteArtifact:
    note_path: Path
    meta_path: Path


def _build_manifest(note: Note) -> dict[str, object]:
    return {
        'note_id': note.note_id,
        'note_version': note.note_version,
        'source_path': str(note.source_path),
        'source_type': note.source_type,
        'source_name': note.source_name,
        'content_hash': note.content_hash,
        'structured_hash': sha256(note.structured_markdown.encode('utf-8')).hexdigest(),
        'created_at': note.created_at.isoformat(),
    }


def save_note_locally(note: Note, notes_dir: Path) -> SavedNoteArtifact:
    """Persiste a nota estruturada e um manifesto mínimo no diretório local."""
    notes_dir.mkdir(parents=True, exist_ok=True)
    note_path = notes_dir / f'{note.note_id}.md'
    meta_path = notes_dir / f'{note.note_id}.meta.json'
    note_path.write_text(note.structured_markdown, encoding='utf-8')
    meta_path.write_text(
        json.dumps(_build_manifest(note), ensure_ascii=False, indent=2) + '\n',
        encoding='utf-8',
    )
    return SavedNoteArtifact(note_path=note_path, meta_path=meta_path)
