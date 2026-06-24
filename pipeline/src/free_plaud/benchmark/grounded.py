from statistics import fmean
from typing import Literal

from pydantic import BaseModel, Field

from free_plaud.benchmark.datasets import BenchmarkDataset
from free_plaud.benchmark.metrics import abstention_metrics, lexical_groundedness
from free_plaud.notes.schemas import Note
from free_plaud.providers.embed import Embedder
from free_plaud.retrieval.rag import answer_with_citations
from free_plaud.storage.vector import LocalVectorStore


class GroundedAnswerResult(BaseModel):
    """Avaliação de uma única pergunta no benchmark de resposta fundamentada."""

    sample_id: str
    question: str
    category: str | None
    answered: bool
    expected_abstain: bool
    decision_correct: bool
    groundedness: float | None
    citation_count: int
    latency_ms: int


class GroundedAnswerReport(BaseModel):
    """Resultado agregado de faithfulness e abstenção sobre um dataset."""

    dataset_name: str
    strategy: str
    sample_count: int
    answered_count: int
    mean_groundedness: float
    abstention: dict[str, float]
    results: list[GroundedAnswerResult] = Field(default_factory=list)


def evaluate_grounded_answers(
    note: Note,
    dataset: BenchmarkDataset,
    *,
    strategy: Literal['lexical', 'vector', 'hybrid'] = 'lexical',
    top_k: int = 3,
    vector_store: LocalVectorStore | None = None,
    embedder: Embedder | None = None,
) -> GroundedAnswerReport:
    """Responde cada sample com answer_with_citations e mede a qualidade gerada.

    Para cada pergunta computa a fundamentação lexical da resposta nos trechos
    citados (proxy de faithfulness, calculado só nas respondidas) e compara a
    decisão de responder/abster-se com a categoria esperada: ``negativa``
    significa que o sistema deveria abster-se. O agregado traz a groundedness
    média das respondidas e as métricas de abstenção sobre todas as samples.
    """
    results: list[GroundedAnswerResult] = []
    groundedness_values: list[float] = []
    predicted_abstain: list[bool] = []
    gold_abstain: list[bool] = []

    for sample in dataset.samples:
        response = answer_with_citations(
            note,
            sample.question,
            top_k=top_k,
            strategy=strategy,
            vector_store=vector_store,
            embedder=embedder,
        )
        answered = not response.no_answer
        expected_abstain = sample.category == 'negativa'

        groundedness: float | None = None
        if answered:
            supporting = [citation.snippet for citation in response.citations]
            groundedness = lexical_groundedness(response.answer or '', supporting)
            groundedness_values.append(groundedness)

        predicted_abstain.append(not answered)
        gold_abstain.append(expected_abstain)
        results.append(
            GroundedAnswerResult(
                sample_id=sample.sample_id,
                question=sample.question,
                category=sample.category,
                answered=answered,
                expected_abstain=expected_abstain,
                decision_correct=(not answered) == expected_abstain,
                groundedness=groundedness,
                citation_count=len(response.citations),
                latency_ms=response.latency_ms,
            )
        )

    return GroundedAnswerReport(
        dataset_name=dataset.dataset_name,
        strategy=strategy,
        sample_count=len(results),
        answered_count=len(groundedness_values),
        mean_groundedness=fmean(groundedness_values) if groundedness_values else 0.0,
        abstention=abstention_metrics(predicted_abstain, gold_abstain),
        results=results,
    )
