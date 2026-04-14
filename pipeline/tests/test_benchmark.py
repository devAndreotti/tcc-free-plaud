import csv
import json
from pathlib import Path

from typer.testing import CliRunner

from free_plaud.app.config import Settings
from free_plaud.benchmark.datasets import BenchmarkDataset, BenchmarkSample, load_benchmark_dataset
from free_plaud.benchmark.metrics import mean_reciprocal_rank, recall_at_k_from_ranks
from free_plaud.benchmark.reports import export_benchmark_csv, export_benchmark_json
from free_plaud.benchmark.runners import run_benchmark
from free_plaud.cli import app
from free_plaud.notes.schemas import Note
from free_plaud.retrieval.indexer import index_note
from free_plaud.storage.sqlite import connect_sqlite, init_sqlite

runner = CliRunner()


def _build_note(tmp_path: Path) -> Note:
    text = (
        'O benchmark mede recall, latencia e cobertura de citacoes para comparar retrieval. '
        'A recuperacao vetorial usa embeddings persistidos no ChromaDB local. '
        'O SQLite registra execucoes, metricas e consultas avaliadas.'
    )
    return Note(
        note_id='benchmark-note',
        note_version=1,
        source_type='md',
        source_path=tmp_path / 'benchmark.md',
        source_name='benchmark.md',
        title='Benchmark do pipeline RAG',
        summary='Resumo da nota de benchmark.',
        topics=[],
        tasks=[],
        tags=['md'],
        raw_text=text,
        normalized_text=text,
        structured_markdown=f'# Benchmark do pipeline RAG\n\n{text}\n',
        content_hash='a' * 64,
    )


def test_load_benchmark_dataset_from_json_object(tmp_path: Path) -> None:
    dataset_path = tmp_path / 'dataset.json'
    dataset_path.write_text(
        json.dumps(
            {
                'dataset_name': 'rag-baseline',
                'samples': [
                    {
                        'sample_id': 'q-1',
                        'question': 'O que o benchmark mede?',
                        'expected_note_id': 'benchmark-note',
                        'expected_terms': ['recall', 'latencia'],
                    }
                ],
            }
        ),
        encoding='utf-8',
    )

    dataset = load_benchmark_dataset(dataset_path)

    assert dataset.dataset_name == 'rag-baseline'
    assert dataset.samples[0].sample_id == 'q-1'
    assert dataset.samples[0].expected_note_id == 'benchmark-note'
    assert dataset.samples[0].expected_terms == ['recall', 'latencia']


def test_metrics_compute_mrr_and_recall_at_k_from_ranks() -> None:
    ranks = [1, 4, None]

    assert mean_reciprocal_rank(ranks) == (1.0 + 0.25 + 0.0) / 3
    assert recall_at_k_from_ranks(ranks, 3) == 1 / 3
    assert recall_at_k_from_ranks(ranks, 5) == 2 / 3


def test_run_benchmark_persists_run_and_queries_in_sqlite(tmp_path: Path) -> None:
    note = _build_note(tmp_path)
    chunks = index_note(note, chunk_size=120, overlap=30)
    dataset = BenchmarkDataset(
        dataset_name='rag-baseline',
        samples=[
            BenchmarkSample(
                sample_id='q-1',
                question='O que o benchmark mede?',
                expected_note_id=note.note_id,
                expected_chunk_id=chunks[0].chunk_id,
                expected_terms=['recall', 'latencia'],
            ),
            BenchmarkSample(
                sample_id='q-2',
                question='Qual message broker foi escolhido?',
                expected_terms=['kafka'],
            ),
        ],
    )
    connection = init_sqlite(tmp_path / 'free_plaud.sqlite3')

    result = run_benchmark(
        note,
        dataset,
        connection=connection,
        strategy='lexical',
        top_k=3,
        chunk_size=120,
        overlap=30,
        run_name='lexical-baseline',
    )

    run_row = connection.execute(
        'SELECT benchmark_run_id, dataset_name, retrieval_strategy, query_count, metrics_json FROM benchmark_runs WHERE benchmark_run_id = ?',
        (result.benchmark_run_id,),
    ).fetchone()
    query_rows = connection.execute(
        'SELECT query_id, hit_at_k, reciprocal_rank FROM benchmark_queries WHERE benchmark_run_id = ? ORDER BY query_id',
        (result.benchmark_run_id,),
    ).fetchall()

    assert result.metrics['query_count'] == 2
    assert result.metrics['recall_at_3'] == 0.5
    assert result.metrics['mrr'] == 0.5
    assert run_row['dataset_name'] == 'rag-baseline'
    assert run_row['retrieval_strategy'] == 'lexical'
    assert run_row['query_count'] == 2
    assert json.loads(run_row['metrics_json'])['recall_at_3'] == 0.5
    assert [row['hit_at_k'] for row in query_rows] == [1, 0]
    assert [row['reciprocal_rank'] for row in query_rows] == [1.0, 0.0]


