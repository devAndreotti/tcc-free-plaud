from free_plaud.notes.schemas import Note
from free_plaud.retrieval.chunking import chunk_text
from free_plaud.retrieval.models import Chunk


def index_note(note: Note, chunk_size: int = 800, overlap: int = 120) -> list[Chunk]:
    """Produz chunks indexáveis a partir da nota estruturada."""
    return chunk_text(
        note.note_id,
        note.note_version,
        note.normalized_text,
        chunk_size=chunk_size,
        overlap=overlap,
        normalized_text_sha256=note.content_hash,
    )
