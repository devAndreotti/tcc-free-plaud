import json
from pathlib import Path

from typer.testing import CliRunner

from free_plaud.app.config import Settings
from free_plaud.cli import app
from free_plaud.notes.schemas import Note
from free_plaud.retrieval.chunking import chunk_text
from free_plaud.storage.models import BenchmarkQueryRecord, BenchmarkRunRecord, ProcessingLogRecord
from free_plaud.storage.sqlite import (
    connect_sqlite,
    get_notes_by_id,
    init_sqlite,
    insert_benchmark_query,
    insert_benchmark_run,
    insert_processing_log,
    list_chunks,
    replace_chunks_for_note,
    upsert_note,
)

runner = CliRunner()


def _build_note(tmp_path: Path) -> Note:
    return Note(
        note_id='sample-note',
        note_version=1,
        source_type='md',
        source_path=tmp_path / 'sample.md',
        source_name='sample.md',
        title='Sample Note',
        summary='Resumo da nota.',
        topics=[],
        tasks=[],
        tags=['md'],
        raw_text='Texto bruto da nota.',
        normalized_text='Texto normalizado da nota.',
        structured_markdown='---\ntitle: Sample Note\n---\n\n# Sample Note\n\nTexto normalizado da nota.',
        content_hash='a' * 64,
    )


def test_init_sqlite_creates_expected_tables(tmp_path: Path) -> None:
    db_path = tmp_path / 'free_plaud.sqlite3'

    connection = init_sqlite(db_path)

    tables = {
        row['name']
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
        )
    }

    assert {'notes', 'chunks', 'processing_logs', 'benchmark_runs', 'benchmark_queries'} <= tables


def test_upsert_note_persists_canonical_note_fields(tmp_path: Path) -> None:
    db_path = tmp_path / 'free_plaud.sqlite3'
    note = _build_note(tmp_path)

    connection = init_sqlite(db_path)
    upsert_note(connection, note)

    row = connection.execute(
        'SELECT note_id, note_version, source_type, source_path, title, summary, content_hash FROM notes WHERE note_id = ?',
        (note.note_id,),
    ).fetchone()

    assert row['note_id'] == note.note_id
    assert row['note_version'] == note.note_version
    assert row['source_type'] == note.source_type
    assert row['source_path'] == str(note.source_path)
    assert row['title'] == note.title
    assert row['summary'] == note.summary
    assert row['content_hash'] == note.content_hash


def test_replace_chunks_for_note_persists_offset_aware_lineage(tmp_path: Path) -> None:
    db_path = tmp_path / 'free_plaud.sqlite3'
    note = _build_note(tmp_path)
    chunks = chunk_text(
        note.note_id,
        note.note_version,
        note.normalized_text,
        chunk_size=12,
        overlap=4,
        normalized_text_sha256=note.content_hash,
    )

    connection = init_sqlite(db_path)
    upsert_note(connection, note)
    replace_chunks_for_note(connection, note.note_id, chunks)

    rows = connection.execute(
        'SELECT chunk_id, note_id, note_version, chunk_index, char_start, char_end, strategy FROM chunks WHERE note_id = ? ORDER BY chunk_index',
        (note.note_id,),
    ).fetchall()

    assert len(rows) == len(chunks)
    assert rows[0]['note_id'] == note.note_id
    assert rows[0]['note_version'] == note.note_version
    assert rows[0]['chunk_index'] == 0
    assert rows[0]['char_start'] == 0
    assert rows[0]['char_end'] > rows[0]['char_start']
    assert rows[0]['strategy'] == 'fixed_char_window'


def test_list_chunks_and_get_notes_by_id_return_persisted_contract(tmp_path: Path) -> None:
    db_path = tmp_path / 'free_plaud.sqlite3'
    note = _build_note(tmp_path)
    chunks = chunk_text(
        note.note_id,
        note.note_version,
        note.normalized_text,
        chunk_size=12,
        overlap=4,
        normalized_text_sha256=note.content_hash,
    )

    connection = init_sqlite(db_path)
    upsert_note(connection, note)
    replace_chunks_for_note(connection, note.note_id, chunks)

    persisted_chunks = list_chunks(connection)
    notes = get_notes_by_id(connection, [note.note_id])

    assert [chunk.chunk_id for chunk in persisted_chunks] == [chunk.chunk_id for chunk in chunks]
    assert notes[note.note_id].note_id == note.note_id
    assert notes[note.note_id].source_path == note.source_path


