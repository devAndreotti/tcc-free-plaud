from free_plaud.notes.schemas import Note
from free_plaud.providers.embed import Embedder
from free_plaud.retrieval.chunking import chunk_text
from free_plaud.retrieval.models import Chunk
from free_plaud.storage.vector import LocalVectorStore


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
