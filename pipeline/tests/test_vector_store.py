import json
from pathlib import Path

from typer.testing import CliRunner

from free_plaud.app.config import Settings
from free_plaud.cli import app
from free_plaud.notes.schemas import Note
from free_plaud.retrieval.indexer import index_note_in_vector_store
from free_plaud.retrieval.models import Chunk, SearchHit
from free_plaud.retrieval.search import _fuse_hits_by_rank, hybrid_search, open_semantic_search, semantic_search
from free_plaud.storage.vector import LocalVectorStore

runner = CliRunner()


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


def _build_note(tmp_path: Path, **overrides: object) -> Note:
    payload: dict[str, object] = {
        'note_id': 'vector-note',
        'note_version': 1,
        'source_type': 'md',
        'source_path': tmp_path / 'vector.md',
        'source_name': 'vector.md',
        'title': 'Benchmark vetorial',
        'summary': 'Resumo vetorial.',
        'topics': [],
        'tasks': [],
        'tags': ['md'],
        'raw_text': (
            'O benchmark compara recall e latencia entre estrategias de retrieval. '
            'O SQLite persiste metadados e logs. '
            'O frontend renderiza os resultados em uma tela separada.'
        ),
        'normalized_text': (
            'O benchmark compara recall e latencia entre estrategias de retrieval. '
            'O SQLite persiste metadados e logs. '
            'O frontend renderiza os resultados em uma tela separada.'
        ),
        'structured_markdown': (
            '# Benchmark vetorial\n\n'
            'O benchmark compara recall e latencia entre estrategias de retrieval.\n\n'
            'O SQLite persiste metadados e logs.\n\n'
            'O frontend renderiza os resultados em uma tela separada.\n'
        ),
        'content_hash': 'a' * 64,
    }
    payload.update(overrides)
    return Note(**payload)


def test_local_vector_store_upserts_and_queries_chunks_with_metadata(tmp_path: Path) -> None:
    embedder = FakeEmbedder()
    note = _build_note(tmp_path)
    store = LocalVectorStore(tmp_path / 'vector_store', collection_name='test_chunks')

    chunks = index_note_in_vector_store(note, store, embedder, chunk_size=90, overlap=20)
    hits = store.query(embedder.embed(['benchmark recall'])[0], top_k=2, note_id=note.note_id)

    assert store.healthcheck() is True
    assert store.count() == len(chunks)
    assert hits
    assert hits[0].chunk.note_id == note.note_id
    assert hits[0].chunk.note_version == note.note_version
    assert hits[0].chunk.chunk_id
    assert hits[0].score > 0


def test_delete_by_note_id_uses_filtered_lookup_without_global_scan(monkeypatch, tmp_path: Path) -> None:
    embedder = FakeEmbedder()
    store = LocalVectorStore(tmp_path / 'vector_store', collection_name='delete_by_note')
    first = _build_note(tmp_path, note_id='first-note')
    second = _build_note(tmp_path, note_id='second-note', title='Segunda nota')
    first_chunks = index_note_in_vector_store(first, store, embedder, chunk_size=90, overlap=20)
    index_note_in_vector_store(second, store, embedder, chunk_size=90, overlap=20)

    def fail_global_scan():
        raise AssertionError('delete_by_note_id nao deve listar a collection inteira')

    monkeypatch.setattr(store, 'list_records', fail_global_scan)

    deleted = store.delete_by_note_id(first.note_id)

    assert deleted == len(first_chunks)
    assert store.query(embedder.embed(['benchmark recall'])[0], top_k=5, note_id=first.note_id) == []
    assert store.query(embedder.embed(['benchmark recall'])[0], top_k=5, note_id=second.note_id)


def test_semantic_search_returns_ranked_hits_for_related_query(tmp_path: Path) -> None:
    embedder = FakeEmbedder()
    store = LocalVectorStore(tmp_path / 'vector_store', collection_name='semantic_search')
    note = _build_note(tmp_path)

    index_note_in_vector_store(note, store, embedder, chunk_size=90, overlap=20)
    hits = semantic_search('recall latencia retrieval', store, embedder, top_k=3, note_id=note.note_id)

    assert hits
    assert hits[0].strategy == 'vector'
    assert hits[0].chunk.note_id == note.note_id
    assert hits[0].score >= hits[-1].score


