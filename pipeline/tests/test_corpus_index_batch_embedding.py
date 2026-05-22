from pathlib import Path

from free_plaud.app.config import Settings
from free_plaud.corpus.service import index_corpus_path
from free_plaud.retrieval.models import Chunk
from free_plaud.storage.sqlite import count_chunks, count_notes, init_sqlite
from free_plaud.storage.vector import LocalVectorStore


class RecordingEmbedder:
    model_name = 'recording'

    def __init__(self) -> None:
        self.batch_sizes: list[int] = []

    def embed(self, texts: list[str]) -> list[list[float]]:
        self.batch_sizes.append(len(texts))
        return [[float(index + 1)] + [0.0] * 15 for index, _ in enumerate(texts)]


class BrokenBatchEmbedder(RecordingEmbedder):
    model_name = 'broken-batch'

    def embed(self, texts: list[str]) -> list[list[float]]:
        self.batch_sizes.append(len(texts))
        return super().embed(texts[:-1])


class RecordingVectorStore(LocalVectorStore):
    def __init__(self, base_dir: Path, *, collection_name: str) -> None:
        super().__init__(base_dir, collection_name=collection_name)
        self.upsert_sizes: list[int] = []

    def upsert_chunks(self, chunks: list[Chunk], embeddings: list[list[float]], *, embedding_model: str) -> None:
        self.upsert_sizes.append(len(chunks))
        super().upsert_chunks(chunks, embeddings, embedding_model=embedding_model)


def _settings(tmp_path: Path) -> Settings:
    return Settings(
        workspace_dir=tmp_path,
        data_dir=tmp_path / 'data',
        notes_dir=tmp_path / 'data' / 'corpus' / 'notes',
        datasets_dir=tmp_path / 'data' / 'datasets',
        results_dir=tmp_path / 'data' / 'results',
        sqlite_path=tmp_path / 'data' / 'results' / 'free_plaud.sqlite3',
        vector_store_dir=tmp_path / 'data' / 'results' / 'vector_store',
        vector_collection_name='corpus_batch_embedding_test',
        embedding_model='recording',
        default_chunk_size=600,
        default_chunk_overlap=40,
        corpus_embedding_batch_size=2,
        corpus_upsert_batch_size=2,
    )


def test_index_corpus_path_embeds_and_upserts_across_files_in_batches(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    root = tmp_path / 'corpus'
    root.mkdir()
    for index in range(5):
        (root / f'doc-{index}.md').write_text(
            f'# Doc {index}\n\nConteudo curto do documento {index} para um chunk.\n',
            encoding='utf-8',
        )
    embedder = RecordingEmbedder()
    vector_store = RecordingVectorStore(settings.vector_store_dir, collection_name=settings.vector_collection_name)

    result = index_corpus_path(
        root,
        settings=settings,
        vector_store=vector_store,
        embedder=embedder,
        recursive=True,
    )

    assert result.status == 'success'
    assert result.indexed_count == 5
    assert result.unchanged_count == 0
    assert embedder.batch_sizes == [2, 2, 1]
    assert vector_store.upsert_sizes == [2, 2, 1]


def test_index_corpus_path_skips_batch_embedding_for_unchanged_files(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    root = tmp_path / 'corpus'
    root.mkdir()
    for index in range(3):
        (root / f'doc-{index}.md').write_text(
            f'# Doc {index}\n\nConteudo estavel do documento {index}.\n',
            encoding='utf-8',
        )
    first_embedder = RecordingEmbedder()
    second_embedder = RecordingEmbedder()
    vector_store = RecordingVectorStore(settings.vector_store_dir, collection_name=settings.vector_collection_name)

    first = index_corpus_path(
        root,
        settings=settings,
        vector_store=vector_store,
        embedder=first_embedder,
        recursive=True,
    )
    second = index_corpus_path(
        root,
        settings=settings,
        vector_store=vector_store,
        embedder=second_embedder,
        recursive=True,
    )

    assert first.status == 'success'
    assert second.status == 'success'
    assert second.indexed_count == 0
    assert second.unchanged_count == 3
    assert second_embedder.batch_sizes == []


def test_index_corpus_path_handles_batch_embedding_size_mismatch(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    root = tmp_path / 'corpus'
    root.mkdir()
    (root / 'a.md').write_text('# A\n\nConteudo A.\n', encoding='utf-8')
    (root / 'b.md').write_text('# B\n\nConteudo B.\n', encoding='utf-8')
    vector_store = RecordingVectorStore(settings.vector_store_dir, collection_name=settings.vector_collection_name)

    result = index_corpus_path(
        root,
        settings=settings,
        vector_store=vector_store,
        embedder=BrokenBatchEmbedder(),
        recursive=True,
    )
    connection = init_sqlite(settings.sqlite_path)

    assert result.status == 'failed'
    assert result.indexed_count == 0
    assert result.failed_count == 2
    assert {item.status for item in result.results} == {'failed'}
    assert vector_store.upsert_sizes == []
    assert count_notes(connection) == 0
    assert count_chunks(connection) == 0
