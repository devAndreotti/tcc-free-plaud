from pathlib import Path
from tempfile import TemporaryDirectory
from time import perf_counter

from escolio.app.config import Settings, get_settings
from escolio.corpus.benchmark_support import (
    CountingEmbedder,
    EmbedderFactory,
    IndexFn,
    build_benchmark_settings,
    rate,
    write_index_benchmark_fixture,
)
from escolio.corpus.models import (
    CorpusCommitMode,
    CorpusIndexBenchmarkResult,
    CorpusIndexBenchmarkRunResult,
)
from escolio.providers.embed import Embedder


def benchmark_corpus_indexing(
    *,
    files: int = 100,
    repeat: int = 2,
    settings: Settings | None = None,
    embedder: Embedder | None = None,
    chunk_size: int | None = None,
    overlap: int | None = None,
    commit_mode: CorpusCommitMode | None = None,
    index_fn: IndexFn,
    get_embedder_fn: EmbedderFactory,
) -> CorpusIndexBenchmarkResult:
    """Mede indexacao em corpus sintetico dentro de workspace temporario."""
    if files <= 0:
        raise ValueError('files precisa ser maior que zero.')
    if repeat <= 0:
        raise ValueError('repeat precisa ser maior que zero.')

    resolved_settings = settings or get_settings()
    resolved_embedder = embedder or get_embedder_fn(
        resolved_settings.embedding_model,
        device=resolved_settings.embedding_device,
    )
    counting_embedder = CountingEmbedder(resolved_embedder)
    resolved_chunk_size = chunk_size or resolved_settings.default_chunk_size
    resolved_overlap = resolved_settings.default_chunk_overlap if overlap is None else overlap
    commit_mode_requested = commit_mode or resolved_settings.corpus_commit_mode

    with TemporaryDirectory(prefix='escolio-corpus-benchmark-', ignore_cleanup_errors=True) as temporary_dir:
        workspace_dir = Path(temporary_dir)
        benchmark_settings = build_benchmark_settings(resolved_settings, workspace_dir)
        source_dir = workspace_dir / 'fixture'
        ignored_files = write_index_benchmark_fixture(source_dir, files)
        total_started_at = perf_counter()
        runs: list[CorpusIndexBenchmarkRunResult] = []

        for repeat_index in range(1, repeat + 1):
            calls_before = counting_embedder.calls
            started_at = perf_counter()
            batch_result = index_fn(
                source_dir,
                settings=benchmark_settings,
                embedder=counting_embedder,
                chunk_size=resolved_chunk_size,
                overlap=resolved_overlap,
                recursive=True,
                commit_mode=commit_mode_requested,
            )
            elapsed_ms = int((perf_counter() - started_at) * 1000)
            chunks_indexed = sum(item.chunks_indexed for item in batch_result.results if item.status == 'success')
            chunks_seen = sum(item.chunks_indexed for item in batch_result.results)
            processed_files = batch_result.indexed_count + batch_result.unchanged_count + batch_result.failed_count
            runs.append(
                CorpusIndexBenchmarkRunResult(
                    repeat_index=repeat_index,
                    status=batch_result.status,
                    elapsed_ms=elapsed_ms,
                    files_per_second=rate(processed_files, elapsed_ms),
                    chunks_per_second=rate(chunks_seen, elapsed_ms),
                    total_found=batch_result.total_found,
                    indexed_count=batch_result.indexed_count,
                    unchanged_count=batch_result.unchanged_count,
                    failed_count=batch_result.failed_count,
                    skipped_count=batch_result.skipped_count,
                    chunks_indexed=chunks_indexed,
                    embedding_calls=counting_embedder.calls - calls_before,
                    commit_mode_resolved=batch_result.commit_mode_resolved,
                )
            )

        total_elapsed_ms = int((perf_counter() - total_started_at) * 1000)

    indexed_count = sum(run.indexed_count for run in runs)
    unchanged_count = sum(run.unchanged_count for run in runs)
    failed_count = sum(run.failed_count for run in runs)
    skipped_count = runs[-1].skipped_count if runs else ignored_files
    chunks_indexed = sum(run.chunks_indexed for run in runs)
    processed_files = indexed_count + unchanged_count + failed_count

    if failed_count and (indexed_count or unchanged_count):
        status = 'partial'
    elif failed_count:
        status = 'failed'
    else:
        status = 'success'

    return CorpusIndexBenchmarkResult(
        status=status,  # type: ignore[arg-type]
        files_requested=files,
        supported_files=files,
        ignored_files=ignored_files,
        repeat=repeat,
        embedding_model=counting_embedder.model_name,
        commit_mode_requested=commit_mode_requested,
        commit_mode_resolved=runs[-1].commit_mode_resolved if runs else 'atomic',
        chunk_size=resolved_chunk_size,
        overlap=resolved_overlap,
        total_elapsed_ms=total_elapsed_ms,
        files_per_second=rate(processed_files, total_elapsed_ms),
        chunks_per_second=rate(chunks_indexed, total_elapsed_ms),
        indexed_count=indexed_count,
        unchanged_count=unchanged_count,
        failed_count=failed_count,
        skipped_count=skipped_count,
        chunks_indexed=chunks_indexed,
        embedding_calls=counting_embedder.calls,
        runs=runs,
    )


