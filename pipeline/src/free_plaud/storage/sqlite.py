import json
import sqlite3
from collections.abc import Iterable
from datetime import datetime
from pathlib import Path

from free_plaud.notes.schemas import Note
from free_plaud.retrieval.models import Chunk
from free_plaud.storage.models import BenchmarkQueryRecord, BenchmarkRunRecord, ProcessingLogRecord

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


def count_notes(connection: sqlite3.Connection) -> int:
    row = connection.execute('SELECT COUNT(*) AS total FROM notes').fetchone()
    return int(row['total'])


def count_chunks(connection: sqlite3.Connection) -> int:
    row = connection.execute('SELECT COUNT(*) AS total FROM chunks').fetchone()
    return int(row['total'])


def list_chunk_ids(connection: sqlite3.Connection) -> set[str]:
    rows = connection.execute('SELECT chunk_id FROM chunks').fetchall()
    return {str(row['chunk_id']) for row in rows}


def delete_corpus_notes_and_chunks(connection: sqlite3.Connection) -> tuple[int, int]:
    """Remove apenas corpus persistido, preservando benchmark e logs."""
    notes_total = count_notes(connection)
    chunks_total = count_chunks(connection)
    connection.execute('DELETE FROM chunks')
    connection.execute('DELETE FROM notes')
    connection.commit()
    return notes_total, chunks_total


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
        created_at=datetime.fromisoformat(str(row['created_at']).replace('Z', '+00:00')),
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