def test_hybrid_search_fuses_lexical_and_vector_hits(tmp_path: Path) -> None:
    embedder = FakeEmbedder()
    store = LocalVectorStore(tmp_path / 'vector_store', collection_name='hybrid_search')
    note = _build_note(tmp_path)

    chunks = index_note_in_vector_store(note, store, embedder, chunk_size=90, overlap=20)
    hits = hybrid_search(
        'benchmark recall',
        chunks,
        store,
        embedder,
        top_k=3,
        note_id=note.note_id,
    )

    assert hits
    assert hits[0].strategy == 'hybrid'
    assert hits[0].chunk.note_id == note.note_id
    assert 'benchmark' in hits[0].matched_terms
    assert hits[0].score >= hits[-1].score


def test_rank_fusion_supports_lexical_weighting() -> None:
    chunk_lexical = Chunk(
        chunk_id='chunk-lexical',
        note_id='vector-note',
        note_version=1,
        chunk_index=1,
        chunk_text='Benchmark recall e latencia.',
        token_count=4,
        char_start=25,
        char_end=53,
        chunk_size=90,
        overlap=20,
        strategy='fixed-window',
        normalized_text_sha256='a' * 64,
        text_sha256='b' * 64,
        pipeline_version='test',
    )
    chunk_vector = Chunk(
        chunk_id='chunk-vector',
        note_id='vector-note',
        note_version=1,
        chunk_index=0,
        chunk_text='Embeddings persistidos no ChromaDB.',
        token_count=4,
        char_start=54,
        char_end=88,
        chunk_size=90,
        overlap=20,
        strategy='fixed-window',
        normalized_text_sha256='c' * 64,
        text_sha256='d' * 64,
        pipeline_version='test',
    )
    lexical_hits = [SearchHit(chunk=chunk_lexical, score=2.0, matched_terms=[], term_coverage=0.0, strategy='lexical')]
    vector_hits = [
        SearchHit(chunk=chunk_vector, score=0.9, matched_terms=[], term_coverage=0.0, strategy='vector', distance=0.2),
    ]

    equal_weight_hits = _fuse_hits_by_rank(
        lexical_hits,
        vector_hits,
        top_k=2,
        rank_constant=1,
        lexical_weight=1.0,
        vector_weight=1.0,
    )
    lexical_weighted_hits = _fuse_hits_by_rank(
        lexical_hits,
        vector_hits,
        top_k=2,
        rank_constant=1,
        lexical_weight=4.0,
        vector_weight=1.0,
    )

    assert equal_weight_hits[0].chunk.chunk_id == 'chunk-vector'
    assert lexical_weighted_hits[0].chunk.chunk_id == 'chunk-lexical'
    assert lexical_weighted_hits[0].score > equal_weight_hits[0].score


def test_semantic_search_marks_fuzzy_term_matches_for_vector_hits() -> None:
    class StubVectorStore:
        def query(self, query_embedding: list[float], *, top_k: int, note_id: str | None = None) -> list[SearchHit]:
            chunk = Chunk(
                chunk_id='chunk-1',
                note_id='vector-note',
                note_version=1,
                chunk_index=0,
                chunk_text='O estudo esta medindo recall e latencia para avaliar retrieval.',
                token_count=10,
                char_start=0,
                char_end=68,
                chunk_size=90,
                overlap=20,
                strategy='fixed-window',
                normalized_text_sha256='a' * 64,
                text_sha256='b' * 64,
                pipeline_version='test',
            )
            return [SearchHit(chunk=chunk, score=0.71, strategy='vector', distance=0.41)]

    hits = semantic_search(
        'O que o estudo mede?',
        StubVectorStore(),
        FakeEmbedder(),
        top_k=1,
        note_id='vector-note',
    )

    assert hits
    assert hits[0].matched_terms == ['estudo', 'mede']
    assert hits[0].term_coverage == 1.0


