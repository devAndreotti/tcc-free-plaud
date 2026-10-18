import sqlite3
from pathlib import Path

from escolio.app.config import Settings
from escolio.corpus.ask import answer_corpus_with_citations
from escolio.corpus.service import index_corpus_path, reset_corpus
from escolio.retrieval.models import AskResponse
from escolio.storage.sqlite import (
    init_sqlite,
    list_corpus_roots,
    note_ids_under_root,
    record_corpus_root,
)
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


def _settings(tmp_path: Path) -> Settings:
    return Settings(
        workspace_dir=tmp_path,
        data_dir=tmp_path / 'data',
        notes_dir=tmp_path / 'data' / 'corpus' / 'notes',
        datasets_dir=tmp_path / 'data' / 'datasets',
        results_dir=tmp_path / 'data' / 'results',
        sqlite_path=tmp_path / 'data' / 'results' / 'escolio.sqlite3',
        vector_store_dir=tmp_path / 'data' / 'results' / 'vector_store',
        vector_collection_name='corpus_roots_test',
        embedding_model='fake-hash',
        default_chunk_size=220,
        default_chunk_overlap=40,
    )


def _write(folder: Path, name: str, text: str) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    (folder / name).write_text(text, encoding='utf-8')


def _index(settings: Settings, connection: sqlite3.Connection, vector_store: LocalVectorStore, folder: Path):
    return index_corpus_path(
        folder, settings=settings, connection=connection, vector_store=vector_store, embedder=FakeEmbedder()
    )


def _indexed_corpus(tmp_path: Path) -> tuple[Settings, sqlite3.Connection, LocalVectorStore, Path, Path]:
    settings = _settings(tmp_path)
    connection = init_sqlite(settings.sqlite_path)
    vector_store = LocalVectorStore(settings.vector_store_dir, collection_name=settings.vector_collection_name)
    obsidian = tmp_path / 'obsidian'
    culinaria = tmp_path / 'culinaria'
    _write(obsidian, 'broker.md', '# Broker\n\nRabbitMQ foi adotado como message broker do pipeline.\n')
    _write(obsidian, 'runbook.md', '# Runbook\n\nA equipe SRE ficou responsavel pelo runbook de operacao.\n')
    _write(culinaria, 'bolo.md', '# Bolo de chocolate\n\nPara o bolo de chocolate misture farinha, ovos e cacau.\n')
    _index(settings, connection, vector_store, obsidian)
    _index(settings, connection, vector_store, culinaria)
    return settings, connection, vector_store, obsidian, culinaria


def _sources(response: AskResponse) -> set[str]:
    return {source.source_path for source in response.used_sources}


def test_list_corpus_roots_lists_each_indexed_folder_with_notes_count_regressao(tmp_path: Path) -> None:
    _, connection, _, obsidian, culinaria = _indexed_corpus(tmp_path)

    roots = {row['root']: row['notes_count'] for row in list_corpus_roots(connection)}

    assert roots == {str(obsidian.resolve()): 2, str(culinaria.resolve()): 1}


def test_list_corpus_roots_omits_roots_without_notes_regressao(tmp_path: Path) -> None:
    _, connection, _, _, _ = _indexed_corpus(tmp_path)
    record_corpus_root(connection, tmp_path / 'vazia')

    roots = [row['root'] for row in list_corpus_roots(connection)]

    assert str((tmp_path / 'vazia').resolve()) not in roots
    assert len(roots) == 2


