import json
from datetime import UTC, datetime
from pathlib import Path
from statistics import mean, median
from tempfile import TemporaryDirectory
from time import perf_counter

from escolio.app.config import Settings, get_settings
from escolio.corpus.ask import answer_corpus_with_citations
from escolio.corpus.benchmark_support import (
    CountingEmbedder,
    EmbedderFactory,
    IndexFn,
    build_benchmark_settings,
    git_commit_for_path,
    percentile,
    rate,
    torch_environment,
    write_index_benchmark_fixture,
)
from escolio.corpus.models import (
    CorpusCommitMode,
    CorpusIndexBatchResult,
    CorpusIndexProgress,
    CorpusPerfBenchmarkResult,
)
from escolio.providers.embed import Embedder
from escolio.storage.sqlite import init_sqlite
from escolio.storage.vector import LocalVectorStore


def perf_benchmark_corpus(
    *,
    files: int = 100,
    repeat: int = 1,
    ask_repeat: int = 10,
    include_cold_start: bool = False,
    settings: Settings | None = None,
    embedder: Embedder | None = None,
    chunk_size: int | None = None,
    overlap: int | None = None,
    commit_mode: CorpusCommitMode | None = None,
    index_fn: IndexFn,
    get_embedder_fn: EmbedderFactory,
) -> CorpusPerfBenchmarkResult:
    """Roda benchmark pequeno, pergunta no corpus e salva JSON comparavel."""
    if files <= 0:
        raise ValueError('files precisa ser maior que zero.')
    if repeat <= 0:
        raise ValueError('repeat precisa ser maior que zero.')
    if ask_repeat < 0:
        raise ValueError('ask-repeat não pode ser negativo.')

    resolved_settings = settings or get_settings()
    resolved_chunk_size = chunk_size or resolved_settings.default_chunk_size
    resolved_overlap = resolved_settings.default_chunk_overlap if overlap is None else overlap
    commit_mode_requested = commit_mode or resolved_settings.corpus_commit_mode
    cold_start_ms = 0
    embedder_init_ms = 0
    first_embed_ms = 0
    warm_embed_ms = 0
    base_embedder = embedder

    if base_embedder is None:
        init_started_at = perf_counter()
        base_embedder = get_embedder_fn(resolved_settings.embedding_model, device=resolved_settings.embedding_device)
        embedder_init_ms = int((perf_counter() - init_started_at) * 1000)
        if include_cold_start:
            first_started_at = perf_counter()
            base_embedder.embed(['escolio cold start benchmark'])
            first_embed_ms = int((perf_counter() - first_started_at) * 1000)
            warm_started_at = perf_counter()
            base_embedder.embed(['escolio warm benchmark'])
            warm_embed_ms = int((perf_counter() - warm_started_at) * 1000)
    cold_start_ms = embedder_init_ms + first_embed_ms
    counting_embedder = CountingEmbedder(base_embedder)

    with TemporaryDirectory(prefix='escolio-corpus-perf-', ignore_cleanup_errors=True) as temporary_dir:
        workspace_dir = Path(temporary_dir)
        benchmark_settings = build_benchmark_settings(resolved_settings, workspace_dir)
        source_dir = workspace_dir / 'fixture'
        ignored_files = write_index_benchmark_fixture(source_dir, files)
        progress_events: list[CorpusIndexProgress] = []
        batch_results: list[CorpusIndexBatchResult] = []
        total_index_ms = 0
        for _ in range(repeat):
            run_events: list[CorpusIndexProgress] = []
            index_started_at = perf_counter()
            batch_result = index_fn(
                source_dir,
                settings=benchmark_settings,
                embedder=counting_embedder,
                chunk_size=resolved_chunk_size,
                overlap=resolved_overlap,
                recursive=True,
                commit_mode=commit_mode_requested,
                progress=run_events.append,
            )
            total_index_ms += int((perf_counter() - index_started_at) * 1000)
            batch_results.append(batch_result)
            if not progress_events:
                progress_events = run_events
        connection = init_sqlite(benchmark_settings.sqlite_path)
        vector_store = LocalVectorStore(
            benchmark_settings.vector_store_dir,
            collection_name=benchmark_settings.vector_collection_name,
        )
        ask_latencies: list[int] = []
        try:
            for _ in range(ask_repeat):
                ask_started_at = perf_counter()
                answer_corpus_with_citations(
                    'RabbitMQ runbook SRE pipeline',
                    connection=connection,
                    vector_store=vector_store,
                    embedder=counting_embedder,
                    strategy='hybrid',
                    top_k=benchmark_settings.retrieval_top_k,
                )
                ask_latencies.append(int((perf_counter() - ask_started_at) * 1000))
        finally:
            connection.close()

    first_progress_ms = progress_events[0].elapsed_ms if progress_events else 0
    first_committed_ms = next(
        (event.elapsed_ms for event in progress_events if event.phase == 'committed' or event.indexed_count > 0),
        0,
    )
    chunks_indexed = sum(
        item.chunks_indexed
        for batch_result in batch_results
        for item in batch_result.results
        if item.status == 'success'
    )
    processed_files = sum(
        batch_result.indexed_count + batch_result.unchanged_count + batch_result.failed_count
        for batch_result in batch_results
    )
    failed_count = sum(batch_result.failed_count for batch_result in batch_results)
    indexed_count = sum(batch_result.indexed_count for batch_result in batch_results)
    unchanged_count = sum(batch_result.unchanged_count for batch_result in batch_results)
    if failed_count and (indexed_count or unchanged_count):
        status = 'partial'
    elif failed_count:
        status = 'failed'
    elif batch_results and any(batch_result.status == 'cancelled' for batch_result in batch_results):
        status = 'cancelled'
    else:
        status = 'success'
    environment = torch_environment()
    timestamp = datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')
    output_dir = resolved_settings.results_dir / 'corpus_perf'
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f'perf-{timestamp}.json'
    result = CorpusPerfBenchmarkResult(
        status=status,  # type: ignore[arg-type]
        output_path=str(output_path),
        timestamp=timestamp,
        git_commit=git_commit_for_path(resolved_settings.workspace_dir),
        cold_start_ms=cold_start_ms,
        python_import_ms=0,
        embedder_init_ms=embedder_init_ms,
        first_embed_ms=first_embed_ms,
        warm_embed_ms=warm_embed_ms,
        first_progress_ms=first_progress_ms,
        first_committed_ms=first_committed_ms,
        first_askable_ms=first_committed_ms,
        total_index_ms=total_index_ms,
        files_per_second=rate(processed_files, total_index_ms),
        chunks_per_second=rate(chunks_indexed, total_index_ms),
        embedding_calls=counting_embedder.calls,
        ask_avg_ms=round(mean(ask_latencies), 3) if ask_latencies else 0.0,
        ask_p50_ms=float(median(ask_latencies)) if ask_latencies else 0.0,
        ask_p95_ms=percentile(ask_latencies, 0.95),
        commit_mode_requested=commit_mode_requested,
        commit_mode_resolved=batch_results[0].commit_mode_resolved if batch_results else 'atomic',
        device=resolved_settings.embedding_device,
        embedding_model=counting_embedder.model_name,
        torch_version=environment.get('torch_version') if isinstance(environment.get('torch_version'), str) else None,
        cuda_available=bool(environment.get('cuda_available')),
        gpu_name=environment.get('gpu_name') if isinstance(environment.get('gpu_name'), str) else None,
        peak_vram_mb=environment.get('peak_vram_mb') if isinstance(environment.get('peak_vram_mb'), int) else None,
        dataset_shape={
            'files_requested': files,
            'supported_files': files,
            'ignored_files': ignored_files,
            'chunks_indexed': chunks_indexed,
            'ask_repeat': ask_repeat,
            'repeat': repeat,
        },
        settings={
            'chunk_size': resolved_chunk_size,
            'overlap': resolved_overlap,
            'corpus_embedding_batch_size': resolved_settings.corpus_embedding_batch_size,
            'corpus_upsert_batch_size': resolved_settings.corpus_upsert_batch_size,
            'corpus_micro_batch_chunks': resolved_settings.corpus_micro_batch_chunks,
            'corpus_micro_batch_files': resolved_settings.corpus_micro_batch_files,
            'corpus_index_workers': resolved_settings.corpus_index_workers,
        },
        environment=environment,
    )
    output_path.write_text(json.dumps(result.model_dump(mode='json'), ensure_ascii=True, indent=2), encoding='utf-8')
    return result
