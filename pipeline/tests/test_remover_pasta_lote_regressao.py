import sqlite3
from pathlib import Path

from escolio.app.config import Settings
from escolio.corpus.service import index_corpus_path, remove_corpus_root
from escolio.storage.sqlite import count_notes, init_sqlite, note_ids_under_root
from escolio.storage.vector import LocalVectorStore


class FakeEmbedder:
    model_name = 'fake-hash'

    def embed(self, texts: list[str]) -> list[list[float]]:
        embeddings: list[list[float]] = []
        for text in texts:
            vector = [0.0] * 16
            for token in text.lower().split():
                vector[sum(ord(char) for char in token) % len(vector)] += 1.0
            embeddings.append(vector)
        return embeddings


class SpyStore(LocalVectorStore):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.single_calls = 0
        self.batch_calls = 0

    def delete_by_note_id(self, note_id: str) -> int:
        self.single_calls += 1
        return super().delete_by_note_id(note_id)

    def delete_by_note_ids(self, note_ids: list[str]) -> None:
        self.batch_calls += 1
        super().delete_by_note_ids(note_ids)


def _settings(tmp_path: Path) -> Settings:
    return Settings(
        workspace_dir=tmp_path,
        data_dir=tmp_path / 'data',
        notes_dir=tmp_path / 'data' / 'corpus' / 'notes',
        datasets_dir=tmp_path / 'data' / 'datasets',
        results_dir=tmp_path / 'data' / 'results',
        sqlite_path=tmp_path / 'data' / 'results' / 'escolio.sqlite3',
        vector_store_dir=tmp_path / 'data' / 'results' / 'vector_store',
        vector_collection_name='remover_lote_test',
        strategy='hybrid',
    )


def _write_folder(folder: Path, count: int, prefix: str) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    for index in range(count):
        text = f'# {prefix} {index}\n\nNota {prefix} numero {index} sobre cafe coado e bolo de cacau.\n'
        (folder / f'{prefix}-{index}.md').write_text(text, encoding='utf-8')


def _marks(n: int) -> str:
    return ','.join('?' * n)


def _count(connection: sqlite3.Connection, sql: str, params: tuple = ()) -> int:
    return int(connection.execute(sql, params).fetchone()[0])


def test_remove_corpus_root_deletes_all_notes_in_batch_regressao(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    connection = init_sqlite(settings.sqlite_path)
    vector_store = SpyStore(settings.vector_store_dir, collection_name=settings.vector_collection_name)
    cul = tmp_path / 'cul'
    other = tmp_path / 'other'
    _write_folder(cul, 7, 'cul')
    _write_folder(other, 2, 'other')
    index_corpus_path(cul, settings=settings, connection=connection, vector_store=vector_store, embedder=FakeEmbedder())
    index_corpus_path(other, settings=settings, connection=connection, vector_store=vector_store, embedder=FakeEmbedder())
    other_ids = note_ids_under_root(connection, str(other.resolve()))
    cul_ids = note_ids_under_root(connection, str(cul.resolve()))
    assert len(cul_ids) == 7

    commits: list[str] = []
    connection.set_trace_callback(lambda sql: commits.append(sql) if sql.strip().upper() == 'COMMIT' else None)
    vector_store.single_calls = 0
    vector_store.batch_calls = 0

    removed = remove_corpus_root(str(cul.resolve()), settings=settings, connection=connection, vector_store=vector_store)
    connection.set_trace_callback(None)

    assert removed == 7
    assert note_ids_under_root(connection, str(cul.resolve())) == set()
    assert _count(connection, f'SELECT COUNT(*) FROM chunks WHERE note_id IN ({_marks(7)})', tuple(cul_ids)) == 0
    assert _count(connection, f'SELECT COUNT(*) FROM chunks_fts WHERE note_id IN ({_marks(7)})', tuple(cul_ids)) == 0
    assert {record[1]['note_id'] for record in vector_store.list_records()} == other_ids
    assert count_notes(connection) == 2
    assert _count(connection, f'SELECT COUNT(*) FROM chunks_fts WHERE note_id IN ({_marks(2)})', tuple(other_ids)) > 0
    # Em lote: uma chamada ao Chroma por bloco (aqui, um bloco) e nenhuma chamada por nota.
    assert vector_store.single_calls == 0
    assert vector_store.batch_calls == 1
    # Um COMMIT do lote de notas e outro do forget_corpus_root (esquecer a raiz); nada de commit por nota.
    assert len(commits) == 2
    assert (cul / 'cul-0.md').exists()
