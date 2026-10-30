import sqlite3
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter

from escolio.app.config import Settings
from escolio.corpus.cancellation import CancellationToken
from escolio.corpus.index_results import (
    ProgressCallback,
    emit_progress,
    failure_result,
    is_cancelled,
)
from escolio.corpus.models import (
    CorpusCommitMode,
    CorpusIndexResult,
    ResolvedCorpusCommitMode,
)
from escolio.notes.schemas import Note
from escolio.providers.embed import Embedder
from escolio.retrieval.models import Chunk
from escolio.storage.sqlite import (
    delete_note_and_chunks,
    list_note_ids_by_source_path,
    replace_chunks_for_note,
    upsert_note,
)
from escolio.storage.vector import LocalVectorStore


@dataclass(frozen=True)
class PendingCorpusIndex:
    source_path: Path
    note: Note
    chunks: list[Chunk]


@dataclass(frozen=True)
class PreparationFailure:
    source_path: Path
    error_code: str
    message: str


def batched(items: list, batch_size: int):
    for start in range(0, len(items), batch_size):
        yield items[start : start + batch_size]


def count_pending_chunks(items: list[PendingCorpusIndex]) -> int:
    return sum(len(item.chunks) for item in items)


def duplicate_note_ids(items: list[PendingCorpusIndex]) -> set[str]:
    seen: set[str] = set()
    duplicates: set[str] = set()
    for item in items:
        if item.note.note_id in seen:
            duplicates.add(item.note.note_id)
        seen.add(item.note.note_id)
    return duplicates


def delete_superseded_source_notes(
    connection: sqlite3.Connection,
    vector_store: LocalVectorStore,
    note: Note,
) -> None:
    for existing_note_id in list_note_ids_by_source_path(connection, note.source_path):
        if existing_note_id == note.note_id:
            continue
        vector_store.delete_by_note_id(existing_note_id)
        delete_note_and_chunks(connection, existing_note_id)


def resolve_initial_commit_mode(
    requested: CorpusCommitMode,
    *,
    total_files: int,
    settings: Settings,
    source_is_file: bool = False,
) -> ResolvedCorpusCommitMode:
    if requested == 'atomic' or source_is_file:
        return 'atomic'
    if requested == 'microbatch':
        return 'microbatch'
    return 'microbatch' if total_files > settings.corpus_atomic_max_files else 'atomic'


def should_switch_auto_to_microbatch(
    requested: CorpusCommitMode,
    resolved: ResolvedCorpusCommitMode,
    *,
    pending_items: list[PendingCorpusIndex],
    settings: Settings,
) -> bool:
    return (
        requested == 'auto'
        and resolved == 'atomic'
        and count_pending_chunks(pending_items) > settings.corpus_atomic_max_chunks
    )


def should_flush_microbatch(pending_items: list[PendingCorpusIndex], *, settings: Settings) -> bool:
    if not pending_items:
        return False
    return (
        len(pending_items) >= settings.corpus_micro_batch_files
        or count_pending_chunks(pending_items) >= settings.corpus_micro_batch_chunks
    )


@dataclass
class CommitOutcome:
    results: list[CorpusIndexResult]
    indexed_count: int
    failed_count: int
    embedding_ms: int
    writing_ms: int


