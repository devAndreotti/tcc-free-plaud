import json
import os
import sqlite3
from collections.abc import Iterable
from datetime import datetime
from pathlib import Path

from escolio.notes.schemas import Note
from escolio.retrieval.models import Chunk
from escolio.storage.models import (
    BenchmarkQueryRecord,
    BenchmarkRunRecord,
    ProcessingLogRecord,
)

SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS notes (
    note_id TEXT PRIMARY KEY,
    note_version INTEGER NOT NULL,
    source_type TEXT NOT NULL,
    source_path TEXT NOT NULL,
    source_name TEXT NOT NULL,
    title TEXT NOT NULL,
    summary TEXT NOT NULL,
    raw_text TEXT NOT NULL,
    normalized_text TEXT NOT NULL,
    structured_markdown TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    provider TEXT NOT NULL,
    model TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS chunks (
    chunk_id TEXT PRIMARY KEY,
    note_id TEXT NOT NULL REFERENCES notes(note_id) ON DELETE CASCADE,
    note_version INTEGER NOT NULL,
    chunk_index INTEGER NOT NULL,
    char_start INTEGER NOT NULL,
    char_end INTEGER NOT NULL,
    chunk_size INTEGER NOT NULL,
    overlap INTEGER NOT NULL,
    chunk_text TEXT NOT NULL,
    token_count INTEGER NOT NULL,
    strategy TEXT NOT NULL,
    normalized_text_sha256 TEXT NOT NULL,
    text_sha256 TEXT NOT NULL,
    pipeline_version TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    UNIQUE (note_id, note_version, chunk_index)
);

CREATE TABLE IF NOT EXISTS corpus_roots (
    root TEXT PRIMARY KEY,
    last_indexed_at TEXT
);

CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
    chunk_id UNINDEXED,
    note_id UNINDEXED,
    chunk_text,
    tokenize = 'unicode61 remove_diacritics 2'
);

CREATE TABLE IF NOT EXISTS processing_logs (
    log_id INTEGER PRIMARY KEY AUTOINCREMENT,
    process_id TEXT NOT NULL,
    note_id TEXT REFERENCES notes(note_id) ON DELETE SET NULL,
    chunk_id TEXT REFERENCES chunks(chunk_id) ON DELETE SET NULL,
    stage TEXT NOT NULL,
    status TEXT NOT NULL,
    pipeline_version TEXT NOT NULL,
    config_json TEXT NOT NULL DEFAULT '{}' CHECK (json_valid(config_json)),
    message TEXT,
    error_text TEXT,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    duration_ms INTEGER
);

CREATE TABLE IF NOT EXISTS benchmark_runs (
    benchmark_run_id TEXT PRIMARY KEY,
    run_name TEXT NOT NULL,
    dataset_name TEXT NOT NULL,
    corpus_snapshot TEXT NOT NULL,
    retrieval_strategy TEXT NOT NULL,
    chunking_strategy TEXT NOT NULL,
    embedding_model TEXT NOT NULL,
    top_k INTEGER NOT NULL CHECK (top_k > 0),
    query_count INTEGER NOT NULL CHECK (query_count >= 0),
    pipeline_version TEXT NOT NULL,
    status TEXT NOT NULL,
    config_json TEXT NOT NULL DEFAULT '{}' CHECK (json_valid(config_json)),
    metrics_json TEXT NOT NULL DEFAULT '{}' CHECK (json_valid(metrics_json)),
    started_at TEXT NOT NULL,
    finished_at TEXT,
    duration_ms INTEGER,
    notes TEXT
);

