import sqlite3
from collections.abc import Callable
from pathlib import Path

from escolio.app.config import Settings, get_settings
from escolio.app.paths import ensure_runtime_dirs
from escolio.corpus.cancellation import CancellationToken
from escolio.corpus.index_results import ProgressCallback
from escolio.corpus.maintenance import reset_corpus
from escolio.corpus.models import (
    CorpusCommitMode,
    CorpusIndexBatchResult,
    CorpusRebuildResult,
)
from escolio.corpus.status import get_corpus_status
from escolio.providers.embed import Embedder
from escolio.storage.sqlite import init_sqlite
from escolio.storage.vector import LocalVectorStore

# index_fn chega por parametro (a fachada service passa index_corpus_path em tempo de chamada),
# para que monkeypatch em escolio.corpus.service continue valendo sem ciclo de import.
IndexFn = Callable[..., CorpusIndexBatchResult]


def rebuild_corpus(
    path: Path | str,
    *,
    settings: Settings | None = None,
    connection: sqlite3.Connection | None = None,
    vector_store: LocalVectorStore | None = None,
    embedder: Embedder | None = None,
    chunk_size: int | None = None,
    overlap: int | None = None,
    recursive: bool = False,
    dry_run: bool = True,
    commit_mode: CorpusCommitMode | None = None,
    progress: ProgressCallback | None = None,
    cancel_token: CancellationToken | None = None,
    index_fn: IndexFn,
) -> CorpusRebuildResult:
    """Reconstroi corpus ativo a partir de arquivo ou diretorio controlado."""
    resolved_settings = settings or get_settings()
    ensure_runtime_dirs(resolved_settings)
    source_path = Path(path).expanduser()

    owns_connection = connection is None
    resolved_connection = connection or init_sqlite(resolved_settings.sqlite_path)
    resolved_vector_store = vector_store or LocalVectorStore(
        resolved_settings.vector_store_dir,
        collection_name=resolved_settings.vector_collection_name,
    )

    try:
        before_status = get_corpus_status(
            settings=resolved_settings,
            connection=resolved_connection,
            vector_store=resolved_vector_store,
        )
        if not source_path.exists():
            return CorpusRebuildResult(
                source_path=str(source_path),
                recursive=recursive,
                dry_run=dry_run,
                status='failed',
                before_status=before_status,
                error_code='INPUT_NOT_FOUND',
                message='Caminho não encontrado.',
            )

        reset_result = reset_corpus(
            settings=resolved_settings,
            connection=resolved_connection,
            vector_store=resolved_vector_store,
            dry_run=dry_run,
        )
        if dry_run:
            return CorpusRebuildResult(
                source_path=str(source_path),
                recursive=recursive,
                dry_run=True,
                status='preview',
                before_status=before_status,
                reset=reset_result,
                after_status=before_status,
            )

        index_result = index_fn(
            source_path,
            settings=resolved_settings,
            connection=resolved_connection,
            vector_store=resolved_vector_store,
            embedder=embedder,
            chunk_size=chunk_size,
            overlap=overlap,
            recursive=recursive,
            commit_mode=commit_mode,
            progress=progress,
            cancel_token=cancel_token,
        )
        after_status = get_corpus_status(
            settings=resolved_settings,
            connection=resolved_connection,
            vector_store=resolved_vector_store,
        )
        return CorpusRebuildResult(
            source_path=str(source_path),
            recursive=recursive,
            dry_run=False,
            status=index_result.status,
            before_status=before_status,
            reset=reset_result,
            index_result=index_result,
            after_status=after_status,
        )
    finally:
        if owns_connection:
            resolved_connection.close()