def test_open_semantic_search_reranks_hits_using_lexical_evidence() -> None:
    class StubVectorStore:
        def query(self, query_embedding: list[float], *, top_k: int, note_id: str | None = None) -> list[SearchHit]:
            weak_chunk = Chunk(
                chunk_id='chunk-weak',
                note_id='vector-note',
                note_version=1,
                chunk_index=0,
                chunk_text='Documento sobre governanca geral e processos internos.',
                token_count=7,
                char_start=0,
                char_end=56,
                chunk_size=90,
                overlap=20,
                strategy='fixed-window',
                normalized_text_sha256='a' * 64,
                text_sha256='b' * 64,
                pipeline_version='test',
            )
            strong_chunk = Chunk(
                chunk_id='chunk-strong',
                note_id='vector-note',
                note_version=1,
                chunk_index=1,
                chunk_text='O pipeline adotou RabbitMQ como message broker padrao da plataforma.',
                token_count=10,
                char_start=57,
                char_end=126,
                chunk_size=90,
                overlap=20,
                strategy='fixed-window',
                normalized_text_sha256='c' * 64,
                text_sha256='d' * 64,
                pipeline_version='test',
            )
            return [
                SearchHit(chunk=weak_chunk, score=0.92, strategy='vector', distance=0.08),
                SearchHit(chunk=strong_chunk, score=0.71, strategy='vector', distance=0.40),
            ]

    hits = open_semantic_search(
        'Qual message broker foi adotado como padrao da plataforma?',
        StubVectorStore(),
        FakeEmbedder(),
        top_k=2,
    )

    assert hits
    assert hits[0].chunk.chunk_id == 'chunk-strong'
    assert 'message' in hits[0].matched_terms
    assert hits[0].term_coverage > 0.5


def test_open_semantic_search_filters_low_evidence_hits_for_long_queries() -> None:
    class StubVectorStore:
        def query(self, query_embedding: list[float], *, top_k: int, note_id: str | None = None) -> list[SearchHit]:
            weak_chunk = Chunk(
                chunk_id='chunk-weak',
                note_id='vector-note',
                note_version=1,
                chunk_index=0,
                chunk_text='Texto menciona domina, mas trata de relatorios internos e governanca.',
                token_count=10,
                char_start=0,
                char_end=70,
                chunk_size=90,
                overlap=20,
                strategy='fixed-window',
                normalized_text_sha256='a' * 64,
                text_sha256='b' * 64,
                pipeline_version='test',
            )
            return [SearchHit(chunk=weak_chunk, score=0.88, strategy='vector', distance=0.13)]

    hits = open_semantic_search(
        'Quais tecnologias o candidato domina para desenvolver apps mobile?',
        StubVectorStore(),
        FakeEmbedder(),
        top_k=5,
    )

    assert hits == []


def test_open_semantic_search_filters_hits_that_match_only_low_signal_terms() -> None:
    class StubVectorStore:
        def query(self, query_embedding: list[float], *, top_k: int, note_id: str | None = None) -> list[SearchHit]:
            weak_chunk = Chunk(
                chunk_id='chunk-weak',
                note_id='vector-note',
                note_version=1,
                chunk_index=0,
                chunk_text='O RabbitMQ foi escolhido por menor risco tecnico a curto prazo.',
                token_count=11,
                char_start=0,
                char_end=64,
                chunk_size=90,
                overlap=20,
                strategy='fixed-window',
                normalized_text_sha256='a' * 64,
                text_sha256='b' * 64,
                pipeline_version='test',
            )
            return [SearchHit(chunk=weak_chunk, score=0.90, strategy='vector', distance=0.11)]

    hits = open_semantic_search(
        'Qual banco relacional foi escolhido para autenticar o painel web?',
        StubVectorStore(),
        FakeEmbedder(),
        top_k=5,
    )

    assert hits == []


def test_index_note_in_vector_store_raises_when_embedding_count_does_not_match_chunks(tmp_path: Path) -> None:
    class BrokenEmbedder(FakeEmbedder):
        model_name = 'broken'

        def embed(self, texts: list[str]) -> list[list[float]]:
            return super().embed(texts[:-1])

    store = LocalVectorStore(tmp_path / 'vector_store', collection_name='broken_embeddings')
    note = _build_note(tmp_path)

    try:
        index_note_in_vector_store(note, store, BrokenEmbedder(), chunk_size=90, overlap=20)
    except ValueError as exc:
        assert 'embeddings' in str(exc)
    else:
        raise AssertionError('Era esperado ValueError quando a quantidade de embeddings nao bate com os chunks.')


