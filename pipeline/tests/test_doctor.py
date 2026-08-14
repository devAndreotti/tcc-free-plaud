from pathlib import Path

from free_plaud.app.config import Settings
from free_plaud.app.doctor import run_doctor
from free_plaud.retrieval.models import Chunk
from free_plaud.storage.sqlite import init_sqlite
from free_plaud.storage.vector import LocalVectorStore


def _settings(tmp_path: Path, **overrides: object) -> Settings:
    values = {
        'workspace_dir': tmp_path,
        'data_dir': tmp_path / 'data',
        'notes_dir': tmp_path / 'data' / 'corpus' / 'notes',
        'datasets_dir': tmp_path / 'data' / 'datasets',
        'results_dir': tmp_path / 'data' / 'results',
        'sqlite_path': tmp_path / 'data' / 'results' / 'free_plaud.sqlite3',
        'vector_store_dir': tmp_path / 'data' / 'results' / 'vector_store',
        'vector_collection_name': 'doctor_test_chunks',
        'embedding_model': 'chroma-default',
        'embedding_device': 'cpu',
        'answer_provider': 'extractive',
    }
    values.update(overrides)
    return Settings(**values)


def _chunk(chunk_id: str, note_id: str, text: str) -> Chunk:
    return Chunk(
        chunk_id=chunk_id,
        note_id=note_id,
        note_version=1,
        chunk_index=0,
        char_start=0,
        char_end=len(text),
        chunk_size=800,
        overlap=120,
        chunk_text=text,
        token_count=len(text.split()),
        strategy='fixed_window',
        normalized_text_sha256=f'{chunk_id}-normalized',
        text_sha256=f'{chunk_id}-text',
        pipeline_version='test',
    )


def _by_code(report) -> dict[str, object]:
    return {check.code: check for check in report.checks}


def test_doctor_reports_fake_hash_as_error_without_leaking_secrets(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv('FREE_PLAUD_ANSWER_API_KEY', raising=False)
    settings = _settings(
        tmp_path,
        embedding_model='fake-hash',
        answer_provider='openai-compatible',
        answer_api_key='sk-should-not-leak',
    )

    report = run_doctor(settings=settings)

    checks = _by_code(report)
    assert report.status == 'error'
    assert checks['settings.embedding_model'].status == 'error'  # type: ignore[attr-defined]
    assert checks['api_key'].status == 'ok'  # type: ignore[attr-defined]
    assert 'sk-should-not-leak' not in report.model_dump_json()


def test_doctor_warns_for_chroma_default_cuda_but_keeps_embedding_model_ok(tmp_path: Path) -> None:
    report = run_doctor(settings=_settings(tmp_path, embedding_model='chroma-default', embedding_device='cuda'))

    checks = _by_code(report)
    assert report.status == 'warning'
    assert checks['settings.embedding_model'].status == 'ok'  # type: ignore[attr-defined]
    assert checks['settings.embedding_device'].status == 'warning'  # type: ignore[attr-defined]


def test_doctor_errors_when_sentence_transformer_cuda_is_unavailable(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr('free_plaud.providers.embed._cuda_available', lambda: False)

    report = run_doctor(
        settings=_settings(
            tmp_path,
            embedding_model='sentence-transformer:sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2',
            embedding_device='cuda',
        )
    )

    checks = _by_code(report)
    assert report.status == 'error'
    assert checks['settings.embedding_device'].status == 'error'  # type: ignore[attr-defined]
    assert 'CUDA indisponivel' in checks['settings.embedding_device'].message  # type: ignore[attr-defined]


def test_doctor_keeps_extractive_without_api_key_ok_and_warns_for_remote_provider(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv('FREE_PLAUD_ANSWER_API_KEY', raising=False)

    extractive = run_doctor(settings=_settings(tmp_path / 'extractive', answer_provider='extractive'))
    remote = run_doctor(
        settings=_settings(tmp_path / 'remote', answer_provider='openai-compatible', answer_api_key=None)
    )

    assert _by_code(extractive)['api_key'].status == 'ok'  # type: ignore[attr-defined]
    assert _by_code(remote)['api_key'].status == 'warning'  # type: ignore[attr-defined]


def test_doctor_reports_corpus_inconsistency(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    connection = init_sqlite(settings.sqlite_path)
    vector_store = LocalVectorStore(settings.vector_store_dir, collection_name=settings.vector_collection_name)
    stale_chunk = _chunk('stale-chunk-1', 'stale-note', 'Conteudo sem linha equivalente no SQLite.')
    vector_store.upsert_chunks([stale_chunk], [[1.0] + [0.0] * 15], embedding_model='fake-hash')

    try:
        report = run_doctor(settings=settings, connection=connection, vector_store=vector_store)
    finally:
        connection.close()

    corpus = _by_code(report)['corpus']
    assert report.status == 'error'
    assert corpus.status == 'error'  # type: ignore[attr-defined]
    assert corpus.details['status'] == 'inconsistent'  # type: ignore[attr-defined]
    assert corpus.details['stale_vector_chunks_count'] == 1  # type: ignore[attr-defined]


def test_doctor_returns_structured_errors_when_corpus_status_crashes(tmp_path: Path, monkeypatch) -> None:
    def broken_corpus_status(**kwargs):
        _ = kwargs
        raise RuntimeError('chroma indisponivel')

    monkeypatch.setattr('free_plaud.app.doctor_corpus.get_corpus_status', broken_corpus_status)

    report = run_doctor(settings=_settings(tmp_path))

    checks = _by_code(report)
    assert report.status == 'error'
    assert checks['fts'].status == 'error'  # type: ignore[attr-defined]
    assert checks['corpus'].status == 'error'  # type: ignore[attr-defined]
    assert 'chroma indisponivel' in checks['corpus'].message  # type: ignore[attr-defined]