def test_source_root_respects_separator_boundary_regressao(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    connection = init_sqlite(settings.sqlite_path)
    vector_store = LocalVectorStore(settings.vector_store_dir, collection_name=settings.vector_collection_name)
    cul = tmp_path / 'cul'
    culinaria = tmp_path / 'culinaria'
    _write(cul, 'cafe.md', '# Cafe\n\nNota da pasta cul sobre cafe coado.\n')
    _write(culinaria, 'bolo.md', '# Bolo\n\nPara o bolo de chocolate misture farinha e cacau.\n')
    _index(settings, connection, vector_store, cul)
    _index(settings, connection, vector_store, culinaria)

    roots = {row['root']: row['notes_count'] for row in list_corpus_roots(connection)}
    cul_note_ids = note_ids_under_root(connection, str(cul))
    response = answer_corpus_with_citations(
        'Como fazer bolo de chocolate com farinha?',
        connection=connection,
        strategy='lexical',
        source_root=str(cul),
    )

    assert roots == {str(cul.resolve()): 1, str(culinaria.resolve()): 1}
    assert len(cul_note_ids) == 1
    assert response.status == 'no_answer'


def test_ask_with_source_root_cites_only_notes_of_that_folder_regressao(tmp_path: Path) -> None:
    _, connection, _, _, culinaria = _indexed_corpus(tmp_path)

    response = answer_corpus_with_citations(
        'Como fazer bolo de chocolate com farinha?',
        connection=connection,
        strategy='lexical',
        source_root=str(culinaria),
    )

    assert response.status == 'answer'
    assert _sources(response) == {str(culinaria / 'bolo.md')}


def test_ask_with_source_root_abstains_for_content_of_another_folder_regressao(tmp_path: Path) -> None:
    _, connection, _, _, culinaria = _indexed_corpus(tmp_path)

    response = answer_corpus_with_citations(
        'Qual message broker foi adotado no pipeline?',
        connection=connection,
        strategy='lexical',
        source_root=str(culinaria),
    )

    assert response.status == 'no_answer'
    assert response.no_answer is True
    assert response.citations == []


def test_ask_without_source_root_cites_notes_of_every_folder_regressao(tmp_path: Path) -> None:
    _, connection, _, obsidian, culinaria = _indexed_corpus(tmp_path)

    broker = answer_corpus_with_citations('Qual message broker foi adotado?', connection=connection, strategy='lexical')
    bolo = answer_corpus_with_citations('Como fazer bolo de chocolate?', connection=connection, strategy='lexical')

    assert str(obsidian / 'broker.md') in _sources(broker)
    assert str(culinaria / 'bolo.md') in _sources(bolo)


def test_root_is_recorded_when_reindex_is_all_unchanged_regressao(tmp_path: Path) -> None:
    settings, connection, vector_store, obsidian, _ = _indexed_corpus(tmp_path)
    connection.execute('DELETE FROM corpus_roots')
    connection.commit()

    result = _index(settings, connection, vector_store, obsidian)

    assert result.unchanged_count == 2
    assert str(obsidian.resolve()) in {row['root'] for row in list_corpus_roots(connection)}


def test_reset_corpus_clears_corpus_roots_regressao(tmp_path: Path) -> None:
    settings, connection, vector_store, _, _ = _indexed_corpus(tmp_path)
    assert list_corpus_roots(connection)

    reset_corpus(settings=settings, connection=connection, vector_store=vector_store, dry_run=False)

    assert list_corpus_roots(connection) == []
    assert connection.execute('SELECT COUNT(*) FROM corpus_roots').fetchone()[0] == 0


def test_ask_hybrid_with_source_root_filters_vector_candidates_regressao(tmp_path: Path) -> None:
    _, connection, vector_store, _, culinaria = _indexed_corpus(tmp_path)

    response = answer_corpus_with_citations(
        'Como fazer bolo de chocolate com farinha?',
        connection=connection,
        vector_store=vector_store,
        embedder=FakeEmbedder(),
        strategy='hybrid',
        source_root=str(culinaria),
    )
    abstained = answer_corpus_with_citations(
        'Qual message broker foi adotado no pipeline?',
        connection=connection,
        vector_store=vector_store,
        embedder=FakeEmbedder(),
        strategy='hybrid',
        source_root=str(culinaria),
    )

    assert response.status == 'answer'
    assert _sources(response) == {str(culinaria / 'bolo.md')}
    assert abstained.status == 'no_answer'
