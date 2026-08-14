from collections.abc import Callable
from pathlib import Path
from typing import Literal

from free_plaud.app.config import Settings, get_settings
from free_plaud.app.paths import ensure_runtime_dirs
from free_plaud.benchmark.datasets import load_benchmark_suite
from free_plaud.benchmark.runners import (
    BenchmarkComparisonResult,
    compare_benchmark_suite,
)
from free_plaud.corpus.ask import answer_corpus_with_citations
from free_plaud.corpus.cancellation import CancellationToken
from free_plaud.corpus.discovery import discover_corpus_files
from free_plaud.corpus.models import (
    CorpusDiscoveryResult,
    CorpusIndexBatchResult,
    CorpusIndexProgress,
    CorpusResetResult,
    CorpusStatusResult,
)
from free_plaud.corpus.runtime import CorpusRuntime
from free_plaud.corpus.service import (
    get_corpus_status,
    index_corpus_path,
    rebuild_corpus,
    reset_corpus,
)
from free_plaud.notes.schemas import Note
from free_plaud.providers.answer import get_answer_provider
from free_plaud.providers.embed import get_embedder, validate_runtime_embedding_model
from free_plaud.retrieval.models import AskResponse
from free_plaud.storage.sqlite import get_all_notes, init_sqlite
from free_plaud.storage.vector import LocalVectorStore

AskStrategy = Literal['lexical', 'vector', 'hybrid']
ProgressCallback = Callable[[CorpusIndexProgress], None]


def ask_corpus(
    question: str,
    strategy: AskStrategy,
    *,
    settings: Settings | None = None,
    runtime: CorpusRuntime | None = None,
) -> AskResponse:
    cleaned_question = question.strip()
    if not cleaned_question:
        raise ValueError('Pergunta vazia.')
    if strategy not in {'lexical', 'vector', 'hybrid'}:
        raise ValueError("strategy deve ser 'lexical', 'vector' ou 'hybrid'.")

    resolved_settings = settings or get_settings()
    ensure_runtime_dirs(resolved_settings)
    connection = init_sqlite(resolved_settings.sqlite_path)
    vector_store = None
    embedder = None
    if strategy in {'vector', 'hybrid'}:
        validate_runtime_embedding_model(resolved_settings.embedding_model)
        if runtime is not None:
            vector_store = runtime.get_vector_store()
            embedder = runtime.get_embedder()
        else:
            vector_store = LocalVectorStore(
                resolved_settings.vector_store_dir,
                collection_name=resolved_settings.vector_collection_name,
            )
            embedder = get_embedder(resolved_settings.embedding_model, device=resolved_settings.embedding_device)

    try:
        return answer_corpus_with_citations(
            cleaned_question,
            connection=connection,
            vector_store=vector_store,
            embedder=embedder,
            strategy=strategy,
            top_k=resolved_settings.retrieval_top_k,
            answer_provider=get_answer_provider(
                resolved_settings.answer_provider,
                model=resolved_settings.answer_model,
                base_url=resolved_settings.answer_base_url,
                api_key=resolved_settings.answer_api_key,
                temperature=resolved_settings.answer_temperature,
                max_tokens=resolved_settings.answer_max_tokens,
                timeout_seconds=resolved_settings.answer_timeout_seconds,
            ),
        )
    finally:
        connection.close()


def list_corpus_notes(*, settings: Settings | None = None) -> list[Note]:
    resolved_settings = settings or get_settings()
    ensure_runtime_dirs(resolved_settings)
    connection = init_sqlite(resolved_settings.sqlite_path)
    try:
        return get_all_notes(connection)
    finally:
        connection.close()


def corpus_status_from_tui(*, settings: Settings | None = None) -> CorpusStatusResult:
    return get_corpus_status(settings=settings or get_settings())


def _resolve_folder_path(folder_path: Path | str) -> Path:
    raw_path = str(folder_path).strip()
    if not raw_path:
        raise ValueError('Informe uma pasta para indexar.')

    target = Path(raw_path).expanduser()
    if not target.exists():
        raise FileNotFoundError(f'Pasta nao encontrada: {target}')
    if not target.is_dir():
        raise ValueError(f'Path precisa ser pasta: {target}')
    return target