def commit_pending_items(
    pending_items: list[PendingCorpusIndex],
    *,
    settings: Settings,
    vector_store: LocalVectorStore,
    connection: sqlite3.Connection,
    embedder: Embedder,
    progress: ProgressCallback | None,
    started_at: float,
    source_path: Path,
    total_found: int,
    skipped_count: int,
    unchanged_count: int,
    indexed_count: int,
    failed_count: int,
    commit_mode_requested: CorpusCommitMode,
    commit_mode_resolved: ResolvedCorpusCommitMode,
    batch_index: int,
    batch_total: int,
    cancel_token: CancellationToken | None,
) -> CommitOutcome:
    """Embeda e grava um grupo de notas ja estruturadas.

    O helper deixa SQLite/Chroma writes no thread principal. Isso evita
    compartilhar conexao SQLite entre workers e limita estado parcial ao lote.
    """
    if not pending_items:
        return CommitOutcome([], 0, 0, 0, 0)

    duplicates = duplicate_note_ids(pending_items)
    if duplicates:
        duplicate_list = ', '.join(sorted(duplicates))
        failures = [
            failure_result(
                item.source_path,
                error_code='DUPLICATE_NOTE_ID',
                message=f'Note_id duplicado no lote: {duplicate_list}. Nada foi gravado.',
                vector_store=vector_store,
                embedding_model=embedder.model_name,
            )
            for item in pending_items
        ]
        return CommitOutcome(failures, 0, len(failures), 0, 0)

    chunk_pairs = [(item, chunk) for item in pending_items for chunk in item.chunks]
    embeddings_by_chunk_id: dict[str, list[float]] = {}
    embedding_ms = 0
    writing_ms = 0

    for chunk_batch in batched(chunk_pairs, settings.corpus_embedding_batch_size):
        if is_cancelled(cancel_token):
            break
        emit_progress(
            progress,
            phase='embedding',
            started_at=started_at,
            current_path=chunk_batch[0][0].source_path if chunk_batch else source_path,
            total_found=total_found,
            processed_count=indexed_count + unchanged_count + failed_count,
            indexed_count=indexed_count,
            unchanged_count=unchanged_count,
            failed_count=failed_count,
            skipped_count=skipped_count,
            committed_count=indexed_count,
            commit_mode_requested=commit_mode_requested,
            commit_mode_resolved=commit_mode_resolved,
            batch_index=batch_index,
            batch_total=batch_total,
            message=f'Gerando vetores de busca semântica: lote {batch_index}/{batch_total or 1}, {len(chunk_batch)} trechos.',
        )
        chunks = [chunk for _, chunk in chunk_batch]
        embedding_started_at = perf_counter()
        embeddings = embedder.embed([chunk.chunk_text for chunk in chunks])
        embedding_ms += int((perf_counter() - embedding_started_at) * 1000)
        if len(embeddings) != len(chunks):
            failures = [
                failure_result(
                    item.source_path,
                    error_code='INDEXING_FAILED',
                    message='A quantidade de vetores precisa bater com a quantidade de trechos.',
                    vector_store=vector_store,
                    embedding_model=embedder.model_name,
                )
                for item in pending_items
            ]
            return CommitOutcome(failures, 0, len(failures), embedding_ms, writing_ms)
        for chunk, embedding in zip(chunks, embeddings, strict=True):
            embeddings_by_chunk_id[chunk.chunk_id] = embedding

    if is_cancelled(cancel_token):
        return CommitOutcome([], 0, 0, embedding_ms, writing_ms)

    emit_progress(
        progress,
        phase='writing',
        started_at=started_at,
        current_path=source_path,
        total_found=total_found,
        processed_count=indexed_count + unchanged_count + failed_count,
        indexed_count=indexed_count,
        unchanged_count=unchanged_count,
        failed_count=failed_count,
        skipped_count=skipped_count,
        embedding_ms=embedding_ms,
        committed_count=indexed_count,
        commit_mode_requested=commit_mode_requested,
        commit_mode_resolved=commit_mode_resolved,
        batch_index=batch_index,
        batch_total=batch_total,
        message=f'Gravando lote {batch_index}/{batch_total or 1}: {len(pending_items)} arquivos.',
    )
    writing_started_at = perf_counter()
    for item in pending_items:
        delete_superseded_source_notes(connection, vector_store, item.note)
        vector_store.delete_by_note_id(item.note.note_id)
    all_chunks = [chunk for item in pending_items for chunk in item.chunks]
    for chunk_batch in batched(all_chunks, settings.corpus_upsert_batch_size):
        vector_store.upsert_chunks(
            chunk_batch,
            [embeddings_by_chunk_id[chunk.chunk_id] for chunk in chunk_batch],
            embedding_model=embedder.model_name,
        )
    committed_results: list[CorpusIndexResult] = []
    for item in pending_items:
        upsert_note(connection, item.note)
        replace_chunks_for_note(connection, item.note.note_id, item.chunks)
        committed_results.append(
            CorpusIndexResult(
                source_path=str(item.source_path),
                status='success',
                note_id=item.note.note_id,
                chunks_indexed=len(item.chunks),
                embedding_model=embedder.model_name,
                vector_collection_name=vector_store.collection_name,
                vector_entries_count=0,
                message='Nota indexada.',
            )
        )
    writing_ms = int((perf_counter() - writing_started_at) * 1000)
    return CommitOutcome(committed_results, len(committed_results), 0, embedding_ms, writing_ms)
