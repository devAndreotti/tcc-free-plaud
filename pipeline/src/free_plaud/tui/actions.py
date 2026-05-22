from collections.abc import Callable
from pathlib import Path
from typing import Literal

from free_plaud.app.config import Settings, get_settings
from free_plaud.app.paths import ensure_runtime_dirs
from free_plaud.benchmark.datasets import load_benchmark_suite
from free_plaud.benchmark.runners import BenchmarkComparisonResult, compare_benchmark_suite
from free_plaud.corpus.ask import answer_corpus_with_citations
from free_plaud.corpus.discovery import discover_corpus_files
from free_plaud.corpus.models import (
    CorpusDiscoveryResult,
    CorpusIndexBatchResult,
    CorpusIndexProgress,
    CorpusResetResult,
    CorpusStatusResult,
)
from free_plaud.corpus.service import get_corpus_status, index_corpus_path, rebuild_corpus, reset_corpus
from free_plaud.notes.schemas import Note
from free_plaud.providers.embed import get_embedder
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
        vector_store = LocalVectorStore(
            resolved_settings.vector_store_dir,
            collection_name=resolved_settings.vector_collection_name,
        )
        embedder = get_embedder(resolved_settings.embedding_model)

    try:
        return answer_corpus_with_citations(
            cleaned_question,
            connection=connection,
            vector_store=vector_store,
            embedder=embedder,
            strategy=strategy,
            top_k=resolved_settings.retrieval_top_k,
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


def preflight_corpus_folder(folder_path: Path | str) -> CorpusDiscoveryResult:
    target = _resolve_folder_path(folder_path)
    return discover_corpus_files(target, recursive=True)


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
    settings: Settings | None = None,
    progress: ProgressCallback | None = None,
) -> CorpusIndexBatchResult:
    target = _resolve_folder_path(folder_path)
    resolved_settings = settings or get_settings()
    ensure_runtime_dirs(resolved_settings)

    if rebuild:
        result = rebuild_corpus(target, settings=resolved_settings, recursive=True, dry_run=False, progress=progress)
        if result.index_result is not None:
            return result.index_result
        return _failed_batch(target, result.message or result.error_code or 'Rebuild failed.')

    return index_corpus_path(target, settings=resolved_settings, recursive=True, progress=progress)


def reset_corpus_from_tui(confirm: str, *, settings: Settings | None = None) -> CorpusResetResult:
    if confirm.strip() != 'LIMPAR':
        raise ValueError('Digite LIMPAR para confirmar reset do corpus.')
    return reset_corpus(settings=settings or get_settings(), dry_run=False)


def compare_suite_from_tui(
    suite_path: Path | str,
    *,
    settings: Settings | None = None,
) -> BenchmarkComparisonResult:
    resolved_settings = settings or get_settings()
    ensure_runtime_dirs(resolved_settings)
    target = Path(suite_path).expanduser()
    if not target.exists():
        raise FileNotFoundError(f'Suite nao encontrada: {target}')

    suite = load_benchmark_suite(target)
    connection = init_sqlite(resolved_settings.sqlite_path)
    vector_store = LocalVectorStore(
        resolved_settings.results_dir / 'benchmark_compare' / suite.suite_name,
        collection_name=f'{suite.suite_name}_compare',
    )
    embedder = get_embedder(resolved_settings.embedding_model)
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
