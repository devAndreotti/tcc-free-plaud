import csv
import json
from pathlib import Path
from types import SimpleNamespace

from typer.testing import CliRunner

from free_plaud.app.config import Settings
from free_plaud.benchmark.datasets import (
    BenchmarkDataset,
    BenchmarkSample,
    load_benchmark_dataset,
    load_benchmark_suite,
)
from free_plaud.benchmark.metrics import mean_reciprocal_rank, recall_at_k_from_ranks
from free_plaud.benchmark.reports import (
    export_benchmark_comparison_csv,
    export_benchmark_comparison_json,
    export_benchmark_csv,
    export_benchmark_json,
)
from free_plaud.benchmark.runners import BenchmarkSettingsSnapshot, compare_benchmark_suite, run_benchmark
from free_plaud.benchmark.service import run_benchmark_compare
from free_plaud.cli import app
from free_plaud.notes.schemas import Note
from free_plaud.retrieval.indexer import index_note
from free_plaud.storage.vector import LocalVectorStore
from free_plaud.storage.sqlite import connect_sqlite, init_sqlite

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


class FakeRuntime:
    def get_embedder(self) -> FakeEmbedder:
        return FakeEmbedder()


class FakeConnection:
    closed = False

    def close(self) -> None:
        self.closed = True


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


def test_load_benchmark_suite_from_json_object(tmp_path: Path) -> None:
    suite_path = tmp_path / 'suite.json'
    suite_path.write_text(
        json.dumps(
            {
                'suite_name': 'manual-validation',
                'cases': [
                    {
                        'case_id': 'case-1',
                        'document_path': 'samples/doc-1.md',
                        'dataset_path': 'data/datasets/doc-1.json',
                    }
                ],
            }
        ),
        encoding='utf-8',
    )

    suite = load_benchmark_suite(suite_path)

    assert suite.suite_name == 'manual-validation'
    assert suite.cases[0].case_id == 'case-1'
    assert suite.cases[0].document_path == Path('samples/doc-1.md')
    assert suite.cases[0].dataset_path == Path('data/datasets/doc-1.json')


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


def test_run_benchmark_supports_hybrid_strategy(tmp_path: Path) -> None:
    note = _build_note(tmp_path)
    dataset = BenchmarkDataset(
        dataset_name='rag-hybrid',
        samples=[
            BenchmarkSample(
                sample_id='q-1',
                question='O que o benchmark mede?',
                expected_note_id=note.note_id,
                expected_terms=['recall', 'latencia'],
            )
        ],
    )
    vector_store = LocalVectorStore(tmp_path / 'results' / 'vector_store', collection_name='hybrid_run')

    result = run_benchmark(
        note,
        dataset,
        strategy='hybrid',
        top_k=3,
        chunk_size=120,
        overlap=30,
        run_name='hybrid-baseline',
        vector_store=vector_store,
        embedder=FakeEmbedder(),
        hybrid_rank_constant=40,
        hybrid_lexical_weight=1.25,
        hybrid_vector_weight=1.0,
        hybrid_lexical_pool=6,
        hybrid_vector_pool=12,
    )

    assert result.retrieval_strategy == 'hybrid'
    assert result.metrics['recall_at_3'] == 1.0
    assert result.hybrid_config == {
        'rank_constant': 40,
        'lexical_weight': 1.25,
        'vector_weight': 1.0,
        'lexical_pool': 6,
        'vector_pool': 12,
    }


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


