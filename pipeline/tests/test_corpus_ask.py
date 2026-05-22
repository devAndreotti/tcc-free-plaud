from pathlib import Path

from free_plaud.app.config import Settings
from free_plaud.corpus.ask import answer_corpus_with_citations
from free_plaud.corpus.service import index_corpus_path
from free_plaud.retrieval.models import Chunk, SearchHit
from free_plaud.storage.sqlite import init_sqlite, list_chunks
from free_plaud.storage.vector import LocalVectorStore


class FakeEmbedder:
    model_name = 'fake-hash'

    def embed(self, texts: list[str]) -> list[list[float]]:
        embeddings: list[list[float]] = []
        for text in texts:
            vector = [0.0] * 16
            for token in text.lower().split():
                slot = sum(ord(char) for char in token) % len(vector)
                vector[slot] += 1.0
            embeddings.append(vector)
        return embeddings


class StubVectorStore:
    def __init__(self, hits: list[SearchHit]) -> None:
        self.hits = hits

    def query(self, query_embedding: list[float], *, top_k: int = 5, note_id: str | None = None) -> list[SearchHit]:
        return self.hits[:top_k]


def _settings(tmp_path: Path) -> Settings:
    return Settings(
        workspace_dir=tmp_path,
        data_dir=tmp_path / 'data',
        notes_dir=tmp_path / 'data' / 'corpus' / 'notes',
        datasets_dir=tmp_path / 'data' / 'datasets',
        results_dir=tmp_path / 'data' / 'results',
        sqlite_path=tmp_path / 'data' / 'results' / 'free_plaud.sqlite3',
        vector_store_dir=tmp_path / 'data' / 'results' / 'vector_store',
        vector_collection_name='corpus_ask_test',
        embedding_model='fake-hash',
        default_chunk_size=220,
        default_chunk_overlap=40,
    )


def _chunk(chunk_id: str, note_id: str, text: str) -> Chunk:
    return Chunk(
        chunk_id=chunk_id,
        note_id=note_id,
        note_version=1,
        chunk_index=0,
        char_start=0,
        char_end=len(text),
        chunk_size=220,
        overlap=40,
        chunk_text=text,
        token_count=len(text.split()),
        strategy='fixed_window',
        normalized_text_sha256=f'{chunk_id}-normalized',
        text_sha256=f'{chunk_id}-text',
        pipeline_version='test',
    )


def _build_distributed_corpus(root: Path) -> None:
    root.mkdir()
    (root / '01_contexto_base.md').write_text(
        '# Contexto base\n\n'
        'RabbitMQ foi adotado como message broker padrao do pipeline.\n',
        encoding='utf-8',
    )
    (root / '02_detalhe_operacional.md').write_text(
        '# Detalhe operacional\n\n'
        'O runbook de operacao do broker ficou sob responsabilidade da equipe de Plataforma. '
        'O prazo combinado para entregar a primeira versao operacional e de 15 dias corridos. '
        'Esse runbook deve cobrir filas e reprocessamento.\n',
        encoding='utf-8',
    )
    (root / '03_restricao_arquitetural.md').write_text(
        '# Restricao arquitetural\n\n'
        'O padrao Bronze, Silver e Gold divide o pipeline de dados.\n',
        encoding='utf-8',
    )