def test_retrieval_index_and_semantic_search_cli_use_vector_store(monkeypatch, tmp_path: Path) -> None:
    settings = Settings(
        workspace_dir=tmp_path,
        data_dir=tmp_path / 'data',
        notes_dir=tmp_path / 'data' / 'corpus' / 'notes',
        datasets_dir=tmp_path / 'data' / 'datasets',
        results_dir=tmp_path / 'data' / 'results',
        sqlite_path=tmp_path / 'data' / 'results' / 'free_plaud.sqlite3',
        vector_store_dir=tmp_path / 'data' / 'results' / 'vector_store',
        vector_collection_name='cli_chunks',
        embedding_model='fake-hash',
    )
    sample_file = tmp_path / 'cli.md'
    sample_file.write_text(
        '# Documento vetorial\n\n'
        'O benchmark compara recall e latencia para retrieval.\n'
        'O SQLite persiste logs.\n',
        encoding='utf-8',
    )

    monkeypatch.setattr('free_plaud.retrieval.cli.get_settings', lambda: settings)
    monkeypatch.setattr('free_plaud.retrieval.cli.get_embedder', lambda model_name, **kwargs: FakeEmbedder())

    index_result = runner.invoke(app, ['retrieval', 'index', str(sample_file), '--chunk-size', '80', '--overlap', '20'])
    search_result = runner.invoke(
        app,
        ['retrieval', 'semantic-search', '--query', 'benchmark recall', '--top-k', '2', '--note-id', 'cli'],
    )

    assert index_result.exit_code == 0
    payload = json.loads(index_result.stdout)
    assert payload['embedding_model'] == 'fake-hash'
    assert payload['chunks_indexed'] >= 1

    assert search_result.exit_code == 0
    hits = json.loads(search_result.stdout)
    assert hits
    assert hits[0]['note_id'] == 'cli'
    assert hits[0]['strategy'] == 'vector'
    assert 'distance' in hits[0]
    assert 'matched_terms' in hits[0]
    assert 'term_coverage' in hits[0]


def test_open_semantic_search_cli_reranks_shared_collection_results(monkeypatch, tmp_path: Path) -> None:
    settings = Settings(
        workspace_dir=tmp_path,
        data_dir=tmp_path / 'data',
        notes_dir=tmp_path / 'data' / 'corpus' / 'notes',
        datasets_dir=tmp_path / 'data' / 'datasets',
        results_dir=tmp_path / 'data' / 'results',
        sqlite_path=tmp_path / 'data' / 'results' / 'free_plaud.sqlite3',
        vector_store_dir=tmp_path / 'data' / 'results' / 'vector_store',
        vector_collection_name='cli_open_chunks',
        embedding_model='fake-hash',
    )
    relevant_file = tmp_path / 'relevant.md'
    noisy_file = tmp_path / 'noisy.md'
    relevant_file.write_text(
        '# Plataforma\n\n'
        'A plataforma adotou RabbitMQ como message broker padrao.\n',
        encoding='utf-8',
    )
    noisy_file.write_text(
        '# Geral\n\n'
        'Documento de governanca e padrao de reunioes internas.\n',
        encoding='utf-8',
    )

    monkeypatch.setattr('free_plaud.retrieval.cli.get_settings', lambda: settings)
    monkeypatch.setattr('free_plaud.retrieval.cli.get_embedder', lambda model_name, **kwargs: FakeEmbedder())

    runner.invoke(app, ['retrieval', 'index', str(relevant_file), '--chunk-size', '80', '--overlap', '20'])
    runner.invoke(app, ['retrieval', 'index', str(noisy_file), '--chunk-size', '80', '--overlap', '20'])

    search_result = runner.invoke(
        app,
        ['retrieval', 'semantic-search', '--query', 'Qual message broker foi adotado como padrao da plataforma?', '--top-k', '3'],
    )

    assert search_result.exit_code == 0
    hits = json.loads(search_result.stdout)
    assert hits
    assert hits[0]['note_id'] == 'relevant'
    assert hits[0]['term_coverage'] > 0.5