CREATE TABLE IF NOT EXISTS benchmark_queries (
    benchmark_query_id INTEGER PRIMARY KEY AUTOINCREMENT,
    benchmark_run_id TEXT NOT NULL REFERENCES benchmark_runs(benchmark_run_id) ON DELETE CASCADE,
    query_id TEXT,
    query_text TEXT NOT NULL,
    expected_note_id TEXT REFERENCES notes(note_id) ON DELETE SET NULL,
    expected_chunk_id TEXT REFERENCES chunks(chunk_id) ON DELETE SET NULL,
    expected_ref TEXT,
    retrieved_json TEXT NOT NULL DEFAULT '[]' CHECK (json_valid(retrieved_json)),
    hit_at_k INTEGER NOT NULL CHECK (hit_at_k IN (0, 1)),
    reciprocal_rank REAL,
    latency_ms INTEGER,
    notes TEXT
);
"""


def _json_dump(payload: dict[str, object] | list[dict[str, object]]) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def connect_sqlite(path: Path) -> sqlite3.Connection:
    """Abre conexão local com SQLite garantindo o diretório pai."""
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.execute('PRAGMA foreign_keys = ON')
    return connection


def init_sqlite(path: Path) -> sqlite3.Connection:
    """Inicializa o schema mínimo da Sprint 4.2."""
    connection = connect_sqlite(path)
    connection.executescript(SCHEMA)
    connection.commit()
    return connection


def upsert_note(connection: sqlite3.Connection, note: Note) -> None:
    connection.execute(
        """
        INSERT INTO notes (
            note_id, note_version, source_type, source_path, source_name, title, summary,
            raw_text, normalized_text, structured_markdown, content_hash, provider, model, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(note_id) DO UPDATE SET
            note_version = excluded.note_version,
            source_type = excluded.source_type,
            source_path = excluded.source_path,
            source_name = excluded.source_name,
            title = excluded.title,
            summary = excluded.summary,
            raw_text = excluded.raw_text,
            normalized_text = excluded.normalized_text,
            structured_markdown = excluded.structured_markdown,
            content_hash = excluded.content_hash,
            provider = excluded.provider,
            model = excluded.model,
            created_at = excluded.created_at
        """,
        (
            note.note_id,
            note.note_version,
            note.source_type,
            str(note.source_path),
            note.source_name,
            note.title,
            note.summary,
            note.raw_text,
            note.normalized_text,
            note.structured_markdown,
            note.content_hash,
            note.provider,
            note.model,
            note.created_at.isoformat(),
        ),
    )
    connection.commit()


def replace_chunks_for_note(connection: sqlite3.Connection, note_id: str, chunks: list[Chunk]) -> None:
    connection.execute('DELETE FROM chunks WHERE note_id = ?', (note_id,))
    connection.execute('DELETE FROM chunks_fts WHERE note_id = ?', (note_id,))
    connection.executemany(
        """
        INSERT INTO chunks (
            chunk_id, note_id, note_version, chunk_index, char_start, char_end, chunk_size,
            overlap, chunk_text, token_count, strategy, normalized_text_sha256, text_sha256, pipeline_version
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (
                chunk.chunk_id,
                chunk.note_id,
                chunk.note_version,
                chunk.chunk_index,
                chunk.char_start,
                chunk.char_end,
                chunk.chunk_size,
                chunk.overlap,
                chunk.chunk_text,
                chunk.token_count,
                chunk.strategy,
                chunk.normalized_text_sha256,
                chunk.text_sha256,
                chunk.pipeline_version,
            )
            for chunk in chunks
        ],
    )
    connection.executemany(
        """
        INSERT INTO chunks_fts (chunk_id, note_id, chunk_text)
        VALUES (?, ?, ?)
        """,
        [(chunk.chunk_id, chunk.note_id, chunk.chunk_text) for chunk in chunks],
    )
    connection.commit()


def _chunk_from_row(row: sqlite3.Row) -> Chunk:
    return Chunk(
        chunk_id=row['chunk_id'],
        note_id=row['note_id'],
        note_version=row['note_version'],
        chunk_index=row['chunk_index'],
        char_start=row['char_start'],
        char_end=row['char_end'],
        chunk_size=row['chunk_size'],
        overlap=row['overlap'],
        chunk_text=row['chunk_text'],
        token_count=row['token_count'],
        strategy=row['strategy'],
        normalized_text_sha256=row['normalized_text_sha256'],
        text_sha256=row['text_sha256'],
        pipeline_version=row['pipeline_version'],
    )


def list_chunks(connection: sqlite3.Connection) -> list[Chunk]:
    """Lista chunks persistidos em ordem estavel para retrieval de corpus."""
    rows = connection.execute(
        """
        SELECT
            chunk_id, note_id, note_version, chunk_index, char_start, char_end, chunk_size,
            overlap, chunk_text, token_count, strategy, normalized_text_sha256,
            text_sha256, pipeline_version
        FROM chunks
        ORDER BY note_id, note_version, chunk_index
        """
    ).fetchall()
    return [_chunk_from_row(row) for row in rows]


