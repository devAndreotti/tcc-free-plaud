from pathlib import Path

import chromadb
from chromadb.api.models.Collection import Collection

from free_plaud.retrieval.models import Chunk, SearchHit


def _distance_to_score(distance: float) -> float:
    return 1.0 / (1.0 + max(distance, 0.0))


def _chunk_from_record(chunk_id: str, document: str, metadata: dict[str, object]) -> Chunk:
    return Chunk(
        chunk_id=chunk_id,
        note_id=str(metadata['note_id']),
        note_version=int(metadata['note_version']),
        chunk_index=int(metadata['chunk_index']),
        char_start=int(metadata['char_start']),
        char_end=int(metadata['char_end']),
        chunk_size=int(metadata['chunk_size']),
        overlap=int(metadata['overlap']),
        chunk_text=document,
        token_count=int(metadata['token_count']),
        strategy=str(metadata['strategy']),
        normalized_text_sha256=str(metadata['normalized_text_sha256']),
        text_sha256=str(metadata['text_sha256']),
        pipeline_version=str(metadata['pipeline_version']),
    )


class LocalVectorStore:
    """Persistência vetorial local usando ChromaDB."""

    def __init__(self, base_dir: Path, *, collection_name: str = 'free_plaud_chunks') -> None:
        self.base_dir = base_dir
        self.collection_name = collection_name
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self._client = chromadb.PersistentClient(path=str(self.base_dir))

    def _collection(self) -> Collection:
        return self._client.get_or_create_collection(
            name=self.collection_name,
            metadata={'hnsw:space': 'cosine'},
        )

    def healthcheck(self) -> bool:
        return self.base_dir.exists()

    def count(self) -> int:
        return self._collection().count()

    def reset(self) -> None:
        try:
            self._client.delete_collection(self.collection_name)
        except Exception:
            pass

    def upsert_chunks(self, chunks: list[Chunk], embeddings: list[list[float]], *, embedding_model: str) -> None:
        if len(chunks) != len(embeddings):
            raise ValueError('A quantidade de embeddings precisa bater com a quantidade de chunks.')
        if not chunks:
            return

        metadatas = [
            {
                'note_id': chunk.note_id,
                'note_version': chunk.note_version,
                'chunk_index': chunk.chunk_index,
                'char_start': chunk.char_start,
                'char_end': chunk.char_end,
                'chunk_size': chunk.chunk_size,
                'overlap': chunk.overlap,
                'token_count': chunk.token_count,
                'strategy': chunk.strategy,
                'normalized_text_sha256': chunk.normalized_text_sha256,
                'text_sha256': chunk.text_sha256,
                'pipeline_version': chunk.pipeline_version,
                'embedding_model': embedding_model,
            }
            for chunk in chunks
        ]
        self._collection().upsert(
            ids=[chunk.chunk_id for chunk in chunks],
            documents=[chunk.chunk_text for chunk in chunks],
            embeddings=embeddings,
            metadatas=metadatas,
        )

    def query(self, query_embedding: list[float], *, top_k: int = 5, note_id: str | None = None) -> list[SearchHit]:
        if top_k <= 0 or self.count() == 0:
            return []

        result = self._collection().query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            where={'note_id': note_id} if note_id else None,
            include=['documents', 'metadatas', 'distances'],
        )

        ids = result.get('ids', [[]])[0]
        documents = result.get('documents', [[]])[0]
        metadatas = result.get('metadatas', [[]])[0]
        distances = result.get('distances', [[]])[0]

        hits: list[SearchHit] = []
        for chunk_id, document, metadata, distance in zip(ids, documents, metadatas, distances, strict=False):
            if metadata is None or document is None:
                continue
            hits.append(
                SearchHit(
                    chunk=_chunk_from_record(chunk_id, str(document), metadata),
                    score=_distance_to_score(float(distance)),
                    strategy='vector',
                    distance=float(distance),
                )
            )
        return hits
