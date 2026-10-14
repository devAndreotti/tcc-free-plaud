from pathlib import Path

from escolio.benchmark.datasets import load_benchmark_dataset, load_benchmark_suite
from escolio.benchmark.runners import _is_relevant
from escolio.ingest.loaders import load_document
from escolio.notes.structurer import structure_document
from escolio.retrieval.indexer import index_note

REPO_ROOT = Path(__file__).resolve().parents[2]
SUITE_PATH = REPO_ROOT / 'data' / 'datasets' / 'manual_validation' / 'suite.json'


def test_real_benchmark_datasets_load_and_keep_consistent_note_scope() -> None:
    suite = load_benchmark_suite(SUITE_PATH)
    assert suite.cases, 'Esperava casos reais em data/datasets/manual_validation/suite.json.'

    for case in suite.cases:
        dataset = load_benchmark_dataset(REPO_ROOT / case.dataset_path)

        assert dataset.dataset_name
        assert len(dataset.samples) >= 3

        sample_ids = [sample.sample_id for sample in dataset.samples]
        assert len(sample_ids) == len(set(sample_ids))

        note_ids = {sample.expected_note_id for sample in dataset.samples}
        assert len(note_ids) == 1
        assert None not in note_ids

        # Toda pergunta precisa de um chunk (800/120) com todos os termos esperados; senão o
        # benchmark mede um alvo inalcançável.
        note = structure_document(load_document(REPO_ROOT / case.document_path))
        assert note_ids == {note.note_id}
        chunks = index_note(note, chunk_size=800, overlap=120)
        for sample in dataset.samples:
            assert sample.question.strip()
            assert sample.expected_terms
            assert any(_is_relevant(sample, chunk) for chunk in chunks), sample.sample_id


def test_real_negative_dataset_has_only_unanswerable_questions() -> None:
    suite = load_benchmark_suite(SUITE_PATH)
    assert suite.negative_dataset_path is not None

    negatives = load_benchmark_dataset(REPO_ROOT / suite.negative_dataset_path)
    assert len(negatives.samples) >= 5
    for sample in negatives.samples:
        assert sample.category == 'negativa'
        assert sample.expected_note_id is None
        assert not sample.expected_terms