def list_chunks_for_note(connection: sqlite3.Connection, note_id: str) -> list[Chunk]:
    """Lista apenas chunks de uma nota, em ordem estavel para detalhe operacional."""
    rows = connection.execute(
        """
        SELECT
            chunk_id, note_id, note_version, chunk_index, char_start, char_end, chunk_size,
            overlap, chunk_text, token_count, strategy, normalized_text_sha256,
            text_sha256, pipeline_version
        FROM chunks
        WHERE note_id = ?
        ORDER BY note_version, chunk_index
        """,
        (note_id,),
    ).fetchall()
    return [_chunk_from_row(row) for row in rows]


def count_notes(connection: sqlite3.Connection) -> int:
    row = connection.execute('SELECT COUNT(*) AS total FROM notes').fetchone()
    return int(row['total'])


def count_chunks(connection: sqlite3.Connection) -> int:
    row = connection.execute('SELECT COUNT(*) AS total FROM chunks').fetchone()
    return int(row['total'])


def count_fts_chunks(connection: sqlite3.Connection) -> int:
    row = connection.execute('SELECT COUNT(*) AS total FROM chunks_fts').fetchone()
    return int(row['total'])


def rebuild_chunks_fts(connection: sqlite3.Connection) -> int:
    """Reconstrói o indice FTS a partir da tabela canonica de chunks."""
    connection.execute('DELETE FROM chunks_fts')
    connection.execute(
        """
        INSERT INTO chunks_fts (chunk_id, note_id, chunk_text)
        SELECT chunk_id, note_id, chunk_text
        FROM chunks
        ORDER BY note_id, note_version, chunk_index
        """
    )
    connection.commit()
    return count_fts_chunks(connection)


def ensure_chunks_fts_current(connection: sqlite3.Connection) -> str:
    """Garante FTS sincronizado para bancos antigos ou importados."""
    chunks_total = count_chunks(connection)
    fts_total = count_fts_chunks(connection)
    if fts_total == chunks_total:
        return 'ready'
    if chunks_total == 0:
        connection.execute('DELETE FROM chunks_fts')
        connection.commit()
        return 'ready'
    rebuild_chunks_fts(connection)
    return 'rebuilt'


def list_fts_vocabulary(connection: sqlite3.Connection) -> list[str]:
    """Palavras indexadas no FTS (minúsculas, sem acento), via fts5vocab na base temporária."""
    connection.execute(
        "CREATE VIRTUAL TABLE IF NOT EXISTS temp.chunks_fts_vocab USING fts5vocab(main, 'chunks_fts', 'row')"
    )
    return [str(row[0]) for row in connection.execute('SELECT term FROM temp.chunks_fts_vocab')]


def search_chunks_fts(
    connection: sqlite3.Connection,
    match_query: str,
    *,
    limit: int,
    note_ids: frozenset[str] | None = None,
) -> list[tuple[Chunk, float]]:
    """Busca candidatos lexicais via FTS5/BM25, opcionalmente restrita a algumas notas."""
    if not match_query.strip() or limit <= 0:
        return []
    if note_ids is not None and not note_ids:
        return []
    scope_sql = ''
    params: list[object] = [match_query]
    if note_ids is not None:
        scope_sql = f"AND c.note_id IN ({', '.join('?' for _ in note_ids)})"
        params.extend(sorted(note_ids))
    params.append(limit)
    rows = connection.execute(
        f"""
        SELECT
            c.chunk_id, c.note_id, c.note_version, c.chunk_index, c.char_start, c.char_end,
            c.chunk_size, c.overlap, c.chunk_text, c.token_count, c.strategy,
            c.normalized_text_sha256, c.text_sha256, c.pipeline_version,
            bm25(chunks_fts) AS bm25_score
        FROM chunks_fts
        JOIN chunks AS c ON c.chunk_id = chunks_fts.chunk_id
        WHERE chunks_fts MATCH ? {scope_sql}
        ORDER BY bm25_score
        LIMIT ?
        """,
        params,
    ).fetchall()
    return [(_chunk_from_row(row), float(row['bm25_score'])) for row in rows]


def list_chunk_ids(connection: sqlite3.Connection) -> set[str]:
    rows = connection.execute('SELECT chunk_id FROM chunks').fetchall()
    return {str(row['chunk_id']) for row in rows}


