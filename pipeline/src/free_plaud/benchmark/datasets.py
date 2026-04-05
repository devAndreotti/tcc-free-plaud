from pydantic import BaseModel, Field


class BenchmarkSample(BaseModel):
    """Representa uma consulta de benchmark com resposta esperada."""

    sample_id: str
    question: str
    expected_terms: list[str] = Field(default_factory=list)


def demo_dataset() -> list[BenchmarkSample]:
    return [
        BenchmarkSample(
            sample_id='demo-1',
            question='Qual é o tema principal do documento?',
            expected_terms=['tema', 'principal'],
        )
    ]
