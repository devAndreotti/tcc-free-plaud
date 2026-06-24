import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

BenchmarkCategory = Literal['direta', 'inferida', 'negativa']


class BenchmarkSample(BaseModel):
    """Representa uma consulta de benchmark com evidência esperada."""

    sample_id: str
    question: str
    expected_note_id: str | None = None
    expected_chunk_id: str | None = None
    expected_terms: list[str] = Field(default_factory=list)
    expected_ref: str | None = None
    category: BenchmarkCategory | None = None


class BenchmarkDataset(BaseModel):
    """Coleção versionável de perguntas para avaliação experimental."""

    dataset_name: str
    samples: list[BenchmarkSample]


class BenchmarkSuiteCase(BaseModel):
    """Relaciona um documento local ao dataset que deve avaliá-lo."""

    case_id: str
    document_path: Path
    dataset_path: Path


class BenchmarkSuite(BaseModel):
    """Coleção reproduzível de casos para comparar estratégias."""

    suite_name: str
    cases: list[BenchmarkSuiteCase]


def load_benchmark_dataset(path: Path) -> BenchmarkDataset:
    """Carrega dataset JSON em formato objeto ou lista simples."""
    payload = json.loads(path.read_text(encoding='utf-8'))
    if isinstance(payload, list):
        return BenchmarkDataset(dataset_name=path.stem, samples=[BenchmarkSample(**item) for item in payload])
    return BenchmarkDataset(**payload)


def load_benchmark_suite(path: Path) -> BenchmarkSuite:
    """Carrega manifesto JSON com múltiplos pares documento/dataset."""
    payload = json.loads(path.read_text(encoding='utf-8'))
    return BenchmarkSuite(**payload)


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
