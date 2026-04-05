PRAGMA foreign_keys = ON;
PRAGMA journal_mode = WAL;
PRAGMA synchronous = NORMAL;
PRAGMA temp_store = MEMORY;

CREATE TABLE IF NOT EXISTS notes (
    note_id INTEGER PRIMARY KEY,
    source_type TEXT NOT NULL,
    source_uri TEXT,
    external_id TEXT,
    title TEXT,
    language_code TEXT NOT NULL DEFAULT 'pt-BR',
    markdown_content TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    metadata_json TEXT NOT NULL DEFAULT '{}' CHECK (json_valid(metadata_json)),
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'archived', 'deleted')),
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    UNIQUE (source_type, source_uri)
);

CREATE TABLE IF NOT EXISTS chunks (
    chunk_id INTEGER PRIMARY KEY,
    note_id INTEGER NOT NULL REFERENCES notes(note_id) ON DELETE CASCADE,
    chunk_index INTEGER NOT NULL,
    section_path TEXT,
    content TEXT NOT NULL,
    token_count INTEGER,
    char_start INTEGER,
    char_end INTEGER,
    chunk_hash TEXT NOT NULL,
    embedding_model TEXT,
    embedding_ref TEXT,
    metadata_json TEXT NOT NULL DEFAULT '{}' CHECK (json_valid(metadata_json)),
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    UNIQUE (note_id, chunk_index)
);

CREATE TABLE IF NOT EXISTS processing_logs (
    log_id INTEGER PRIMARY KEY,
    process_id TEXT NOT NULL,
    note_id INTEGER REFERENCES notes(note_id) ON DELETE SET NULL,
    chunk_id INTEGER REFERENCES chunks(chunk_id) ON DELETE SET NULL,
    stage TEXT NOT NULL CHECK (stage IN ('ingest', 'parse', 'normalize', 'chunk', 'embed', 'index', 'delete', 'benchmark')),
    status TEXT NOT NULL CHECK (status IN ('started', 'success', 'error', 'skipped')),
    pipeline_version TEXT NOT NULL,
    model_name TEXT,
    config_json TEXT NOT NULL DEFAULT '{}' CHECK (json_valid(config_json)),
    message TEXT,
    error_text TEXT,
    started_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    finished_at TEXT,
    duration_ms INTEGER
);

CREATE TABLE IF NOT EXISTS benchmark_runs (
    benchmark_run_id INTEGER PRIMARY KEY,
    run_name TEXT NOT NULL,
    dataset_name TEXT NOT NULL,
    corpus_snapshot TEXT NOT NULL,
    retrieval_strategy TEXT NOT NULL,
    chunking_strategy TEXT NOT NULL,
    embedding_model TEXT NOT NULL,
    reranker_model TEXT,
    top_k INTEGER NOT NULL CHECK (top_k > 0),
    query_count INTEGER NOT NULL CHECK (query_count >= 0),
    pipeline_version TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('started', 'success', 'error')),
    config_json TEXT NOT NULL DEFAULT '{}' CHECK (json_valid(config_json)),
    metrics_json TEXT NOT NULL DEFAULT '{}' CHECK (json_valid(metrics_json)),
    started_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    finished_at TEXT,
    duration_ms INTEGER,
    notes TEXT
);

CREATE TABLE IF NOT EXISTS benchmark_queries (
    benchmark_query_id INTEGER PRIMARY KEY,
    benchmark_run_id INTEGER NOT NULL REFERENCES benchmark_runs(benchmark_run_id) ON DELETE CASCADE,
    query_id TEXT,
    query_text TEXT NOT NULL,
    expected_note_id INTEGER REFERENCES notes(note_id) ON DELETE SET NULL,
    expected_chunk_id INTEGER REFERENCES chunks(chunk_id) ON DELETE SET NULL,
    expected_ref TEXT,
    retrieved_json TEXT NOT NULL DEFAULT '[]' CHECK (json_valid(retrieved_json)),
    hit_at_k INTEGER NOT NULL CHECK (hit_at_k IN (0, 1)),
    reciprocal_rank REAL,
    latency_ms INTEGER,
    notes TEXT
);

CREATE INDEX IF NOT EXISTS idx_notes_source ON notes(source_type, source_uri);
CREATE INDEX IF NOT EXISTS idx_notes_content_hash ON notes(content_hash);
CREATE INDEX IF NOT EXISTS idx_notes_updated_at ON notes(updated_at);
CREATE INDEX IF NOT EXISTS idx_notes_metadata_origin ON notes(json_extract(metadata_json, '$.origin'));

CREATE INDEX IF NOT EXISTS idx_chunks_note_id ON chunks(note_id);
CREATE INDEX IF NOT EXISTS idx_chunks_note_chunk_index ON chunks(note_id, chunk_index);
CREATE INDEX IF NOT EXISTS idx_chunks_embedding_model ON chunks(embedding_model);
CREATE INDEX IF NOT EXISTS idx_chunks_metadata_section ON chunks(json_extract(metadata_json, '$.section_type'));

CREATE INDEX IF NOT EXISTS idx_processing_logs_process_id ON processing_logs(process_id);
CREATE INDEX IF NOT EXISTS idx_processing_logs_stage_status ON processing_logs(stage, status, started_at);
CREATE INDEX IF NOT EXISTS idx_processing_logs_note_id ON processing_logs(note_id);
CREATE INDEX IF NOT EXISTS idx_processing_logs_chunk_id ON processing_logs(chunk_id);

CREATE INDEX IF NOT EXISTS idx_benchmark_runs_dataset ON benchmark_runs(dataset_name, started_at);
CREATE INDEX IF NOT EXISTS idx_benchmark_runs_strategy ON benchmark_runs(retrieval_strategy, embedding_model, chunking_strategy);
CREATE INDEX IF NOT EXISTS idx_benchmark_queries_run_id ON benchmark_queries(benchmark_run_id);
CREATE INDEX IF NOT EXISTS idx_benchmark_queries_hit_at_k ON benchmark_queries(hit_at_k, latency_ms);
