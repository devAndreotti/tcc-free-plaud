import csv
import json
from pathlib import Path
from types import SimpleNamespace

from typer.testing import CliRunner

from escolio.app.config import Settings
from escolio.benchmark.datasets import (
    BenchmarkDataset,
    BenchmarkSample,
    load_benchmark_dataset,
    load_benchmark_suite,
)
from escolio.benchmark.metrics import (
    mean_reciprocal_rank,
    ndcg_at_k,
    recall_at_k_from_ranks,
)
from escolio.benchmark.reports import (
    export_benchmark_comparison_csv,
    export_benchmark_comparison_json,
    export_benchmark_csv,
    export_benchmark_json,
)
from escolio.benchmark.runners import (
    BenchmarkSettingsSnapshot,
    compare_benchmark_suite,
    run_benchmark,
)
from escolio.benchmark.service import run_benchmark_compare
from escolio.cli import app
from escolio.notes.schemas import Note
from escolio.retrieval.indexer import index_note
from escolio.storage.sqlite import connect_sqlite, init_sqlite
from escolio.storage.vector import LocalVectorStore

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


def test_run_benchmark_reports_ndcg(tmp_path: Path) -> None:
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

    result = run_benchmark(note, dataset, strategy='lexical', top_k=5, chunk_size=120, overlap=30)

    ranks = [query.relevant_rank for query in result.queries]
    assert result.metrics['ndcg_at_10'] == ndcg_at_k(ranks, 10)
    assert {'ndcg_at_3', 'ndcg_at_5', 'ndcg_at_10'} <= set(result.metrics)


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
    connection = init_sqlite(tmp_path / 'escolio.sqlite3')

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
        sqlite_path=tmp_path / 'data' / 'results' / 'escolio.sqlite3',
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

    monkeypatch.setattr('escolio.benchmark.cli.get_settings', lambda: settings)

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
        sqlite_path=tmp_path / 'data' / 'results' / 'escolio.sqlite3',
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

    monkeypatch.setattr('escolio.benchmark.cli.get_settings', lambda: settings)
    monkeypatch.setattr('escolio.benchmark.cli.get_embedder', lambda model_name, **kwargs: FakeEmbedder())

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
        sqlite_path=tmp_path / 'data' / 'results' / 'escolio.sqlite3',
        vector_store_dir=tmp_path / 'data' / 'results' / 'vector_store',
        embedding_model='fake-hash',
    )
    sample_file = tmp_path / 'benchmark.md'
    sample_file.write_text('# Benchmark\n\nTexto de benchmark.\n', encoding='utf-8')
    dataset_path = tmp_path / 'dataset.json'
    dataset_path.write_text(json.dumps({'dataset_name': 'fake-hash-dataset', 'samples': []}), encoding='utf-8')

    def fail_init_sqlite(_path):
        raise AssertionError('benchmark nao deve abrir SQLite com fake-hash')

    monkeypatch.setattr('escolio.benchmark.cli.get_settings', lambda: settings)
    monkeypatch.setattr('escolio.benchmark.cli.init_sqlite', fail_init_sqlite)

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
    assert 'uv run escolio config preset apply cpu_rapido' in combined_output
    assert 'Traceback' not in combined_output


