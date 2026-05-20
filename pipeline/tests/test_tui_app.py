import asyncio
import time
from pathlib import Path

import pytest
from textual.widgets import Button, Input

from free_plaud.app.config import Settings
from free_plaud.notes.schemas import Note
from free_plaud.retrieval.models import AskResponse, Citation, UsedSource
from free_plaud.tui.app import ASK_STRATEGIES, AskPane, FreePlaudApp, ask_file


def _settings(tmp_path: Path) -> Settings:
    return Settings(
        workspace_dir=tmp_path,
        data_dir=tmp_path / 'data',
        notes_dir=tmp_path / 'data' / 'corpus' / 'notes',
        datasets_dir=tmp_path / 'data' / 'datasets',
        results_dir=tmp_path / 'data' / 'results',
        sqlite_path=tmp_path / 'data' / 'results' / 'free_plaud.sqlite3',
        vector_store_dir=tmp_path / 'data' / 'results' / 'vector_store',
        vector_collection_name='tui_test',
        embedding_model='fake-hash',
        retrieval_top_k=4,
    )


def _note(path: Path) -> Note:
    return Note(
        note_id='note-tui',
        source_type='md',
        source_path=path,
        source_name=path.name,
        title='Nota TUI',
        summary='Resumo.',
        raw_text='O benchmark mede recall e latencia.',
        normalized_text='O benchmark mede recall e latencia.',
        structured_markdown='# Nota TUI\n\nO benchmark mede recall e latencia.\n',
        content_hash='b' * 64,
    )


def _answer(question: str) -> AskResponse:
    citation = Citation(
        note_id='note-tui',
        note_version=1,
        chunk_id='chunk-1',
        snippet='O benchmark mede recall e latencia.',
        source_path='sample.md',
        char_start=0,
        char_end=35,
    )
    return AskResponse(
        query=question,
        status='answer',
        no_answer=False,
        answer='O benchmark mede recall e latencia.',
        claims=[],
        citations=[citation],
        limitations=[],
        used_sources=[
            UsedSource(doc_id='note-tui', note_version=1, source_path='sample.md', chunk_ids=['chunk-1'])
        ],
        latency_ms=1,
    )


def test_ask_file_exposes_supported_strategies() -> None:
    assert ASK_STRATEGIES == ('lexical', 'vector', 'hybrid')


def test_ask_file_lexical_uses_file_pipeline_without_vector_dependencies(monkeypatch, tmp_path: Path) -> None:
    sample = tmp_path / 'sample.md'
    sample.write_text('# Sample\n\nO benchmark mede recall e latencia.\n', encoding='utf-8')
    captured: dict[str, object] = {}

    monkeypatch.setattr('free_plaud.tui.app.load_document', lambda path: ('document', path))
    monkeypatch.setattr('free_plaud.tui.app.structure_document', lambda document: _note(sample))

    def fail_vector_store(*args, **kwargs):  # noqa: ANN002, ANN003
        raise AssertionError('lexical nao deve inicializar vector store')

    def fail_embedder(*args, **kwargs):  # noqa: ANN002, ANN003
        raise AssertionError('lexical nao deve inicializar embedder')

    def fake_answer_with_citations(note, question, top_k, **kwargs):  # noqa: ANN001, ANN002, ANN003
        captured.update(note=note, question=question, top_k=top_k, kwargs=kwargs)
        return _answer(question)

    monkeypatch.setattr('free_plaud.tui.app.LocalVectorStore', fail_vector_store)
    monkeypatch.setattr('free_plaud.tui.app.get_embedder', fail_embedder)
    monkeypatch.setattr('free_plaud.tui.app.answer_with_citations', fake_answer_with_citations)

    response = ask_file(sample, '  O que o benchmark mede?  ', 'lexical', settings=_settings(tmp_path))

    assert response.status == 'answer'
    assert captured['question'] == 'O que o benchmark mede?'
    assert captured['top_k'] == 4
    assert captured['kwargs'] == {'strategy': 'lexical'}


def test_ask_file_hybrid_initializes_vector_dependencies(monkeypatch, tmp_path: Path) -> None:
    sample = tmp_path / 'sample.md'
    sample.write_text('# Sample\n\nO benchmark mede recall e latencia.\n', encoding='utf-8')
    captured: dict[str, object] = {}

    class FakeVectorStore:
        def __init__(self, path: Path, *, collection_name: str) -> None:
            captured['vector_store_path'] = path
            captured['collection_name'] = collection_name

    class FakeEmbedder:
        model_name = 'fake-hash'

    monkeypatch.setattr('free_plaud.tui.app.load_document', lambda path: ('document', path))
    monkeypatch.setattr('free_plaud.tui.app.structure_document', lambda document: _note(sample))
    monkeypatch.setattr('free_plaud.tui.app.LocalVectorStore', FakeVectorStore)
    monkeypatch.setattr('free_plaud.tui.app.get_embedder', lambda model_name: FakeEmbedder())

    def fake_answer_with_citations(note, question, top_k, **kwargs):  # noqa: ANN001, ANN002, ANN003
        captured.update(note=note, question=question, top_k=top_k, kwargs=kwargs)
        return _answer(question)

    monkeypatch.setattr('free_plaud.tui.app.answer_with_citations', fake_answer_with_citations)

    response = ask_file(sample, 'O que o benchmark mede?', 'hybrid', settings=_settings(tmp_path))

    assert response.status == 'answer'
    assert captured['vector_store_path'] == tmp_path / 'data' / 'results' / 'vector_store'
    assert captured['collection_name'] == 'tui_test'
    assert captured['kwargs']['strategy'] == 'hybrid'  # type: ignore[index]
    assert isinstance(captured['kwargs']['vector_store'], FakeVectorStore)  # type: ignore[index]
    assert isinstance(captured['kwargs']['embedder'], FakeEmbedder)  # type: ignore[index]


