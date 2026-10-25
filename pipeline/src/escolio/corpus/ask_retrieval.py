import sqlite3
from collections.abc import Callable
from typing import Literal

from escolio.providers.embed import Embedder
from escolio.retrieval.models import Chunk, SearchHit
from escolio.retrieval.search import (
    _stem_like,
    fuse_hits_by_rank,
    lexical_search_hits,
    match_terms_in_text,
    normalize_query_terms,
    open_semantic_search,
)
from escolio.storage.sqlite import (
    count_chunks,
    ensure_chunks_fts_current,
    list_chunks,
    list_fts_vocabulary,
)
from escolio.storage.vector import LocalVectorStore

# Busca FTS injetada pelo chamador (ask.py passa search_chunks_fts, para o monkeypatch dos testes valer).
FtsSearch = Callable[..., list[tuple[Chunk, float]]]


RetrievalStrategy = Literal['lexical', 'vector', 'hybrid']


# Radicais do vocabulário do corpus, por (arquivo, chunks no FTS, último rowid): muda a cada indexação.
_VOCABULARY_STEMS: dict[tuple[str, int, int], frozenset[str]] = {}


def _vocabulary_key(connection: sqlite3.Connection) -> tuple[str, int, int]:
    # Consultas baratas: COUNT(*) no FTS varre a tabela (~40 ms com 4 mil chunks); o maior rowid
    # do FTS muda a cada chunk gravado.
    path = str(connection.execute('PRAGMA database_list').fetchone()[2])
    last_rowid = connection.execute('SELECT MAX(rowid) FROM chunks_fts').fetchone()[0]
    return path, count_chunks(connection), int(last_rowid or 0)


def corpus_vocabulary_stems(connection: sqlite3.Connection) -> frozenset[str] | None:
    """Radicais das palavras do corpus, em cache até a próxima indexação (~1 s com 4 mil chunks)."""
    try:
        key = _vocabulary_key(connection)
        if key[0] and key in _VOCABULARY_STEMS:
            return _VOCABULARY_STEMS[key]
        if ensure_chunks_fts_current(connection) == 'rebuilt':
            key = _vocabulary_key(connection)
        stems = frozenset(_stem_like(term) for term in list_fts_vocabulary(connection))
    except sqlite3.OperationalError:
        return None  # sem FTS, a pergunta segue sem este filtro
    if key[0]:  # banco em memória não tem caminho estável para servir de chave
        _VOCABULARY_STEMS.clear()  # ponytail: um corpus por vez; o app e o benchmark alternam pouco
        _VOCABULARY_STEMS[key] = stems
    return stems


def _filter_hits_to_persisted_chunks(hits: list[SearchHit], valid_chunk_ids: set[str]) -> tuple[list[SearchHit], int]:
    filtered: list[SearchHit] = []
    stale_chunk_ids: set[str] = set()
    for hit in hits:
        if hit.chunk.chunk_id in valid_chunk_ids:
            filtered.append(hit)
        else:
            stale_chunk_ids.add(hit.chunk.chunk_id)
    return filtered, len(stale_chunk_ids)


def _build_fts_match_query(query_terms: list[str]) -> str:
    escaped_terms = [term.replace('"', '""') for term in query_terms if term.strip()]
    return ' OR '.join(f'"{term}"' for term in escaped_terms)


def fts_lexical_search_hits(
    connection: sqlite3.Connection,
    query: str,
    *,
    top_k: int = 5,
    candidate_limit: int | None = None,
    note_ids: frozenset[str] | None = None,
    search_rows: FtsSearch,
) -> list[SearchHit]:
    """Busca lexical do corpus via FTS5/BM25, com fallback Python se FTS falhar."""
    if top_k <= 0:
        return []

    query_terms = normalize_query_terms(query)
    if not query_terms:
        return []

    match_query = _build_fts_match_query(query_terms)
    if not match_query:
        return []

    try:
        ensure_chunks_fts_current(connection)
        candidate_rows = search_rows(
            connection,
            match_query,
            limit=candidate_limit or max(top_k * 4, 40),
            note_ids=note_ids,
        )
    except sqlite3.OperationalError:
        return lexical_search_hits(query, _chunks_in_scope(connection, note_ids), top_k=top_k)

    scored: list[SearchHit] = []
    for rank, (chunk, bm25_score) in enumerate(candidate_rows, start=1):
        matched_terms, term_coverage = match_terms_in_text(query_terms, chunk.chunk_text)
        if not matched_terms:
            continue
        scored.append(
            SearchHit(
                chunk=chunk,
                score=float(len(matched_terms)) + (1.0 / rank),
                matched_terms=matched_terms,
                term_coverage=term_coverage,
                strategy='lexical',
                distance=abs(bm25_score),
            )
        )

    if scored:
        return scored[:top_k]
    return lexical_search_hits(query, _chunks_in_scope(connection, note_ids), top_k=top_k)


def _chunks_in_scope(connection: sqlite3.Connection, note_ids: frozenset[str] | None) -> list[Chunk]:
    chunks = list_chunks(connection)
    if note_ids is None:
        return chunks
    return [chunk for chunk in chunks if chunk.note_id in note_ids]


def retrieve_corpus_hits(
    question: str,
    *,
    connection: sqlite3.Connection,
    valid_chunk_ids: set[str],
    top_k: int,
    strategy: RetrievalStrategy,
    vector_store: LocalVectorStore | None,
    embedder: Embedder | None,
    search_rows: FtsSearch,
    note_ids: frozenset[str] | None = None,
) -> tuple[list[SearchHit], int]:
    # O escopo entra na consulta (FTS: IN; Chroma: $in), então a pasta nunca fica sem candidatos por pool curto.
    if strategy == 'lexical':
        return fts_lexical_search_hits(connection, question, top_k=top_k, note_ids=note_ids, search_rows=search_rows), 0

    if vector_store is None or embedder is None:
        raise ValueError('Vector store e embedder sao obrigatorios para strategy=vector e strategy=hybrid.')

    candidate_pool_size = max(top_k * 8, 24)
    if strategy == 'vector':
        vector_hits = open_semantic_search(question, vector_store, embedder, top_k=candidate_pool_size, note_ids=note_ids)
        filtered_hits, stale_count = _filter_hits_to_persisted_chunks(vector_hits, valid_chunk_ids)
        return filtered_hits[:top_k], stale_count

    if strategy == 'hybrid':
        lexical_hits = fts_lexical_search_hits(
            connection,
            question,
            top_k=max(top_k * 3, top_k),
            note_ids=note_ids,
            search_rows=search_rows,
        )
        vector_hits = open_semantic_search(question, vector_store, embedder, top_k=candidate_pool_size, note_ids=note_ids)
        filtered_vector_hits, stale_count = _filter_hits_to_persisted_chunks(vector_hits, valid_chunk_ids)
        return (
            fuse_hits_by_rank(
                lexical_hits,
                filtered_vector_hits,
                top_k=top_k,
            ),
            stale_count,
        )

    raise ValueError("strategy deve ser 'lexical', 'vector' ou 'hybrid'.")