def test_insert_processing_log_and_benchmark_records(tmp_path: Path) -> None:
    db_path = tmp_path / 'free_plaud.sqlite3'
    note = _build_note(tmp_path)
    chunks = chunk_text(
        note.note_id,
        note.note_version,
        note.normalized_text,
        chunk_size=12,
        overlap=4,
        normalized_text_sha256=note.content_hash,
    )
    log = ProcessingLogRecord(
        process_id='proc-001',
        note_id=note.note_id,
        chunk_id=chunks[0].chunk_id,
        stage='chunk',
        status='success',
        pipeline_version='pipeline-0.4.2',
        config={'chunk_size': 12, 'overlap': 4},
        message='Chunking concluido.',
        duration_ms=42,
    )
    benchmark_run = BenchmarkRunRecord(
        benchmark_run_id='run-001',
        run_name='baseline',
        dataset_name='demo',
        corpus_snapshot='snapshot-001',
        retrieval_strategy='lexical',
        chunking_strategy='fixed_char_window',
        embedding_model='not-run-yet',
        top_k=3,
        query_count=1,
        pipeline_version='pipeline-0.4.2',
        status='success',
        metrics={'recall_at_3': 1.0},
    )
    benchmark_query = BenchmarkQueryRecord(
        benchmark_run_id='run-001',
        query_id='q-1',
        query_text='o que a nota descreve?',
        expected_note_id=note.note_id,
        expected_chunk_id=chunks[0].chunk_id,
        retrieved=[{'chunk_id': chunks[0].chunk_id, 'rank': 1, 'score': 1.0}],
        hit_at_k=1,
        reciprocal_rank=1.0,
        latency_ms=15,
    )

    connection = init_sqlite(db_path)
    upsert_note(connection, note)
    replace_chunks_for_note(connection, note.note_id, chunks)
    insert_processing_log(connection, log)
    insert_benchmark_run(connection, benchmark_run)
    insert_benchmark_query(connection, benchmark_query)

    log_row = connection.execute(
        'SELECT process_id, stage, status, config_json, message FROM processing_logs WHERE process_id = ?',
        ('proc-001',),
    ).fetchone()
    run_row = connection.execute(
        'SELECT benchmark_run_id, retrieval_strategy, metrics_json FROM benchmark_runs WHERE benchmark_run_id = ?',
        ('run-001',),
    ).fetchone()
    query_row = connection.execute(
        'SELECT benchmark_run_id, expected_note_id, expected_chunk_id, retrieved_json, hit_at_k FROM benchmark_queries WHERE query_id = ?',
        ('q-1',),
    ).fetchone()

    assert log_row['stage'] == 'chunk'
    assert json.loads(log_row['config_json']) == {'chunk_size': 12, 'overlap': 4}
    assert run_row['retrieval_strategy'] == 'lexical'
    assert json.loads(run_row['metrics_json'])['recall_at_3'] == 1.0
    assert query_row['expected_note_id'] == note.note_id
    assert query_row['expected_chunk_id'] == chunks[0].chunk_id
    assert json.loads(query_row['retrieved_json'])[0]['rank'] == 1
    assert query_row['hit_at_k'] == 1


def test_storage_init_cli_creates_sqlite_database(monkeypatch, tmp_path: Path) -> None:
    settings = Settings(
        workspace_dir=tmp_path,
        data_dir=tmp_path / 'data',
        notes_dir=tmp_path / 'data' / 'corpus' / 'notes',
        datasets_dir=tmp_path / 'data' / 'datasets',
        results_dir=tmp_path / 'data' / 'results',
        sqlite_path=tmp_path / 'data' / 'results' / 'free_plaud.sqlite3',
        vector_store_dir=tmp_path / 'data' / 'results' / 'vector_store',
    )
    monkeypatch.setattr('free_plaud.storage.cli.get_settings', lambda: settings)

    result = runner.invoke(app, ['storage', 'init'])

    assert result.exit_code == 0
    assert settings.sqlite_path.exists()
    connection = connect_sqlite(settings.sqlite_path)
    row = connection.execute("SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'notes'").fetchone()
    assert row['name'] == 'notes'
