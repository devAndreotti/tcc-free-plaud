from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from statistics import quantiles
from time import perf_counter
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field

from escolio.benchmark.answer_metrics import generation_discard_reason
from escolio.benchmark.datasets import (
    BenchmarkDataset,
    BenchmarkSample,
    BenchmarkSuite,
    load_benchmark_dataset,
)
from escolio.benchmark.metrics import (
    abstention_metrics,
    bootstrap_ci,
    mean_reciprocal_rank,
    ndcg_at_k,
    recall_at_k_from_ranks,
)
from escolio.corpus.ask import answer_corpus_with_citations, retrieve_corpus_hits
from escolio.ingest.loaders import load_document
from escolio.notes.schemas import Note
from escolio.notes.structurer import structure_document
from escolio.providers.answer import AnswerProvider
from escolio.providers.embed import Embedder
from escolio.retrieval.indexer import index_note, index_note_in_vector_store
from escolio.retrieval.models import Chunk, SearchHit
from escolio.retrieval.search import (
    DEFAULT_HYBRID_LEXICAL_WEIGHT,
    DEFAULT_HYBRID_RANK_CONSTANT,
    DEFAULT_HYBRID_VECTOR_WEIGHT,
    hybrid_search,
    lexical_search_hits,
    semantic_search,
)
from escolio.storage.models import BenchmarkQueryRecord, BenchmarkRunRecord
from escolio.storage.sqlite import (
    insert_benchmark_query,
    insert_benchmark_run,
    list_chunk_ids,
    replace_chunks_for_note,
    upsert_note,
)
from escolio.storage.vector import LocalVectorStore

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


def _contains_expected_terms(text: str, expected_terms: list[str]) -> bool:
    if not expected_terms:
        return True
    lowered = text.lower()
    return all(term.lower() in lowered for term in expected_terms)


def _is_relevant(sample: BenchmarkSample, chunk: Chunk) -> bool:
    if sample.expected_chunk_id:
        return chunk.chunk_id == sample.expected_chunk_id
    if sample.expected_note_id and chunk.note_id != sample.expected_note_id:
        return False
    return _contains_expected_terms(chunk.chunk_text, sample.expected_terms)


