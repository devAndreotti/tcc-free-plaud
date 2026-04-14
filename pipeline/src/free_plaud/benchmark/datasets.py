import json
from pathlib import Path

from pydantic import BaseModel, Field


class BenchmarkSample(BaseModel):
    """Representa uma consulta de benchmark com evidência esperada."""

    sample_id: str
    question: str
    expected_note_id: str | None = None
    expected_chunk_id: str | None = None
    expected_terms: list[str] = Field(default_factory=list)
    expected_ref: str | None = None


class BenchmarkDataset(BaseModel):
    """Coleção versionável de perguntas para avaliação experimental."""

    dataset_name: str
    samples: list[BenchmarkSample]


def load_benchmark_dataset(path: Path) -> BenchmarkDataset:
    """Carrega dataset JSON em formato objeto ou lista simples."""
    payload = json.loads(path.read_text(encoding='utf-8'))
    if isinstance(payload, list):
        return BenchmarkDataset(dataset_name=path.stem, samples=[BenchmarkSample(**item) for item in payload])
    return BenchmarkDataset(**payload)


def demo_dataset() -> BenchmarkDataset:
    return BenchmarkDataset(
        dataset_name='demo',
        samples=[
            BenchmarkSample(
                sample_id='demo-1',
                question='Qual é o tema principal do documento?',
                expected_terms=['tema', 'principal'],
            )
        ],
    )