def test_benchmark_run_cli_accepts_hybrid_knobs(monkeypatch, tmp_path: Path) -> None:
    settings = Settings(
        workspace_dir=tmp_path,
        data_dir=tmp_path / 'data',
        notes_dir=tmp_path / 'data' / 'corpus' / 'notes',
        datasets_dir=tmp_path / 'data' / 'datasets',
        results_dir=tmp_path / 'data' / 'results',
        sqlite_path=tmp_path / 'data' / 'results' / 'free_plaud.sqlite3',
        vector_store_dir=tmp_path / 'data' / 'results' / 'vector_store',
        embedding_model='sentence-transformer:fake-hash',
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
                'dataset_name': 'cli-hybrid-dataset',
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
    monkeypatch.setattr('free_plaud.benchmark.cli.get_embedder', lambda model_name, **kwargs: FakeEmbedder())

    result = runner.invoke(
        app,
        [
            'benchmark',
            'run',
            str(sample_file),
            '--dataset',
            str(dataset_path),
            '--strategy',
            'hybrid',
            '--top-k',
            '3',
            '--chunk-size',
            '120',
            '--overlap',
            '30',
            '--hybrid-rank-constant',
            '40',
            '--hybrid-lexical-weight',
            '1.25',
            '--hybrid-vector-weight',
            '1.0',
            '--hybrid-lexical-pool',
            '6',
            '--hybrid-vector-pool',
            '12',
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload['retrieval_strategy'] == 'hybrid'
    assert payload['hybrid_config'] == {
        'rank_constant': 40,
        'lexical_weight': 1.25,
        'vector_weight': 1.0,
        'lexical_pool': 6,
        'vector_pool': 12,
    }


def test_benchmark_run_cli_rejects_fake_hash_with_actionable_error(monkeypatch, tmp_path: Path) -> None:
    settings = Settings(
        workspace_dir=tmp_path,
        data_dir=tmp_path / 'data',
        notes_dir=tmp_path / 'data' / 'corpus' / 'notes',
        datasets_dir=tmp_path / 'data' / 'datasets',
        results_dir=tmp_path / 'data' / 'results',
        sqlite_path=tmp_path / 'data' / 'results' / 'free_plaud.sqlite3',
        vector_store_dir=tmp_path / 'data' / 'results' / 'vector_store',
        embedding_model='fake-hash',
    )
    sample_file = tmp_path / 'benchmark.md'
    sample_file.write_text('# Benchmark\n\nTexto de benchmark.\n', encoding='utf-8')
    dataset_path = tmp_path / 'dataset.json'
    dataset_path.write_text(json.dumps({'dataset_name': 'fake-hash-dataset', 'samples': []}), encoding='utf-8')

    def fail_init_sqlite(_path):  # noqa: ANN001, ANN202
        raise AssertionError('benchmark nao deve abrir SQLite com fake-hash')

    monkeypatch.setattr('free_plaud.benchmark.cli.get_settings', lambda: settings)
    monkeypatch.setattr('free_plaud.benchmark.cli.init_sqlite', fail_init_sqlite)

    result = runner.invoke(
        app,
        [
            'benchmark',
            'run',
            str(sample_file),
            '--dataset',
            str(dataset_path),
            '--strategy',
            'hybrid',
        ],
    )

    combined_output = f'{result.stdout}\n{result.stderr}\n{result.exception or ""}'
    assert result.exit_code == 1
    assert 'fake-hash e modelo de teste' in combined_output
    assert 'uv run free-plaud config preset apply cpu_rapido' in combined_output
    assert 'Traceback' not in combined_output


def test_benchmark_run_cli_closes_sqlite_connection(monkeypatch, tmp_path: Path) -> None:
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
    sample_file.write_text('# Benchmark\n\nTexto de benchmark.\n', encoding='utf-8')
    dataset_path = tmp_path / 'dataset.json'
    dataset_path.write_text(json.dumps({'dataset_name': 'close-dataset', 'samples': []}), encoding='utf-8')
    connection = FakeConnection()

    monkeypatch.setattr('free_plaud.benchmark.cli.get_settings', lambda: settings)
    monkeypatch.setattr('free_plaud.benchmark.cli.init_sqlite', lambda path: connection)  # noqa: ARG005
    monkeypatch.setattr(
        'free_plaud.benchmark.cli.run_benchmark',
        lambda *args, **kwargs: SimpleNamespace(  # noqa: ARG005
            benchmark_run_id='run-close',
            model_dump=lambda mode='json': {'benchmark_run_id': 'run-close'},
        ),
    )

    result = runner.invoke(
        app,
        [
            'benchmark',
            'run',
            str(sample_file),
            '--dataset',
            str(dataset_path),
        ],
    )

    assert result.exit_code == 0
    assert connection.closed is True


def test_compare_benchmark_suite_runs_lexical_vector_and_hybrid_strategies(tmp_path: Path) -> None:
    sample_file = tmp_path / 'benchmark.md'
    sample_file.write_text(
        '# Benchmark\n\n'
        'O benchmark mede recall, latencia e cobertura de citacoes para comparar retrieval.\n'
        'A recuperacao vetorial usa embeddings persistidos no ChromaDB local.\n',
        encoding='utf-8',
    )
    dataset_path = tmp_path / 'dataset.json'
    dataset_path.write_text(
        json.dumps(
            {
                'dataset_name': 'compare-dataset',
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
    suite_path = tmp_path / 'suite.json'
    suite_path.write_text(
        json.dumps(
            {
                'suite_name': 'compare-suite',
                'cases': [
                    {
                        'case_id': 'case-1',
                        'document_path': sample_file.name,
                        'dataset_path': dataset_path.name,
                    }
                ],
            }
        ),
        encoding='utf-8',
    )
    suite = load_benchmark_suite(suite_path)
    connection = init_sqlite(tmp_path / 'results' / 'free_plaud.sqlite3')
    vector_store = LocalVectorStore(tmp_path / 'results' / 'vector_store', collection_name='compare_suite')

    result = compare_benchmark_suite(
        suite,
        workspace_dir=tmp_path,
        connection=connection,
        top_k=3,
        chunk_size=120,
        overlap=30,
        vector_store=vector_store,
        embedder=FakeEmbedder(),
        hybrid_rank_constant=40,
        hybrid_lexical_weight=1.25,
        hybrid_vector_weight=1.0,
        hybrid_lexical_pool=6,
        hybrid_vector_pool=12,
    )

    assert result.suite_name == 'compare-suite'
    assert result.summaries['lexical'].case_count == 1
    assert result.summaries['vector'].case_count == 1
    assert result.summaries['hybrid'].case_count == 1
    assert result.summaries['lexical'].query_count == 1
    assert result.summaries['vector'].query_count == 1
    assert result.summaries['hybrid'].query_count == 1
    assert result.hybrid_config == {
        'rank_constant': 40,
        'lexical_weight': 1.25,
        'vector_weight': 1.0,
        'lexical_pool': 6,
        'vector_pool': 12,
    }
    assert result.cases[0].lexical.metrics['recall_at_3'] == 1.0
    assert result.cases[0].vector.metrics['recall_at_3'] == 1.0
    assert result.cases[0].hybrid.metrics['recall_at_3'] == 1.0


def test_benchmark_comparison_exports_settings_snapshot(tmp_path: Path) -> None:
    sample_file = tmp_path / 'benchmark.md'
    sample_file.write_text(
        '# Benchmark\n\n'
        'O benchmark mede recall, latencia e cobertura de citacoes para comparar retrieval.\n'
        'A recuperacao vetorial usa embeddings persistidos no ChromaDB local.\n',
        encoding='utf-8',
    )
    dataset_path = tmp_path / 'dataset.json'
    dataset_path.write_text(
        json.dumps(
            {
                'dataset_name': 'snapshot-dataset',
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
    suite_path = tmp_path / 'suite.json'
    suite_path.write_text(
        json.dumps(
            {
                'suite_name': 'snapshot-suite',
                'cases': [
                    {
                        'case_id': 'case-1',
                        'document_path': sample_file.name,
                        'dataset_path': dataset_path.name,
                    }
                ],
            }
        ),
        encoding='utf-8',
    )
    snapshot = BenchmarkSettingsSnapshot(
        embedding_model='fake-hash',
        embedding_device='cpu',
        default_ask_strategy='hybrid',
        retrieval_top_k=4,
        default_chunk_size=120,
        default_chunk_overlap=30,
        answer_provider='extractive',
    )

    result = compare_benchmark_suite(
        load_benchmark_suite(suite_path),
        workspace_dir=tmp_path,
        top_k=4,
        chunk_size=120,
        overlap=30,
        vector_store=LocalVectorStore(tmp_path / 'results' / 'vector_store', collection_name='snapshot_suite'),
        embedder=FakeEmbedder(),
        settings_snapshot=snapshot,
    )
    json_path = export_benchmark_comparison_json(result, tmp_path / 'comparison.json')
    csv_path = export_benchmark_comparison_csv(result, tmp_path / 'comparison.csv')

    payload = json.loads(json_path.read_text(encoding='utf-8'))
    with csv_path.open(encoding='utf-8', newline='') as handle:
        csv_rows = list(csv.DictReader(handle))

    assert payload['settings_snapshot']['embedding_model'] == 'fake-hash'
    assert payload['settings_snapshot']['retrieval_top_k'] == 4
    assert payload['summaries']['hybrid']['mrr'] == 1.0
    assert csv_rows[0]['embedding_device'] == 'cpu'
    assert csv_rows[0]['answer_provider'] == 'extractive'


def test_run_benchmark_compare_service_exports_structured_payload(tmp_path: Path) -> None:
    sample_file = tmp_path / 'benchmark.md'
    sample_file.write_text(
        '# Benchmark\n\n'
        'O benchmark mede recall, latencia e cobertura de citacoes para comparar retrieval.\n'
        'A recuperacao vetorial usa embeddings persistidos no ChromaDB local.\n',
        encoding='utf-8',
    )
    dataset_path = tmp_path / 'dataset.json'
    dataset_path.write_text(
        json.dumps(
            {
                'dataset_name': 'service-dataset',
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
    suite_path = tmp_path / 'suite.json'
    suite_path.write_text(
        json.dumps(
            {
                'suite_name': 'service-suite',
                'cases': [
                    {
                        'case_id': 'case-1',
                        'document_path': sample_file.name,
                        'dataset_path': dataset_path.name,
                    }
                ],
            }
        ),
        encoding='utf-8',
    )
    settings = Settings(
        workspace_dir=tmp_path,
        data_dir=tmp_path / 'data',
        notes_dir=tmp_path / 'data' / 'corpus' / 'notes',
        datasets_dir=tmp_path / 'data' / 'datasets',
        results_dir=tmp_path / 'data' / 'results',
        sqlite_path=tmp_path / 'data' / 'results' / 'free_plaud.sqlite3',
        vector_store_dir=tmp_path / 'data' / 'results' / 'vector_store',
        embedding_model='fake-hash',
        embedding_device='cpu',
        retrieval_top_k=4,
        default_chunk_size=120,
        default_chunk_overlap=30,
    )

    payload = run_benchmark_compare('suite.json', runtime=FakeRuntime(), settings=settings)

    assert payload['ok'] is True
    assert payload['suite_name'] == 'service-suite'
    assert payload['summaries']['hybrid']['recall_at_3'] == 1.0
    assert payload['settings_snapshot']['embedding_model'] == 'fake-hash'
    assert Path(payload['json_report_path']).exists()
    assert Path(payload['csv_report_path']).exists()


def test_benchmark_compare_cli_executes_suite_and_exports_reports(monkeypatch, tmp_path: Path) -> None:
    settings = Settings(
        workspace_dir=tmp_path,
        data_dir=tmp_path / 'data',
        notes_dir=tmp_path / 'data' / 'corpus' / 'notes',
        datasets_dir=tmp_path / 'data' / 'datasets',
        results_dir=tmp_path / 'data' / 'results',
        sqlite_path=tmp_path / 'data' / 'results' / 'free_plaud.sqlite3',
        vector_store_dir=tmp_path / 'data' / 'results' / 'vector_store',
        vector_collection_name='compare_cli',
        embedding_model='fake-hash',
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
                'dataset_name': 'cli-compare-dataset',
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
    suite_path = tmp_path / 'suite.json'
    suite_path.write_text(
        json.dumps(
            {
                'suite_name': 'cli-compare-suite',
                'cases': [
                    {
                        'case_id': 'case-1',
                        'document_path': sample_file.name,
                        'dataset_path': dataset_path.name,
                    }
                ],
            }
        ),
        encoding='utf-8',
    )

    monkeypatch.setattr('free_plaud.benchmark.cli.get_settings', lambda: settings)
    monkeypatch.setattr('free_plaud.benchmark.cli.get_embedder', lambda model_name, **kwargs: FakeEmbedder())

    result = runner.invoke(
        app,
        [
            'benchmark',
            'compare',
            '--suite',
            str(suite_path),
            '--top-k',
            '3',
            '--chunk-size',
            '120',
            '--overlap',
            '30',
            '--embedding-model',
            'sentence-transformer:fake-hash',
            '--hybrid-rank-constant',
            '40',
            '--hybrid-lexical-weight',
            '1.25',
            '--hybrid-vector-weight',
            '1.0',
            '--hybrid-lexical-pool',
            '6',
            '--hybrid-vector-pool',
            '12',
            '--export',
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload['suite_name'] == 'cli-compare-suite'
    assert payload['summaries']['lexical']['recall_at_3'] == 1.0
    assert payload['summaries']['vector']['recall_at_3'] == 1.0
    assert payload['summaries']['hybrid']['recall_at_3'] == 1.0
    assert payload['hybrid_config'] == {
        'rank_constant': 40,
        'lexical_weight': 1.25,
        'vector_weight': 1.0,
        'lexical_pool': 6,
        'vector_pool': 12,
    }
    assert Path(payload['json_report_path']).exists()
    assert Path(payload['csv_report_path']).exists()
    assert payload['embedding_model'] == 'fake-hash'


def test_benchmark_compare_cli_closes_sqlite_connection(monkeypatch, tmp_path: Path) -> None:
    settings = Settings(
        workspace_dir=tmp_path,
        data_dir=tmp_path / 'data',
        notes_dir=tmp_path / 'data' / 'corpus' / 'notes',
        datasets_dir=tmp_path / 'data' / 'datasets',
        results_dir=tmp_path / 'data' / 'results',
        sqlite_path=tmp_path / 'data' / 'results' / 'free_plaud.sqlite3',
        vector_store_dir=tmp_path / 'data' / 'results' / 'vector_store',
        embedding_model='sentence-transformer:fake-hash',
    )
    suite_path = tmp_path / 'suite.json'
    suite_path.write_text(
        json.dumps({'suite_name': 'close-suite', 'cases': []}),
        encoding='utf-8',
    )
    connection = FakeConnection()

    monkeypatch.setattr('free_plaud.benchmark.cli.get_settings', lambda: settings)
    monkeypatch.setattr('free_plaud.benchmark.cli.init_sqlite', lambda path: connection)  # noqa: ARG005
    monkeypatch.setattr('free_plaud.benchmark.cli.LocalVectorStore', lambda *args, **kwargs: object())  # noqa: ARG005
    monkeypatch.setattr('free_plaud.benchmark.cli.get_embedder', lambda *args, **kwargs: FakeEmbedder())  # noqa: ARG005
    monkeypatch.setattr(
        'free_plaud.benchmark.cli.compare_benchmark_suite',
        lambda *args, **kwargs: SimpleNamespace(  # noqa: ARG005
            comparison_id='cmp-close',
            model_dump=lambda mode='json': {'comparison_id': 'cmp-close'},
        ),
    )

    result = runner.invoke(app, ['benchmark', 'compare', '--suite', str(suite_path)])

    assert result.exit_code == 0
    assert connection.closed is True
