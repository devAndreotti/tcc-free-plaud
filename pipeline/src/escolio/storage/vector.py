from pathlib import Path

import chromadb
from chromadb.api.models.Collection import Collection
from chromadb.config import Settings as ChromaSettings
from chromadb.errors import NotFoundError

from escolio.app.legacy import DEFAULT_CHROMA_COLLECTION, LEGACY_CHROMA_COLLECTION
from escolio.retrieval.models import Chunk, SearchHit


def _distance_to_score(distance: float) -> float:
    return 1.0 / (1.0 + max(distance, 0.0))


def _collection_names(client: chromadb.ClientAPI) -> set[str]:
    names: set[str] = set()
    for item in client.list_collections():
        names.add(item if isinstance(item, str) else item.name)
    return names


def _resolve_collection_name(client: chromadb.ClientAPI, requested: str) -> str:
    """Abre free_plaud_chunks quando o store antigo existe e o escolio_chunks ainda nao."""
    if requested != DEFAULT_CHROMA_COLLECTION:
        return requested
    names = _collection_names(client)
    if DEFAULT_CHROMA_COLLECTION not in names and LEGACY_CHROMA_COLLECTION in names:
        return LEGACY_CHROMA_COLLECTION
    return requested


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

    def __init__(self, base_dir: Path, *, collection_name: str = DEFAULT_CHROMA_COLLECTION) -> None:
        self.base_dir = base_dir
        self.base_dir.mkdir(parents=True, exist_ok=True)
        # Telemetria anônima do Chroma vem ligada por padrão; o app é local e não manda nada para fora.
        self._client = chromadb.PersistentClient(
            path=str(self.base_dir), settings=ChromaSettings(anonymized_telemetry=False)
        )
        self.collection_name = _resolve_collection_name(self._client, collection_name)

    def _collection(self) -> Collection:
        return self._client.get_or_create_collection(
            name=self.collection_name,
            metadata={'hnsw:space': 'cosine'},
        )

    def healthcheck(self) -> bool:
        return self.base_dir.exists()

    def count(self) -> int:
        return self._collection().count()

    def list_records(self) -> list[tuple[str, dict[str, object]]]:
        """Lista ids e metadados da collection ativa para checagem operacional."""
        result = self._collection().get(include=['metadatas'])
        ids = result.get('ids', [])
        metadatas = result.get('metadatas', [])
        records: list[tuple[str, dict[str, object]]] = []
        for chunk_id, metadata in zip(ids, metadatas, strict=False):
            if metadata is None:
                continue
            records.append((str(chunk_id), dict(metadata)))
        return records

    def list_chunk_ids(self) -> set[str]:
        return {chunk_id for chunk_id, _ in self.list_records()}

    def has_chunk_ids(self, chunk_ids: list[str]) -> bool:
        if not chunk_ids:
            return False
        result = self._collection().get(ids=chunk_ids)
        found_ids = {str(chunk_id) for chunk_id in result.get('ids', [])}
        return set(chunk_ids).issubset(found_ids)

    def delete_by_note_id(self, note_id: str) -> int:
        result = self._collection().get(where={'note_id': note_id})
        chunk_ids = [str(chunk_id) for chunk_id in result.get('ids', [])]
        if not chunk_ids:
            return 0
        self._collection().delete(ids=chunk_ids)
        return len(chunk_ids)

    def delete_by_note_ids(self, note_ids: list[str]) -> None:
        # ponytail: um delete por bloco de 500 notas; sem get prévio, o filtro $in roda no próprio Chroma.
        for start in range(0, len(note_ids), 500):
            block = note_ids[start : start + 500]
            self._collection().delete(where={'note_id': {'$in': block}})

    def reset(self) -> None:
        try:
            self._client.delete_collection(self.collection_name)
        except NotFoundError:
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

    def query(
        self,
        query_embedding: list[float],
        *,
        top_k: int = 5,
        note_id: str | None = None,
        note_ids: frozenset[str] | None = None,
    ) -> list[SearchHit]:
        if top_k <= 0 or self.count() == 0:
            return []
        if note_ids is not None and not note_ids:
            return []

        if note_id:
            where: dict[str, object] | None = {'note_id': note_id}
        elif note_ids is not None:
            where = {'note_id': {'$in': sorted(note_ids)}}
        else:
            where = None
        result = self._collection().query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            where=where,
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