def list_chunk_ids_for_note(connection: sqlite3.Connection, note_id: str) -> list[str]:
    rows = connection.execute(
        'SELECT chunk_id FROM chunks WHERE note_id = ? ORDER BY chunk_index',
        (note_id,),
    ).fetchall()
    return [str(row['chunk_id']) for row in rows]


def get_note_content_hash(connection: sqlite3.Connection, note_id: str) -> str | None:
    row = connection.execute('SELECT content_hash FROM notes WHERE note_id = ?', (note_id,)).fetchone()
    if row is None:
        return None
    return str(row['content_hash'])


def list_note_ids_by_source_path(connection: sqlite3.Connection, source_path: Path | str) -> list[str]:
    rows = connection.execute(
        'SELECT note_id FROM notes WHERE source_path = ? ORDER BY note_id',
        (str(source_path),),
    ).fetchall()
    return [str(row['note_id']) for row in rows]


def delete_note_and_chunks(connection: sqlite3.Connection, note_id: str) -> None:
    connection.execute('DELETE FROM chunks_fts WHERE note_id = ?', (note_id,))
    connection.execute('DELETE FROM chunks WHERE note_id = ?', (note_id,))
    connection.execute('DELETE FROM notes WHERE note_id = ?', (note_id,))
    connection.commit()


def note_chunks_match_config(connection: sqlite3.Connection, note_id: str, *, chunk_size: int, overlap: int) -> bool:
    rows = connection.execute(
        'SELECT chunk_size, overlap FROM chunks WHERE note_id = ?',
        (note_id,),
    ).fetchall()
    if not rows:
        return False
    return all(int(row['chunk_size']) == chunk_size and int(row['overlap']) == overlap for row in rows)


def delete_corpus_notes_and_chunks(connection: sqlite3.Connection) -> tuple[int, int]:
    """Remove apenas corpus persistido, preservando benchmark e logs."""
    notes_total = count_notes(connection)
    chunks_total = count_chunks(connection)
    connection.execute('DELETE FROM chunks_fts')
    connection.execute('DELETE FROM chunks')
    connection.execute('DELETE FROM notes')
    connection.execute('DELETE FROM corpus_roots')
    connection.commit()
    return notes_total, chunks_total


def _path_key(path: str | Path) -> str:
    # Sem tocar no disco. normcase deixa o Windows case-insensitive e unifica '/' e '\\'.
    return os.path.normcase(os.path.abspath(str(path)))


def _is_under_root(path_key: str, root_key: str) -> bool:
    # Fronteira de separador: 'C:\\x\\cul' não pode casar 'C:\\x\\culinaria'.
    return path_key == root_key or path_key.startswith(root_key.rstrip(os.sep) + os.sep)


def record_corpus_root(connection: sqlite3.Connection, root: Path) -> None:
    """Registra uma pasta indexada como raiz do corpus (chamador passa o caminho resolvido)."""
    connection.execute(
        """
        INSERT INTO corpus_roots (root, last_indexed_at) VALUES (?, ?)
        ON CONFLICT(root) DO UPDATE SET last_indexed_at = excluded.last_indexed_at
        """,
        (str(root), datetime.now().astimezone().isoformat()),
    )
    connection.commit()


def list_corpus_roots(connection: sqlite3.Connection) -> list[dict[str, object]]:
    """Pastas indexadas que têm notas, com a quantidade de notas sob cada uma."""
    roots = [str(row['root']) for row in connection.execute('SELECT root FROM corpus_roots ORDER BY root')]
    note_keys = [_path_key(row['source_path']) for row in connection.execute('SELECT source_path FROM notes')]
    result: list[dict[str, object]] = []
    for root in roots:
        root_key = _path_key(root)
        notes_count = sum(_is_under_root(note_key, root_key) for note_key in note_keys)
        if notes_count:
            result.append({'root': root, 'notes_count': notes_count})
    return result


def note_ids_under_root(connection: sqlite3.Connection, root: str) -> set[str]:
    """Ids das notas cujo arquivo está sob a pasta (incluindo subpastas)."""
    root_key = _path_key(root)
    rows = connection.execute('SELECT note_id, source_path FROM notes').fetchall()
    return {str(row['note_id']) for row in rows if _is_under_root(_path_key(row['source_path']), root_key)}