def test_ask_file_rejects_invalid_inputs(tmp_path: Path) -> None:
    sample = tmp_path / 'sample.md'
    sample.write_text('# Sample\n\nTexto.\n', encoding='utf-8')

    with pytest.raises(ValueError, match='Pergunta'):
        ask_file(sample, '   ', 'lexical', settings=_settings(tmp_path))

    with pytest.raises(ValueError, match='strategy'):
        ask_file(sample, 'Pergunta?', 'rrf', settings=_settings(tmp_path))  # type: ignore[arg-type]

    with pytest.raises(FileNotFoundError):
        ask_file(tmp_path / 'missing.md', 'Pergunta?', 'lexical', settings=_settings(tmp_path))


def test_tui_ask_button_runs_worker_and_renders_response(monkeypatch, tmp_path: Path) -> None:
    sample = tmp_path / 'sample.md'
    sample.write_text('# Sample\n\nTexto.\n', encoding='utf-8')
    captured: dict[str, object] = {}

    def fake_ask_file(file_path: Path, question: str, strategy: str) -> AskResponse:
        captured.update(file_path=file_path, question=question, strategy=strategy)
        return _answer(question)

    monkeypatch.setattr('free_plaud.tui.app.ask_file', fake_ask_file)

    async def run_app() -> None:
        app = FreePlaudApp()
        async with app.run_test(size=(100, 30)) as pilot:
            app.query_one('#ask-file-path', Input).value = str(sample)
            app.query_one('#ask-question', Input).value = 'O que o benchmark mede?'
            await pilot.click('#strategy-lexical')
            await pilot.click('#ask-submit')
            await pilot.pause(0.5)

    asyncio.run(run_app())

    assert captured == {
        'file_path': sample,
        'question': 'O que o benchmark mede?',
        'strategy': 'lexical',
    }


def test_tui_strategy_defaults_to_hybrid_and_updates_active_button() -> None:
    async def run_app() -> None:
        app = FreePlaudApp()
        async with app.run_test(size=(100, 30)) as pilot:
            ask_pane = app.query_one(AskPane)
            assert ask_pane.selected_strategy == 'hybrid'
            assert app.query_one('#strategy-hybrid', Button).has_class('strategy-active')

            await pilot.click('#strategy-vector')
            assert ask_pane.selected_strategy == 'vector'
            assert app.query_one('#strategy-vector', Button).has_class('strategy-active')
            assert not app.query_one('#strategy-hybrid', Button).has_class('strategy-active')

    asyncio.run(run_app())


def test_tui_ask_button_ignores_double_click_while_running(monkeypatch, tmp_path: Path) -> None:
    sample = tmp_path / 'sample.md'
    sample.write_text('# Sample\n\nTexto.\n', encoding='utf-8')
    calls: list[str] = []

    def fake_ask_file(file_path: Path, question: str, strategy: str) -> AskResponse:
        calls.append(strategy)
        time.sleep(0.3)
        return _answer(question)

    monkeypatch.setattr('free_plaud.tui.app.ask_file', fake_ask_file)

    async def run_app() -> None:
        app = FreePlaudApp()
        async with app.run_test(size=(100, 30)) as pilot:
            app.query_one('#ask-file-path', Input).value = str(sample)
            app.query_one('#ask-question', Input).value = 'O que o benchmark mede?'
            await pilot.click('#ask-submit')
            await pilot.click('#ask-submit')
            await pilot.pause(0.8)
            assert not app.query_one('#ask-submit', Button).disabled

    asyncio.run(run_app())

    assert calls == ['hybrid']


def test_tui_ask_button_restores_state_after_worker_error(monkeypatch, tmp_path: Path) -> None:
    sample = tmp_path / 'sample.md'
    sample.write_text('# Sample\n\nTexto.\n', encoding='utf-8')

    def fail_ask_file(file_path: Path, question: str, strategy: str) -> AskResponse:
        raise FileNotFoundError('arquivo quebrado')

    monkeypatch.setattr('free_plaud.tui.app.ask_file', fail_ask_file)

    async def run_app() -> None:
        app = FreePlaudApp()
        async with app.run_test(size=(100, 30)) as pilot:
            app.query_one('#ask-file-path', Input).value = str(sample)
            app.query_one('#ask-question', Input).value = 'O que o benchmark mede?'
            await pilot.click('#ask-submit')
            await pilot.pause(0.5)
            submit = app.query_one('#ask-submit', Button)
            assert not submit.disabled
            assert str(submit.label) == 'Executar ask'

    asyncio.run(run_app())


def test_tui_layout_mounts_at_supported_sizes() -> None:
    async def run_app() -> None:
        for size in ((80, 24), (100, 30), (120, 36)):
            app = FreePlaudApp()
            async with app.run_test(size=size) as pilot:
                await pilot.pause()
                assert app.query_one('#nav-panel')
                assert app.query_one('#ask-form-card')
                assert app.query_one('#ask-result-card')

    asyncio.run(run_app())
