"""Passada no corpus: todas as notas da suite buscadas como o chat busca, com negativas e resposta."""

from time import perf_counter

from escolio.benchmark.answer_metrics import generation_discard_reason
from escolio.benchmark.datasets import BenchmarkDataset, BenchmarkSample
from escolio.benchmark.metrics import abstention_metrics
from escolio.benchmark.query_scoring import _retrieved_payload, _run_query
from escolio.benchmark.runner_models import (
    CORPUS_RETRIEVAL_DEPTH,
    STRATEGIES,
    BenchmarkCorpusResult,
    BenchmarkQueryResult,
    BenchmarkStrategySummary,
)
from escolio.benchmark.summaries import _summarize_answer_metrics, _summarize_queries
from escolio.corpus.ask import answer_corpus_with_citations, retrieve_corpus_hits
from escolio.notes.schemas import Note
from escolio.providers.answer import AnswerProvider
from escolio.providers.embed import Embedder
from escolio.retrieval.rerank import Reranker
from escolio.storage.sqlite import list_chunk_ids
from escolio.storage.vector import LocalVectorStore


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
    reranker: Reranker | None = None,
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
                reranker=reranker,
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
                reranker=reranker,
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
