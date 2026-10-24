"""Modelos de resultado do benchmark: por consulta, por estratégia, por caso e da comparação."""

from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, Field

PIPELINE_VERSION = 'pipeline-0.7.0'
STRATEGIES: tuple[Literal['lexical', 'vector', 'hybrid'], ...] = ('lexical', 'vector', 'hybrid')
# A passada no corpus busca 10 trechos: com o top_k do chat (3), Recall@5 e @10 repetiriam o @3.
CORPUS_RETRIEVAL_DEPTH = 10

class BenchmarkSettingsSnapshot(BaseModel):
    """Configuração operacional gravada junto do resultado experimental."""

    embedding_model: str
    embedding_device: str
    default_ask_strategy: str
    retrieval_top_k: int
    default_chunk_size: int
    default_chunk_overlap: int
    answer_provider: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class BenchmarkQueryResult(BaseModel):
    sample_id: str
    question: str
    expected_note_id: str | None = None
    expected_chunk_id: str | None = None
    expected_ref: str | None = None
    retrieved: list[dict[str, object]] = Field(default_factory=list)
    relevant_rank: int | None = None
    hit_at_k: int
    reciprocal_rank: float
    latency_ms: int
    category: str | None = None
    # Só na passada no corpus: o chat respondeu ou se absteve.
    answered: bool | None = None
    # Só na passada no corpus: a resposta gerativa foi aceita, ou o código do motivo do descarte.
    generated: bool | None = None
    discard_reason: str | None = None
    # Pergunta inteira no chat (recuperação e resposta), não só a busca.
    question_latency_ms: int | None = None
    # Só com `keep_answers` (compare --registrar-respostas): texto da resposta do chat e os trechos citados por ela.
    answer: str | None = None
    contexts: list[str] | None = None


class BenchmarkRunResult(BaseModel):
    benchmark_run_id: str
    run_name: str
    dataset_name: str
    retrieval_strategy: str
    chunking_strategy: str
    embedding_model: str
    top_k: int
    chunk_size: int
    overlap: int
    metrics: dict[str, float | int]
    queries: list[BenchmarkQueryResult]
    hybrid_config: dict[str, int | float | None] | None = None
    settings_snapshot: BenchmarkSettingsSnapshot | None = None
    started_at: datetime
    finished_at: datetime
    duration_ms: int


class BenchmarkAnswerMetrics(BaseModel):
    """Resposta do chat sobre todas as perguntas do corpus. Sem provider generativo: taxa nula e motivos vazios."""

    # Respostas com status `answer` (denominador da taxa de aceite).
    answer_count: int
    accepted_count: int
    accepted_rate: float | None = None
    # Código do motivo -> quantidade, incluindo as negativas que a validação trocou por abstenção.
    discard_reasons: dict[str, int] = Field(default_factory=dict)
    question_p50_ms: float = 0.0
    question_p95_ms: float = 0.0


class BenchmarkStrategySummary(BaseModel):
    strategy: str
    case_count: int
    query_count: int
    mrr: float
    recall_at_3: float
    recall_at_5: float
    recall_at_10: float
    ndcg_at_10: float
    duration_ms: int
    avg_query_latency_ms: float
    p50_query_latency_ms: float = 0.0
    p95_query_latency_ms: float = 0.0
    # Intervalo bootstrap de 95% da média: [inferior, superior].
    mrr_ci: list[float] | None = None
    recall_at_5_ci: list[float] | None = None
    # Decisão de responder/abster-se do chat; só na passada no corpus.
    abstention: dict[str, float] | None = None
    # Métricas da resposta gerativa do chat; só na passada no corpus.
    answer_metrics: BenchmarkAnswerMetrics | None = None


class BenchmarkCaseComparisonResult(BaseModel):
    case_id: str
    document_path: str
    dataset_path: str
    note_id: str
    note_title: str
    lexical: BenchmarkRunResult
    vector: BenchmarkRunResult
    hybrid: BenchmarkRunResult


class BenchmarkCorpusResult(BaseModel):
    """Todas as notas da suite num corpus só, buscadas como o chat busca (sem filtro por nota)."""

    note_count: int
    positive_count: int
    negative_count: int
    retrieval_depth: int
    summaries: dict[str, BenchmarkStrategySummary]
    queries: dict[str, list[BenchmarkQueryResult]]


class BenchmarkComparisonResult(BaseModel):
    comparison_id: str
    suite_name: str
    embedding_model: str
    top_k: int
    chunk_size: int
    overlap: int
    hybrid_config: dict[str, int | float | None] | None = None
    settings_snapshot: BenchmarkSettingsSnapshot | None = None
    summaries: dict[str, BenchmarkStrategySummary]
    cases: list[BenchmarkCaseComparisonResult]
    corpus: BenchmarkCorpusResult | None = None
    # Provider da resposta do chat usado na passada no corpus ('extractive' quando não há gerativo).
    answer_provider: str = 'extractive'
    answer_model: str | None = None
    started_at: datetime
    finished_at: datetime
    duration_ms: int
