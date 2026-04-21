from pathlib import Path

from free_plaud.benchmark.datasets import load_benchmark_dataset


def test_real_benchmark_datasets_load_and_keep_consistent_note_scope() -> None:
    datasets_dir = Path(__file__).resolve().parents[2] / 'data' / 'datasets' / 'manual_validation'
    dataset_paths = sorted(path for path in datasets_dir.glob('*.json') if path.name != 'suite.json')

    assert dataset_paths, 'Esperava datasets reais em data/datasets/manual_validation.'

    for dataset_path in dataset_paths:
        dataset = load_benchmark_dataset(dataset_path)

        assert dataset.dataset_name
        assert len(dataset.samples) >= 3

        sample_ids = [sample.sample_id for sample in dataset.samples]
        assert len(sample_ids) == len(set(sample_ids))

        note_ids = {sample.expected_note_id for sample in dataset.samples}
        assert len(note_ids) == 1
        assert None not in note_ids

        for sample in dataset.samples:
            assert sample.question.strip()
            assert sample.expected_terms
