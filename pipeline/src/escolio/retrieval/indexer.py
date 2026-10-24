from escolio.notes.schemas import Note
from escolio.providers.embed import Embedder
from escolio.retrieval.chunking import build_segment_text, chunk_segments, chunk_text
from escolio.retrieval.models import Chunk
from escolio.storage.vector import LocalVectorStore


def index_note(note: Note, chunk_size: int = 800, overlap: int = 120) -> list[Chunk]:
    """Produz chunks indexáveis a partir da nota estruturada.

    Nota com segmentos de fala (áudio) é fatiada por fala, com tempos; as demais seguem por janela de caracteres.
    """
    if note.segments:
        if build_segment_text(note.segments) != note.normalized_text:
            raise ValueError('Os segmentos da nota não batem com o normalized_text; reestruture a nota.')
        return chunk_segments(
            note.note_id,
            note.note_version,
            note.segments,
            normalized_text_sha256=note.content_hash,
            chunk_size=chunk_size,
            overlap=overlap,
        )
    return chunk_text(
        note.note_id,
        note.note_version,
        note.normalized_text,
        chunk_size=chunk_size,
        overlap=overlap,
        normalized_text_sha256=note.content_hash,
    )


def index_note_in_vector_store(
    note: Note,
    vector_store: LocalVectorStore,
    embedder: Embedder,
    *,
    chunk_size: int = 800,
    overlap: int = 120,
) -> list[Chunk]:
    """Gera chunks, produz embeddings e persiste o resultado no vector store local."""
    chunks = index_note(note, chunk_size=chunk_size, overlap=overlap)
    embeddings = embedder.embed([chunk.chunk_text for chunk in chunks])
    if len(embeddings) != len(chunks):
        raise ValueError('A quantidade de embeddings precisa bater com a quantidade de chunks.')
    vector_store.upsert_chunks(chunks, embeddings, embedding_model=embedder.model_name)
    return chunks
