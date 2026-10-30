import sqlite3

import escolio.corpus.ask as ask_module
from escolio.corpus.ask import retrieve_corpus_hits
from escolio.retrieval.models import Chunk, SearchHit
from escolio.retrieval.rerank import rerank_hits


class FakeReranker:
    """Pontua pelo texto do chunk, sem baixar modelo."""

    model_name = 'fake-reranker'

    def __init__(self, scores: dict[str, float]) -> None:
        self._scores = scores
        self.calls: list[tuple[str, list[str]]] = []

    def score(self, query: str, passages: list[str]) -> list[float]:
        self.calls.append((query, list(passages)))
        return [self._scores[passage] for passage in passages]


def _hit(text: str, score: float, *, strategy: str = 'lexical') -> SearchHit:
    chunk = Chunk(
        chunk_id=f'chunk-{text}',
        note_id='note-1',
        note_version=1,
        chunk_index=0,
        char_start=0,
        char_end=len(text),
        chunk_size=800,
        overlap=120,
        chunk_text=text,
        token_count=len(text.split()),
        strategy='fixed',
        normalized_text_sha256='n',
        text_sha256='t',
        pipeline_version='test',
    )
    return SearchHit(chunk=chunk, score=score, strategy=strategy)


def test_rerank_hits_reorders_by_reranker_score() -> None:
    hits = [_hit('a', 0.9), _hit('b', 0.5), _hit('c', 0.7)]
    reranker = FakeReranker({'a': 0.1, 'b': 0.9, 'c': 0.5})

    result = rerank_hits('pergunta', hits, reranker, top_k=3)

    assert [hit.chunk.chunk_text for hit in result] == ['b', 'c', 'a']
    assert [hit.rerank_score for hit in result] == [0.9, 0.5, 0.1]
    # `score` (escala RRF/vetor) não muda: os limiares de abstenção do ask dependem dele.
    assert [hit.score for hit in result] == [0.5, 0.7, 0.9]
    assert all(hit.strategy == 'lexical' for hit in result)
    assert reranker.calls == [('pergunta', ['a', 'b', 'c'])]


def test_rerank_hits_keeps_original_order_on_ties() -> None:
    hits = [_hit('x', 0.1), _hit('y', 0.2), _hit('z', 0.3)]
    reranker = FakeReranker({'x': 1.0, 'y': 1.0, 'z': 1.0})

    result = rerank_hits('pergunta', hits, reranker, top_k=2)

    assert [hit.chunk.chunk_text for hit in result] == ['x', 'y']


def test_rerank_hits_empty_list_returns_empty_without_calling_reranker() -> None:
    reranker = FakeReranker({})

    assert rerank_hits('pergunta', [], reranker, top_k=3) == []
    assert reranker.calls == []


def test_rerank_hits_without_reranker_keeps_order_and_cuts_top_k() -> None:
    hits = [_hit('a', 0.9), _hit('b', 0.5), _hit('c', 0.7)]

    result = rerank_hits('pergunta', hits, None, top_k=2)

    assert [hit.chunk.chunk_text for hit in result] == ['a', 'b']
    assert [hit.score for hit in result] == [0.9, 0.5]


def test_rerank_hits_rejects_score_count_mismatch() -> None:
    class ShortReranker:
        model_name = 'short'

        def score(self, query: str, passages: list[str]) -> list[float]:
            return [0.5]

    try:
        rerank_hits('pergunta', [_hit('a', 0.1), _hit('b', 0.2)], ShortReranker(), top_k=2)
    except ValueError as exc:
        assert '1 scores para 2 hits' in str(exc)
    else:
        raise AssertionError('mismatch deveria falhar')


def test_retrieve_corpus_hits_widens_pool_and_reranks_before_cut(monkeypatch) -> None:
    pool = [_hit('a', 0.9), _hit('b', 0.5), _hit('c', 0.7)]
    requested: list[int] = []

    def fake_fts(connection, question, *, top_k, note_ids=None):
        requested.append(top_k)
        return pool[:top_k]

    monkeypatch.setattr(ask_module, 'fts_lexical_search_hits', fake_fts)
    reranker = FakeReranker({'a': 0.1, 'b': 0.9, 'c': 0.5})

    hits, stale = retrieve_corpus_hits(
        'pergunta',
        connection=sqlite3.connect(':memory:'),
        valid_chunk_ids=set(),
        top_k=2,
        strategy='lexical',
        vector_store=None,
        embedder=None,
        reranker=reranker,
    )

    assert requested == [24]
    assert stale == 0
    assert [hit.chunk.chunk_text for hit in hits] == ['b', 'c']


def test_reranker_from_settings_empty_model_disables() -> None:
    from escolio.app.config import Settings
    from escolio.retrieval.rerank import reranker_from_settings

    assert reranker_from_settings(Settings(rerank_model='')) is None
    assert reranker_from_settings(Settings(rerank_model='   ')) is None