def test_answer_corpus_with_citations_stitches_multiple_files(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    root = tmp_path / 'corpus'
    _build_distributed_corpus(root)
    embedder = FakeEmbedder()
    vector_store = LocalVectorStore(settings.vector_store_dir, collection_name=settings.vector_collection_name)
    connection = init_sqlite(settings.sqlite_path)
    index_corpus_path(root, settings=settings, connection=connection, vector_store=vector_store, embedder=embedder, recursive=True)

    response = answer_corpus_with_citations(
        'Qual message broker foi adotado, qual equipe ficou responsavel pelo runbook e qual padrao divide o pipeline em Bronze, Silver e Gold?',
        connection=connection,
        vector_store=vector_store,
        embedder=embedder,
        strategy='hybrid',
        top_k=6,
    )

    assert response.status == 'answer'
    assert response.answer
    assert 'RabbitMQ' in response.answer
    assert 'Plataforma' in response.answer
    assert 'Bronze, Silver e Gold' in response.answer
    assert '15 dias corridos' not in response.answer
    assert 'filas e reprocessamento' not in response.answer
    assert {source.doc_id for source in response.used_sources} >= {
        '01-contexto-base',
        '02-detalhe-operacional',
        '03-restricao-arquitetural',
    }
    assert len({citation.note_id for citation in response.citations}) >= 3


def test_answer_corpus_with_citations_returns_no_answer_for_irrelevant_question(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    root = tmp_path / 'corpus'
    _build_distributed_corpus(root)
    embedder = FakeEmbedder()
    vector_store = LocalVectorStore(settings.vector_store_dir, collection_name=settings.vector_collection_name)
    connection = init_sqlite(settings.sqlite_path)
    index_corpus_path(root, settings=settings, connection=connection, vector_store=vector_store, embedder=embedder, recursive=True)

    response = answer_corpus_with_citations(
        'Quais tecnologias o candidato domina para desenvolver apps mobile?',
        connection=connection,
        vector_store=vector_store,
        embedder=embedder,
        strategy='hybrid',
        top_k=6,
    )

    assert response.status == 'no_answer'
    assert response.no_answer is True
    assert response.reason_for_no_answer is not None


def test_answer_corpus_filters_stale_vector_hits_before_citations(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    root = tmp_path / 'corpus'
    _build_distributed_corpus(root)
    connection = init_sqlite(settings.sqlite_path)
    index_corpus_path(root, settings=settings, connection=connection, embedder=FakeEmbedder(), recursive=True)
    stale = _chunk('stale-mobile-1', 'stale-mobile', 'Flutter e React Native sao tecnologias mobile dominadas.')
    vector_store = StubVectorStore([SearchHit(chunk=stale, score=0.99, strategy='vector')])

    response = answer_corpus_with_citations(
        'Quais tecnologias mobile o candidato domina?',
        connection=connection,
        vector_store=vector_store,  # type: ignore[arg-type]
        embedder=FakeEmbedder(),
        strategy='vector',
        top_k=4,
    )

    assert response.status == 'no_answer'
    assert response.no_answer is True
    assert response.citations == []
    assert all(source.doc_id != 'stale-mobile' for source in response.used_sources)
    assert any('stale' in limitation.lower() or 'obsoleto' in limitation.lower() for limitation in response.limitations)


def test_answer_corpus_uses_valid_vector_hit_after_dropping_stale_hit(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    root = tmp_path / 'corpus'
    _build_distributed_corpus(root)
    connection = init_sqlite(settings.sqlite_path)
    index_corpus_path(root, settings=settings, connection=connection, embedder=FakeEmbedder(), recursive=True)
    valid_chunk = next(chunk for chunk in list_chunks(connection) if chunk.note_id == '01-contexto-base')
    stale = _chunk('stale-broker-1', 'stale-broker', 'RabbitMQ foi adotado como message broker em outro corpus.')
    vector_store = StubVectorStore(
        [
            SearchHit(chunk=stale, score=0.99, strategy='vector'),
            SearchHit(chunk=valid_chunk, score=0.95, strategy='vector'),
        ]
    )

    response = answer_corpus_with_citations(
        'Qual message broker foi adotado?',
        connection=connection,
        vector_store=vector_store,  # type: ignore[arg-type]
        embedder=FakeEmbedder(),
        strategy='vector',
        top_k=4,
    )

    assert response.status == 'answer'
    assert 'RabbitMQ' in (response.answer or '')
    assert {citation.note_id for citation in response.citations} == {'01-contexto-base'}
    assert all(citation.note_id != 'stale-broker' for citation in response.citations)