def test_export_benchmark_json_and_csv(tmp_path: Path) -> None:
    note = _build_note(tmp_path)
    dataset = BenchmarkDataset(
        dataset_name='rag-baseline',
        samples=[
            BenchmarkSample(
                sample_id='q-1',
                question='O que o benchmark mede?',
                expected_note_id=note.note_id,
                expected_terms=['recall', 'latencia'],
            )
        ],
    )
    result = run_benchmark(note, dataset, strategy='lexical', top_k=3, chunk_size=120, overlap=30)

    json_path = export_benchmark_json(result, tmp_path / 'benchmark.json')
    csv_path = export_benchmark_csv(result, tmp_path / 'benchmark.csv')

    json_payload = json.loads(json_path.read_text(encoding='utf-8'))
    with csv_path.open(encoding='utf-8', newline='') as handle:
        csv_rows = list(csv.DictReader(handle))

    assert json_payload['benchmark_run_id'] == result.benchmark_run_id
    assert json_payload['metrics']['recall_at_3'] == 1.0
    assert csv_rows[0]['sample_id'] == 'q-1'
    assert csv_rows[0]['hit_at_k'] == '1'


def test_benchmark_run_cli_executes_dataset_and_exports_reports(monkeypatch, tmp_path: Path) -> None:
    settings = Settings(
        workspace_dir=tmp_path,
        data_dir=tmp_path / 'data',
        notes_dir=tmp_path / 'data' / 'corpus' / 'notes',
        datasets_dir=tmp_path / 'data' / 'datasets',
        results_dir=tmp_path / 'data' / 'results',
        sqlite_path=tmp_path / 'data' / 'results' / 'free_plaud.sqlite3',
        vector_store_dir=tmp_path / 'data' / 'results' / 'vector_store',
    )
    sample_file = tmp_path / 'benchmark.md'
    sample_file.write_text(
        '# Benchmark\n\n'
        'O benchmark mede recall, latencia e cobertura de citacoes para comparar retrieval.\n',
        encoding='utf-8',
    )
    dataset_path = tmp_path / 'dataset.json'
    dataset_path.write_text(
        json.dumps(
            {
                'dataset_name': 'cli-dataset',
                'samples': [
                    {
                        'sample_id': 'q-1',
                        'question': 'O que o benchmark mede?',
                        'expected_note_id': 'benchmark',
                        'expected_terms': ['recall', 'latencia'],
                    }
                ],
            }
        ),
        encoding='utf-8',
    )

    monkeypatch.setattr('free_plaud.benchmark.cli.get_settings', lambda: settings)

    result = runner.invoke(
        app,
        [
            'benchmark',
            'run',
            str(sample_file),
            '--dataset',
            str(dataset_path),
            '--strategy',
            'lexical',
            '--top-k',
            '3',
            '--chunk-size',
            '120',
            '--overlap',
            '30',
            '--export',
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload['dataset_name'] == 'cli-dataset'
    assert payload['metrics']['recall_at_3'] == 1.0
    assert Path(payload['json_report_path']).exists()
    assert Path(payload['csv_report_path']).exists()
    connection = connect_sqlite(settings.sqlite_path)
    row = connection.execute('SELECT COUNT(*) AS total FROM benchmark_runs').fetchone()
    assert row['total'] == 1