def _retrieved_payload(hits: list[SearchHit]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for rank, hit in enumerate(hits, start=1):
        rows.append(
            {
                'rank': rank,
                'chunk_id': hit.chunk.chunk_id,
                'note_id': hit.chunk.note_id,
                'score': hit.score,
                'distance': hit.distance,
                'matched_terms': hit.matched_terms,
                'term_coverage': hit.term_coverage,
                'char_start': hit.chunk.char_start,
                'char_end': hit.chunk.char_end,
            }
        )
    return rows


def _run_query(sample: BenchmarkSample, hits: list[SearchHit], latency_ms: int) -> BenchmarkQueryResult:
    relevant_rank: int | None = None
    for rank, hit in enumerate(hits, start=1):
        if _is_relevant(sample, hit.chunk):
            relevant_rank = rank
            break
    reciprocal_rank = (1 / relevant_rank) if relevant_rank else 0.0
    return BenchmarkQueryResult(
        sample_id=sample.sample_id,
        question=sample.question,
        expected_note_id=sample.expected_note_id,
        expected_chunk_id=sample.expected_chunk_id,
        expected_ref=sample.expected_ref,
        retrieved=_retrieved_payload(hits),
        relevant_rank=relevant_rank,
        hit_at_k=1 if relevant_rank else 0,
        reciprocal_rank=reciprocal_rank,
        latency_ms=latency_ms,
    )


def _percentile(values: list[int], percent: int) -> float:
    if len(values) < 2:
        return float(values[0]) if values else 0.0
    return quantiles(values, n=100, method='inclusive')[percent - 1]


def _ci(values: list[float]) -> list[float]:
    interval = bootstrap_ci(values)
    return [interval['lower'], interval['upper']]


def _summarize_queries(
    strategy: str,
    queries: list[BenchmarkQueryResult],
    *,
    case_count: int,
    duration_ms: int,
) -> BenchmarkStrategySummary:
    ranks = [query.relevant_rank for query in queries]
    latencies = [query.latency_ms for query in queries]
    return BenchmarkStrategySummary(
        strategy=strategy,
        case_count=case_count,
        query_count=len(ranks),
        mrr=mean_reciprocal_rank(ranks),
        recall_at_3=recall_at_k_from_ranks(ranks, 3),
        recall_at_5=recall_at_k_from_ranks(ranks, 5),
        recall_at_10=recall_at_k_from_ranks(ranks, 10),
        ndcg_at_10=ndcg_at_k(ranks, 10),
        duration_ms=duration_ms,
        avg_query_latency_ms=(sum(latencies) / len(latencies)) if latencies else 0.0,
        p50_query_latency_ms=_percentile(latencies, 50),
        p95_query_latency_ms=_percentile(latencies, 95),
        mrr_ci=_ci([query.reciprocal_rank for query in queries]),
        recall_at_5_ci=_ci([1.0 if rank is not None and rank <= 5 else 0.0 for rank in ranks]),
    )


def _summarize_strategy(strategy: str, runs: list[BenchmarkRunResult]) -> BenchmarkStrategySummary:
    return _summarize_queries(
        strategy,
        [query for run in runs for query in run.queries],
        case_count=len(runs),
        duration_ms=sum(run.duration_ms for run in runs),
    )


def run_benchmark(
    note: Note,
    dataset: BenchmarkDataset,
    *,
    connection=None,
    strategy: Literal['lexical', 'vector', 'hybrid'] = 'lexical',
    top_k: int = 3,
    chunk_size: int = 800,
    overlap: int = 120,
    run_name: str = 'benchmark',
    vector_store: LocalVectorStore | None = None,
    embedder: Embedder | None = None,
    hybrid_rank_constant: int = DEFAULT_HYBRID_RANK_CONSTANT,
    hybrid_lexical_weight: float = DEFAULT_HYBRID_LEXICAL_WEIGHT,
    hybrid_vector_weight: float = DEFAULT_HYBRID_VECTOR_WEIGHT,
    hybrid_lexical_pool: int | None = None,
    hybrid_vector_pool: int | None = None,
    settings_snapshot: BenchmarkSettingsSnapshot | None = None,
    reuse_vectors: bool = False,
) -> BenchmarkRunResult:
    """Executa benchmark reproduzível sobre uma nota canônica.

    `reuse_vectors` pula o embedding quando o store já tem estes chunks. O chunk_id inclui o
    hash do texto e as posições, então ids iguais são textos iguais; só use quando o store foi
    preenchido pelo mesmo embedder (como na comparação, que zera o store no início).
    """
    started_at = datetime.now(UTC)
    started_perf = perf_counter()

    if strategy == 'lexical':
        chunks = index_note(note, chunk_size=chunk_size, overlap=overlap)
    elif strategy in {'vector', 'hybrid'}:
        if vector_store is None or embedder is None:
            raise ValueError('Vector store e embedder sao obrigatorios para strategy=vector e strategy=hybrid.')
        chunks = index_note(note, chunk_size=chunk_size, overlap=overlap)
        if not (reuse_vectors and vector_store.has_chunk_ids([chunk.chunk_id for chunk in chunks])):
            chunks = index_note_in_vector_store(note, vector_store, embedder, chunk_size=chunk_size, overlap=overlap)
    else:
        raise ValueError("strategy deve ser 'lexical', 'vector' ou 'hybrid'.")

    if connection is not None:
        upsert_note(connection, note)
        replace_chunks_for_note(connection, note.note_id, chunks)

    query_results: list[BenchmarkQueryResult] = []
    for sample in dataset.samples:
        query_started = perf_counter()
        if strategy == 'lexical':
            hits = lexical_search_hits(sample.question, chunks, top_k=top_k)
        elif strategy == 'hybrid':
            hits = hybrid_search(
                sample.question,
                chunks,
                vector_store,  # type: ignore[arg-type]
                embedder,  # type: ignore[arg-type]
                top_k=top_k,
                note_id=note.note_id,
                lexical_pool_size=hybrid_lexical_pool or max(top_k * 3, top_k),
                vector_pool_size=hybrid_vector_pool or max(top_k * 8, 24),
                rank_constant=hybrid_rank_constant,
                lexical_weight=hybrid_lexical_weight,
                vector_weight=hybrid_vector_weight,
            )
        else:
            hits = semantic_search(sample.question, vector_store, embedder, top_k=top_k, note_id=note.note_id)  # type: ignore[arg-type]
        latency_ms = int((perf_counter() - query_started) * 1000)
        query_results.append(_run_query(sample, hits, latency_ms))

    ranks = [result.relevant_rank for result in query_results]
    finished_at = datetime.now(UTC)
    duration_ms = int((perf_counter() - started_perf) * 1000)
    metrics: dict[str, float | int] = {
        'query_count': len(query_results),
        'mrr': mean_reciprocal_rank(ranks),
        'recall_at_3': recall_at_k_from_ranks(ranks, 3),
        'recall_at_5': recall_at_k_from_ranks(ranks, 5),
        'recall_at_10': recall_at_k_from_ranks(ranks, 10),
        'ndcg_at_3': ndcg_at_k(ranks, 3),
        'ndcg_at_5': ndcg_at_k(ranks, 5),
        'ndcg_at_10': ndcg_at_k(ranks, 10),
        'latency_ms': duration_ms,
        'avg_latency_ms': sum(result.latency_ms for result in query_results) / len(query_results)
        if query_results
        else 0.0,
    }
    run_result = BenchmarkRunResult(
        benchmark_run_id=f'run-{uuid4().hex[:12]}',
        run_name=run_name,
        dataset_name=dataset.dataset_name,
        retrieval_strategy=strategy,
        chunking_strategy='fixed_char_window',
        embedding_model=embedder.model_name if embedder else 'not-used',
        top_k=top_k,
        chunk_size=chunk_size,
        overlap=overlap,
        metrics=metrics,
        queries=query_results,
        hybrid_config=(
            {
                'rank_constant': hybrid_rank_constant,
                'lexical_weight': hybrid_lexical_weight,
                'vector_weight': hybrid_vector_weight,
                'lexical_pool': hybrid_lexical_pool or max(top_k * 3, top_k),
                'vector_pool': hybrid_vector_pool or max(top_k * 8, 24),
            }
            if strategy == 'hybrid'
            else None
        ),
        settings_snapshot=settings_snapshot,
        started_at=started_at,
        finished_at=finished_at,
        duration_ms=duration_ms,
    )

    if connection is not None:
        _persist_benchmark_result(connection, note, run_result)
    return run_result


def _summarize_answer_metrics(rows: list[BenchmarkQueryResult], *, has_provider: bool) -> BenchmarkAnswerMetrics:
    """Taxa de aceite sobre as respostas `answer`; latência p50/p95 da pergunta inteira."""
    answer_count = sum(1 for row in rows if row.answered)
    accepted_count = sum(1 for row in rows if row.generated)
    latencies = [row.question_latency_ms for row in rows if row.question_latency_ms is not None]
    return BenchmarkAnswerMetrics(
        answer_count=answer_count,
        accepted_count=accepted_count,
        accepted_rate=accepted_count / answer_count if has_provider and answer_count else None,
        discard_reasons=dict(sorted(Counter(row.discard_reason for row in rows if row.discard_reason).items())),
        question_p50_ms=_percentile(latencies, 50),
        question_p95_ms=_percentile(latencies, 95),
    )


def run_corpus_benchmark(
    cases: list[tuple[Note, BenchmarkDataset]],
    negatives: list[BenchmarkSample],
    *,
    connection,
    vector_store: LocalVectorStore,
    embedder: Embedder,
    top_k: int,
    answer_provider: AnswerProvider | None = None,
    keep_answers: bool = False,
) -> BenchmarkCorpusResult:
    """Mede o cenário do chat: todas as notas num corpus só, sem filtro por nota.

    Os rankings vêm de `retrieve_corpus_hits`, a mesma busca do chat, com profundidade 10. Um
    trecho só conta como relevante se for da nota do caso, então outra nota com os mesmos termos
    é erro. A decisão de responder ou se abster vem de `answer_corpus_with_citations` com
    `answer_provider` (None é o extrativo, determinístico), e as negativas medem se o chat se abstém quando o corpus
    não tem a resposta. Espera as notas já gravadas em `connection` e `vector_store`.
    """
    # ponytail: notas de uma versão antiga da suite seguem no SQLite da comparação como distratoras
    # na busca lexical; limpar o banco por rodada se a suite passar a perder casos com frequência.
    valid_chunk_ids = list_chunk_ids(connection)
    labeled = [
        (sample.model_copy(update={'expected_note_id': sample.expected_note_id or note.note_id}), False)
        for note, dataset in cases
        for sample in dataset.samples
    ] + [(sample, True) for sample in negatives]

    summaries: dict[str, BenchmarkStrategySummary] = {}
    queries_by_strategy: dict[str, list[BenchmarkQueryResult]] = {}
    for strategy in STRATEGIES:
        started = perf_counter()
        positives: list[BenchmarkQueryResult] = []
        rows: list[BenchmarkQueryResult] = []
        predicted_abstain: list[bool] = []
        gold_abstain: list[bool] = []
        for sample, is_negative in labeled:
            query_started = perf_counter()
            hits, _ = retrieve_corpus_hits(
                sample.question,
                connection=connection,
                valid_chunk_ids=valid_chunk_ids,
                top_k=CORPUS_RETRIEVAL_DEPTH,
                strategy=strategy,
                vector_store=vector_store,
                embedder=embedder,
            )
            latency_ms = int((perf_counter() - query_started) * 1000)
            response = answer_corpus_with_citations(
                sample.question,
                connection=connection,
                vector_store=vector_store,
                embedder=embedder,
                strategy=strategy,
                top_k=top_k,
                answer_provider=answer_provider,
            )
            answered = not response.no_answer
            if is_negative:
                row = BenchmarkQueryResult(
                    sample_id=sample.sample_id,
                    question=sample.question,
                    retrieved=_retrieved_payload(hits),
                    hit_at_k=0,
                    reciprocal_rank=0.0,
                    latency_ms=latency_ms,
                )
            else:
                row = _run_query(sample, hits, latency_ms)
                positives.append(row)
            row.category = 'negativa' if is_negative else sample.category
            row.answered = answered
            row.generated = response.generated
            row.discard_reason = generation_discard_reason(response, has_provider=answer_provider is not None)
            row.question_latency_ms = response.latency_ms
            if keep_answers and response.answer:
                cited_chunk_ids = {citation.chunk_id for citation in response.citations}
                row.answer = response.answer
                row.contexts = [hit.chunk.chunk_text for hit in hits if hit.chunk.chunk_id in cited_chunk_ids]
            rows.append(row)
            predicted_abstain.append(not answered)
            gold_abstain.append(is_negative)

        summary = _summarize_queries(
            strategy,
            positives,
            case_count=len(cases),
            duration_ms=int((perf_counter() - started) * 1000),
        )
        summary.abstention = abstention_metrics(predicted_abstain, gold_abstain)
        summary.abstention['answered_positive_rate'] = (
            sum(1 for row in positives if row.answered) / len(positives) if positives else 0.0
        )
        summary.answer_metrics = _summarize_answer_metrics(rows, has_provider=answer_provider is not None)
        summaries[strategy] = summary
        queries_by_strategy[strategy] = rows

    return BenchmarkCorpusResult(
        note_count=len(cases),
        positive_count=sum(1 for _, is_negative in labeled if not is_negative),
        negative_count=len(negatives),
        retrieval_depth=CORPUS_RETRIEVAL_DEPTH,
        summaries=summaries,
        queries=queries_by_strategy,
    )


def benchmark_compare_dir(results_dir: Path, suite_name: str) -> Path:
    """Pasta da comparação, com SQLite e Chroma próprios, separados do corpus do usuário.

    O histórico (benchmark_queries) referencia notes e chunks, então as notas da suite moram no
    mesmo banco do histórico. Usar o banco do corpus enchia Notas e o chat com os documentos da
    suite e deixava chunks no SQLite sem vetor no Chroma (o Doctor acusava corpus inconsistente).
    """
    return results_dir / 'benchmark_compare' / suite_name


def compare_benchmark_suite(
    suite: BenchmarkSuite,
    *,
    workspace_dir: Path,
    connection=None,
    top_k: int = 3,
    chunk_size: int = 800,
    overlap: int = 120,
    vector_store: LocalVectorStore,
    embedder: Embedder,
    hybrid_rank_constant: int = DEFAULT_HYBRID_RANK_CONSTANT,
    hybrid_lexical_weight: float = DEFAULT_HYBRID_LEXICAL_WEIGHT,
    hybrid_vector_weight: float = DEFAULT_HYBRID_VECTOR_WEIGHT,
    hybrid_lexical_pool: int | None = None,
    hybrid_vector_pool: int | None = None,
    settings_snapshot: BenchmarkSettingsSnapshot | None = None,
    answer_provider: AnswerProvider | None = None,
    keep_answers: bool = False,
) -> BenchmarkComparisonResult:
    """Compara lexical, vector e hybrid em múltiplos documentos de forma reproduzível."""
    started_at = datetime.now(UTC)
    started_perf = perf_counter()
    vector_store.reset()

    case_results: list[BenchmarkCaseComparisonResult] = []
    lexical_runs: list[BenchmarkRunResult] = []
    vector_runs: list[BenchmarkRunResult] = []
    hybrid_runs: list[BenchmarkRunResult] = []
    corpus_cases: list[tuple[Note, BenchmarkDataset]] = []

    for case in suite.cases:
        document_path = workspace_dir / case.document_path
        dataset_path = workspace_dir / case.dataset_path
        note = structure_document(load_document(document_path))
        dataset = load_benchmark_dataset(dataset_path)
        corpus_cases.append((note, dataset))

        lexical_result = run_benchmark(
            note,
            dataset,
            connection=connection,
            strategy='lexical',
            top_k=top_k,
            chunk_size=chunk_size,
            overlap=overlap,
            run_name=f'{suite.suite_name}-{case.case_id}-lexical',
            settings_snapshot=settings_snapshot,
        )
        vector_result = run_benchmark(
            note,
            dataset,
            connection=connection,
            strategy='vector',
            top_k=top_k,
            chunk_size=chunk_size,
            overlap=overlap,
            run_name=f'{suite.suite_name}-{case.case_id}-vector',
            vector_store=vector_store,
            embedder=embedder,
            settings_snapshot=settings_snapshot,
        )
        hybrid_result = run_benchmark(
            note,
            dataset,
            connection=connection,
            strategy='hybrid',
            top_k=top_k,
            chunk_size=chunk_size,
            overlap=overlap,
            run_name=f'{suite.suite_name}-{case.case_id}-hybrid',
            vector_store=vector_store,
            embedder=embedder,
            hybrid_rank_constant=hybrid_rank_constant,
            hybrid_lexical_weight=hybrid_lexical_weight,
            hybrid_vector_weight=hybrid_vector_weight,
            hybrid_lexical_pool=hybrid_lexical_pool,
            hybrid_vector_pool=hybrid_vector_pool,
            settings_snapshot=settings_snapshot,
            reuse_vectors=True,  # a rodada vetorial acabou de gravar estes mesmos chunks
        )

        lexical_runs.append(lexical_result)
        vector_runs.append(vector_result)
        hybrid_runs.append(hybrid_result)
        case_results.append(
            BenchmarkCaseComparisonResult(
                case_id=case.case_id,
                document_path=str(case.document_path),
                dataset_path=str(case.dataset_path),
                note_id=note.note_id,
                note_title=note.title,
                lexical=lexical_result,
                vector=vector_result,
                hybrid=hybrid_result,
            )
        )

    corpus = None
    if connection is not None:  # as rodadas por nota acabaram de gravar todas as notas no SQLite e no Chroma
        negatives = (
            load_benchmark_dataset(workspace_dir / suite.negative_dataset_path).samples
            if suite.negative_dataset_path
            else []
        )
        corpus = run_corpus_benchmark(
            corpus_cases,
            negatives,
            connection=connection,
            vector_store=vector_store,
            embedder=embedder,
            top_k=top_k,
            answer_provider=answer_provider,
            keep_answers=keep_answers,
        )

    finished_at = datetime.now(UTC)
    duration_ms = int((perf_counter() - started_perf) * 1000)
    return BenchmarkComparisonResult(
        comparison_id=f'cmp-{uuid4().hex[:12]}',
        suite_name=suite.suite_name,
        embedding_model=embedder.model_name,
        top_k=top_k,
        chunk_size=chunk_size,
        overlap=overlap,
        hybrid_config={
            'rank_constant': hybrid_rank_constant,
            'lexical_weight': hybrid_lexical_weight,
            'vector_weight': hybrid_vector_weight,
            'lexical_pool': hybrid_lexical_pool or max(top_k * 3, top_k),
            'vector_pool': hybrid_vector_pool or max(top_k * 8, 24),
        },
        settings_snapshot=settings_snapshot,
        summaries={
            'lexical': _summarize_strategy('lexical', lexical_runs),
            'vector': _summarize_strategy('vector', vector_runs),
            'hybrid': _summarize_strategy('hybrid', hybrid_runs),
        },
        cases=case_results,
        corpus=corpus,
        answer_provider=answer_provider.provider_name if answer_provider is not None else 'extractive',
        answer_model=getattr(answer_provider, 'model', None),
        started_at=started_at,
        finished_at=finished_at,
        duration_ms=duration_ms,
    )


def _persist_benchmark_result(connection, note: Note, result: BenchmarkRunResult) -> None:
    insert_benchmark_run(
        connection,
        BenchmarkRunRecord(
            benchmark_run_id=result.benchmark_run_id,
            run_name=result.run_name,
            dataset_name=result.dataset_name,
            corpus_snapshot=note.content_hash,
            retrieval_strategy=result.retrieval_strategy,
            chunking_strategy=result.chunking_strategy,
            embedding_model=result.embedding_model,
            top_k=result.top_k,
            query_count=len(result.queries),
            pipeline_version=PIPELINE_VERSION,
            status='success',
            config={
                'chunk_size': result.chunk_size,
                'overlap': result.overlap,
                'hybrid_config': result.hybrid_config,
                'settings_snapshot': (
                    result.settings_snapshot.model_dump(mode='json') if result.settings_snapshot else None
                ),
            },
            metrics=dict(result.metrics),
            started_at=result.started_at,
            finished_at=result.finished_at,
            duration_ms=result.duration_ms,
        ),
    )
    for query in result.queries:
        insert_benchmark_query(
            connection,
            BenchmarkQueryRecord(
                benchmark_run_id=result.benchmark_run_id,
                query_id=query.sample_id,
                query_text=query.question,
                expected_note_id=query.expected_note_id,
                expected_chunk_id=query.expected_chunk_id,
                expected_ref=query.expected_ref,
                retrieved=query.retrieved,
                hit_at_k=query.hit_at_k,  # type: ignore[arg-type]
                reciprocal_rank=query.reciprocal_rank,
                latency_ms=query.latency_ms,
            ),
        )


def run_demo_benchmark(note: Note, samples: list[BenchmarkSample]) -> list[dict[str, float | str]]:
    """Mantém compatibilidade com o comando demo antigo."""
    dataset = BenchmarkDataset(dataset_name='demo', samples=samples)
    result = run_benchmark(note, dataset, strategy='lexical', top_k=3)
    return [
        {
            'sample_id': query.sample_id,
            'recall_at_3': result.metrics['recall_at_3'],
        }
        for query in result.queries
    ]