def preflight_corpus_folder(folder_path: Path | str, *, recursive: bool | None = None) -> CorpusDiscoveryResult:
    target = _resolve_folder_path(folder_path)
    settings = get_settings()
    return discover_corpus_files(target, recursive=settings.corpus_recursive_default if recursive is None else recursive)


def _failed_batch(path: Path, message: str) -> CorpusIndexBatchResult:
    _ = message
    return CorpusIndexBatchResult(
        source_path=str(path),
        recursive=True,
        status='failed',
        total_found=0,
        indexed_count=0,
        failed_count=0,
        skipped_count=0,
        results=[],
        skipped=[],
    )


def index_corpus_folder(
    folder_path: Path | str,
    *,
    rebuild: bool = False,
    recursive: bool | None = None,
    settings: Settings | None = None,
    runtime: CorpusRuntime | None = None,
    progress: ProgressCallback | None = None,
    cancel_token: CancellationToken | None = None,
) -> CorpusIndexBatchResult:
    target = _resolve_folder_path(folder_path)
    resolved_settings = settings or get_settings()
    resolved_recursive = resolved_settings.corpus_recursive_default if recursive is None else recursive
    ensure_runtime_dirs(resolved_settings)
    validate_runtime_embedding_model(resolved_settings.embedding_model)
    vector_store = runtime.get_vector_store() if runtime is not None else None
    embedder = None
    if runtime is not None:
        progress and progress(
            CorpusIndexProgress(
                phase='warmup',
                current_path=str(target),
                commit_mode_requested=resolved_settings.corpus_commit_mode,
                message=f'Aquecendo embeddings: {resolved_settings.embedding_model} device={resolved_settings.embedding_device}.',
            )
        )
        warmup = runtime.warmup_embedder()
        embedder = runtime.get_embedder()
        progress and progress(
            CorpusIndexProgress(
                phase='warmup',
                current_path=str(target),
                warmup_ms=warmup.elapsed_ms,
                commit_mode_requested=resolved_settings.corpus_commit_mode,
                message=f'Embeddings prontos em {warmup.elapsed_ms} ms.',
            )
        )

    if rebuild:
        result = rebuild_corpus(
            target,
            settings=resolved_settings,
            vector_store=vector_store,
            embedder=embedder,
            recursive=resolved_recursive,
            dry_run=False,
            progress=progress,
            cancel_token=cancel_token,
        )
        if result.index_result is not None:
            return result.index_result
        return _failed_batch(target, result.message or result.error_code or 'Rebuild failed.')

    return index_corpus_path(
        target,
        settings=resolved_settings,
        vector_store=vector_store,
        embedder=embedder,
        recursive=resolved_recursive,
        progress=progress,
        cancel_token=cancel_token,
    )


def reset_corpus_from_tui(
    confirm: str,
    *,
    settings: Settings | None = None,
    runtime: CorpusRuntime | None = None,
) -> CorpusResetResult:
    if confirm.strip() != 'LIMPAR':
        raise ValueError('Digite LIMPAR para confirmar reset do corpus.')
    result = reset_corpus(settings=settings or get_settings(), dry_run=False)
    if runtime is not None:
        runtime.clear_vector_store()
    return result


def compare_suite_from_tui(
    suite_path: Path | str,
    *,
    settings: Settings | None = None,
    runtime: CorpusRuntime | None = None,
) -> BenchmarkComparisonResult:
    resolved_settings = settings or get_settings()
    ensure_runtime_dirs(resolved_settings)
    target = Path(suite_path).expanduser()
    if not target.exists():
        raise FileNotFoundError(f'Suite nao encontrada: {target}')
    validate_runtime_embedding_model(resolved_settings.embedding_model)

    suite = load_benchmark_suite(target)
    connection = init_sqlite(resolved_settings.sqlite_path)
    vector_store = LocalVectorStore(
        resolved_settings.results_dir / 'benchmark_compare' / suite.suite_name,
        collection_name=f'{suite.suite_name}_compare',
    )
    embedder = runtime.get_embedder() if runtime is not None else get_embedder(
        resolved_settings.embedding_model,
        device=resolved_settings.embedding_device,
    )
    try:
        return compare_benchmark_suite(
            suite,
            workspace_dir=resolved_settings.workspace_dir,
            connection=connection,
            vector_store=vector_store,
            embedder=embedder,
        )
    finally:
        connection.close()
