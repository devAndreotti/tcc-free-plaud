import json
from pathlib import Path

from typer.testing import CliRunner

from free_plaud.app.config import Settings
from free_plaud.benchmark.datasets import BenchmarkDataset, BenchmarkSample
from free_plaud.benchmark.grounded import evaluate_grounded_answers
from free_plaud.cli import app
from free_plaud.notes.schemas import Note

runner = CliRunner()


def _note(tmp_path: Path) -> Note:
    text = (
        'O benchmark mede recall, latencia e cobertura de citacoes para comparar retrieval. '
        'A recuperacao vetorial usa embeddings persistidos no ChromaDB local. '
        'O SQLite registra execucoes, metricas e consultas avaliadas.'
    )
    return Note(
        note_id='grounded-note',
        note_version=1,
        source_type='md',
        source_path=tmp_path / 'nota.md',
        source_name='nota.md',
        title='Nota de benchmark',
        summary='Resumo da nota.',
        topics=[],
        tasks=[],
        tags=['md'],
        raw_text=text,
        normalized_text=text,
        structured_markdown=f'# Nota de benchmark\n\n{text}\n',
        content_hash='a' * 64,
    )


def test_grounded_eval_answers_direct_and_abstains_on_negative(tmp_path: Path) -> None:
    note = _note(tmp_path)
    dataset = BenchmarkDataset(
        dataset_name='grounded-suite',
        samples=[
            BenchmarkSample(sample_id='d1', question='O que o benchmark mede?', category='direta'),
            BenchmarkSample(sample_id='n1', question='Qual a capital da Mongolia?', category='negativa'),
        ],
    )

    report = evaluate_grounded_answers(note, dataset, strategy='lexical', top_k=3)

    by_id = {result.sample_id: result for result in report.results}

    # Pergunta direta: responde e a resposta está ancorada nas citações.
    assert by_id['d1'].answered is True
    assert by_id['d1'].groundedness is not None
    assert by_id['d1'].groundedness > 0.5
    assert by_id['d1'].decision_correct is True

    # Pergunta negativa: abstém-se corretamente, sem groundedness.
    assert by_id['n1'].answered is False
    assert by_id['n1'].expected_abstain is True
    assert by_id['n1'].decision_correct is True
    assert by_id['n1'].groundedness is None

    # Agregados.
    assert report.sample_count == 2
    assert report.answered_count == 1
    assert 0.0 < report.mean_groundedness <= 1.0
    assert report.abstention['accuracy'] == 1.0


def test_grounded_eval_handles_uncategorized_samples(tmp_path: Path) -> None:
    note = _note(tmp_path)
    dataset = BenchmarkDataset(
        dataset_name='grounded-uncategorized',
        samples=[BenchmarkSample(sample_id='u1', question='O que o benchmark mede?')],
    )

    report = evaluate_grounded_answers(note, dataset, strategy='lexical', top_k=3)

    # Sem categoria => não deveria abster-se; ao responder, a decisão está correta.
    assert report.results[0].expected_abstain is False
    assert report.results[0].answered is True
    assert report.results[0].decision_correct is True
    assert report.abstention['support'] == 1.0


def test_answer_eval_cli_reports_groundedness_and_abstention(monkeypatch, tmp_path: Path) -> None:
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
                'dataset_name': 'cli-grounded',
                'samples': [
                    {'sample_id': 'd1', 'question': 'O que o benchmark mede?', 'category': 'direta'},
                    {'sample_id': 'n1', 'question': 'Qual a capital da Mongolia?', 'category': 'negativa'},
                ],
            }
        ),
        encoding='utf-8',
    )

    monkeypatch.setattr('free_plaud.benchmark.cli.get_settings', lambda: settings)

    result = runner.invoke(
        app,
        ['benchmark', 'answer-eval', str(sample_file), '--dataset', str(dataset_path), '--strategy', 'lexical'],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload['sample_count'] == 2
    assert payload['answered_count'] == 1
    assert payload['abstention']['accuracy'] == 1.0
    assert payload['mean_groundedness'] > 0.0