def _note_from_row(row: sqlite3.Row) -> Note:
    return Note(
        note_id=row['note_id'],
        note_version=row['note_version'],
        source_type=row['source_type'],
        source_path=Path(row['source_path']),
        source_name=row['source_name'],
        title=row['title'],
        summary=row['summary'],
        topics=[],
        tasks=[],
        tags=[row['source_type']],
        raw_text=row['raw_text'],
        normalized_text=row['normalized_text'],
        structured_markdown=row['structured_markdown'],
        content_hash=row['content_hash'],
        provider=row['provider'],
        model=row['model'],
        created_at=datetime.fromisoformat(str(row['created_at'])),
    )


def get_notes_by_id(connection: sqlite3.Connection, note_ids: Iterable[str]) -> dict[str, Note]:
    """Retorna notas persistidas por id, preservando contrato Pydantic de Note."""
    unique_ids = list(dict.fromkeys(note_ids))
    if not unique_ids:
        return {}

    placeholders = ', '.join('?' for _ in unique_ids)
    rows = connection.execute(
        f"""
        SELECT
            note_id, note_version, source_type, source_path, source_name, title, summary,
            raw_text, normalized_text, structured_markdown, content_hash, provider, model, created_at
        FROM notes
        WHERE note_id IN ({placeholders})
        """,
        unique_ids,
    ).fetchall()
    return {row['note_id']: _note_from_row(row) for row in rows}


def get_all_notes(connection: sqlite3.Connection) -> list[Note]:
    """Lista notas persistidas para telas operacionais e inspecao local."""
    rows = connection.execute(
        """
        SELECT
            note_id, note_version, source_type, source_path, source_name, title, summary,
            raw_text, normalized_text, structured_markdown, content_hash, provider, model, created_at
        FROM notes
        ORDER BY created_at DESC, note_id
        """
    ).fetchall()
    return [_note_from_row(row) for row in rows]


def insert_processing_log(connection: sqlite3.Connection, record: ProcessingLogRecord) -> None:
    connection.execute(
        """
        INSERT INTO processing_logs (
            process_id, note_id, chunk_id, stage, status, pipeline_version, config_json,
            message, error_text, started_at, finished_at, duration_ms
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            record.process_id,
            record.note_id,
            record.chunk_id,
            record.stage,
            record.status,
            record.pipeline_version,
            _json_dump(record.config),
            record.message,
            record.error_text,
            record.started_at.isoformat(),
            record.finished_at.isoformat() if record.finished_at else None,
            record.duration_ms,
        ),
    )
    connection.commit()


def insert_benchmark_run(connection: sqlite3.Connection, record: BenchmarkRunRecord) -> None:
    connection.execute(
        """
        INSERT INTO benchmark_runs (
            benchmark_run_id, run_name, dataset_name, corpus_snapshot, retrieval_strategy, chunking_strategy,
            embedding_model, top_k, query_count, pipeline_version, status, config_json, metrics_json,
            started_at, finished_at, duration_ms, notes
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            record.benchmark_run_id,
            record.run_name,
            record.dataset_name,
            record.corpus_snapshot,
            record.retrieval_strategy,
            record.chunking_strategy,
            record.embedding_model,
            record.top_k,
            record.query_count,
            record.pipeline_version,
            record.status,
            _json_dump(record.config),
            _json_dump(record.metrics),
            record.started_at.isoformat(),
            record.finished_at.isoformat() if record.finished_at else None,
            record.duration_ms,
            record.notes,
        ),
    )
    connection.commit()


def insert_benchmark_query(connection: sqlite3.Connection, record: BenchmarkQueryRecord) -> None:
    connection.execute(
        """
        INSERT INTO benchmark_queries (
            benchmark_run_id, query_id, query_text, expected_note_id, expected_chunk_id, expected_ref,
            retrieved_json, hit_at_k, reciprocal_rank, latency_ms, notes
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            record.benchmark_run_id,
            record.query_id,
            record.query_text,
            record.expected_note_id,
            record.expected_chunk_id,
            record.expected_ref,
            _json_dump(record.retrieved),
            record.hit_at_k,
            record.reciprocal_rank,
            record.latency_ms,
            record.notes,
        ),
    )
    connection.commit()