def test_benchmark_run_cli_closes_sqlite_connection(monkeypatch, tmp_path: Path) -> None:
    settings = Settings(
        workspace_dir=tmp_path,
        data_dir=tmp_path / 'data',
        notes_dir=tmp_path / 'data' / 'corpus' / 'notes',
        datasets_dir=tmp_path / 'data' / 'datasets',
        results_dir=tmp_path / 'data' / 'results',
        sqlite_path=tmp_path / 'data' / 'results' / 'escolio.sqlite3',
        vector_store_dir=tmp_path / 'data' / 'results' / 'vector_store',
    )
    sample_file = tmp_path / 'benchmark.md'
    sample_file.write_text('# Benchmark\n\nTexto de benchmark.\n', encoding='utf-8')
    dataset_path = tmp_path / 'dataset.json'
    dataset_path.write_text(json.dumps({'dataset_name': 'close-dataset', 'samples': []}), encoding='utf-8')
    connection = FakeConnection()

    monkeypatch.setattr('escolio.benchmark.cli.get_settings', lambda: settings)
    monkeypatch.setattr('escolio.benchmark.cli.init_sqlite', lambda path: connection)
    monkeypatch.setattr(
        'escolio.benchmark.cli.run_benchmark',
        lambda *args, **kwargs: SimpleNamespace(
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
    connection = init_sqlite(tmp_path / 'results' / 'escolio.sqlite3')
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


def test_compare_benchmark_suite_measures_whole_corpus_and_abstention(tmp_path: Path) -> None:
    documents = {
        'kafka': '# Kafka\n\nO Apache Kafka foi adotado como broker padrao da plataforma de eventos.\n',
        'redis': '# Redis\n\nO timeout do Redis em staging esta configurado para trinta segundos.\n',
    }
    cases = []
    for name, text in documents.items():
        (tmp_path / f'{name}.md').write_text(text, encoding='utf-8')
        (tmp_path / f'{name}.json').write_text(
            json.dumps(
                {
                    'dataset_name': name,
                    'samples': [
                        {
                            'sample_id': f'{name}-1',
                            'question': f'Qual a configuracao do {name}?',
                            'expected_note_id': name,
                            'expected_terms': [name.capitalize()],
                        }
                    ],
                }
            ),
            encoding='utf-8',
        )
        cases.append({'case_id': name, 'document_path': f'{name}.md', 'dataset_path': f'{name}.json'})
    (tmp_path / 'negativas.json').write_text(
        json.dumps(
            {
                'dataset_name': 'negativas',
                'samples': [{'sample_id': 'neg-1', 'question': 'Qual a receita anual do refeitorio?', 'category': 'negativa'}],
            }
        ),
        encoding='utf-8',
    )
    suite_path = tmp_path / 'suite.json'
    suite_path.write_text(
        json.dumps({'suite_name': 'corpus-suite', 'cases': cases, 'negative_dataset_path': 'negativas.json'}),
        encoding='utf-8',
    )

    result = compare_benchmark_suite(
        load_benchmark_suite(suite_path),
        workspace_dir=tmp_path,
        connection=init_sqlite(tmp_path / 'results' / 'benchmark.sqlite3'),
        top_k=3,
        chunk_size=200,
        overlap=20,
        vector_store=LocalVectorStore(tmp_path / 'results' / 'vector_store', collection_name='corpus_suite'),
        embedder=FakeEmbedder(),
    )

    assert result.corpus is not None
    assert (result.corpus.note_count, result.corpus.positive_count, result.corpus.negative_count) == (2, 2, 1)
    lexical = result.corpus.summaries['lexical']
    assert lexical.query_count == 2  # as negativas não entram no MRR
    assert lexical.mrr == 1.0
    assert lexical.mrr_ci == [1.0, 1.0]
    assert lexical.abstention is not None and lexical.abstention['support'] == 3.0
    rows = {row.sample_id: row for row in result.corpus.queries['lexical']}
    # Busca sem filtro por nota: o hit relevante tem de ser da nota do caso.
    assert rows['redis-1'].retrieved[0]['note_id'] == 'redis'
    assert rows['neg-1'].category == 'negativa'
    assert rows['neg-1'].answered is False


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
        sqlite_path=tmp_path / 'data' / 'results' / 'escolio.sqlite3',
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
    # A suite roda num banco próprio: o corpus do usuário não ganha as notas dela.
    corpus = init_sqlite(settings.sqlite_path)
    try:
        assert corpus.execute('SELECT COUNT(*) FROM notes').fetchone()[0] == 0
    finally:
        corpus.close()
    assert (settings.results_dir / 'benchmark_compare' / 'service-suite' / 'benchmark.sqlite3').exists()


def test_run_benchmark_compare_service_emits_rerank_blocks_when_configured(monkeypatch, tmp_path: Path) -> None:
    """Com `rerank_model`, o payload da UI traz baseline, reranker e cobertura; sem ele, nada disso."""
    from benchmark_compare_fakes import FakeReranker

    import escolio.benchmark.service as service_module

    sample_file = tmp_path / 'benchmark.md'
    sample_file.write_text(
        '# Benchmark\n\nO benchmark mede recall, latencia e cobertura de citacoes para comparar retrieval.\n'
        'A recuperacao vetorial usa embeddings persistidos no ChromaDB local.\n',
        encoding='utf-8',
    )
    (tmp_path / 'dataset.json').write_text(
        json.dumps(
            {
                'dataset_name': 'rerank-dataset',
                'samples': [
                    {
                        'sample_id': 'unica-01',
                        'question': 'O que o benchmark mede?',
                        'expected_note_id': 'benchmark',
                        'expected_terms': ['recall', 'latencia'],
                    }
                ],
            }
        ),
        encoding='utf-8',
    )
    (tmp_path / 'suite.json').write_text(
        json.dumps(
            {
                'suite_name': 'rerank-suite',
                'cases': [{'case_id': 'case-1', 'document_path': 'benchmark.md', 'dataset_path': 'dataset.json'}],
            }
        ),
        encoding='utf-8',
    )

    def make_settings(rerank_model: str) -> Settings:
        return Settings(
            workspace_dir=tmp_path,
            data_dir=tmp_path / 'data',
            notes_dir=tmp_path / 'data' / 'corpus' / 'notes',
            datasets_dir=tmp_path / 'data' / 'datasets',
            results_dir=tmp_path / 'data' / 'results',
            sqlite_path=tmp_path / 'data' / 'results' / 'escolio.sqlite3',
            vector_store_dir=tmp_path / 'data' / 'results' / 'vector_store',
            embedding_model='fake-hash',
            embedding_device='cpu',
            retrieval_top_k=4,
            default_chunk_size=120,
            default_chunk_overlap=30,
            rerank_model=rerank_model,
        )

    sem = run_benchmark_compare('suite.json', runtime=FakeRuntime(), settings=make_settings(''))
    assert 'reranked' not in sem and 'coverage' not in sem and 'baseline_ci' not in sem

    monkeypatch.setattr(service_module, 'reranker_from_settings', lambda settings: FakeReranker())
    com = run_benchmark_compare('suite.json', runtime=FakeRuntime(), settings=make_settings('fake-reranker'))
    assert com['reranked']['model'] == 'fake-reranker'
    assert set(com['reranked']['summaries']) == {'lexical', 'vector', 'hybrid'}
    assert 'baseline_ci' in com and 'coverage' in com
    # O mesmo conteúdo é gravado no JSON exportado, que é o que a UI e o `faithfulness --mesclar-em` leem.
    exported = json.loads(Path(com['json_report_path']).read_text(encoding='utf-8'))
    assert exported['reranked']['model'] == 'fake-reranker'



def test_benchmark_compare_cli_executes_suite_and_exports_reports(monkeypatch, tmp_path: Path) -> None:
    settings = Settings(
        workspace_dir=tmp_path,
        data_dir=tmp_path / 'data',
        notes_dir=tmp_path / 'data' / 'corpus' / 'notes',
        datasets_dir=tmp_path / 'data' / 'datasets',
        results_dir=tmp_path / 'data' / 'results',
        sqlite_path=tmp_path / 'data' / 'results' / 'escolio.sqlite3',
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

    monkeypatch.setattr('escolio.benchmark.cli.get_settings', lambda: settings)
    monkeypatch.setattr('escolio.benchmark.cli.get_embedder', lambda model_name, **kwargs: FakeEmbedder())

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
        sqlite_path=tmp_path / 'data' / 'results' / 'escolio.sqlite3',
        vector_store_dir=tmp_path / 'data' / 'results' / 'vector_store',
        embedding_model='sentence-transformer:fake-hash',
    )
    suite_path = tmp_path / 'suite.json'
    suite_path.write_text(
        json.dumps({'suite_name': 'close-suite', 'cases': []}),
        encoding='utf-8',
    )
    connection = FakeConnection()

    monkeypatch.setattr('escolio.benchmark.cli.get_settings', lambda: settings)
    monkeypatch.setattr('escolio.benchmark.cli.init_sqlite', lambda path: connection)
    monkeypatch.setattr('escolio.benchmark.cli.LocalVectorStore', lambda *args, **kwargs: object())
    monkeypatch.setattr('escolio.benchmark.cli.get_embedder', lambda *args, **kwargs: FakeEmbedder())
    monkeypatch.setattr(
        'escolio.benchmark.cli.compare_benchmark_suite',
        lambda *args, **kwargs: SimpleNamespace(
            comparison_id='cmp-close',
            model_dump=lambda mode='json': {'comparison_id': 'cmp-close'},
        ),
    )

    result = runner.invoke(app, ['benchmark', 'compare', '--suite', str(suite_path)])

    assert result.exit_code == 0
    assert connection.closed is True
