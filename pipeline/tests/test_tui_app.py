import asyncio
import threading
from pathlib import Path

import pytest
from textual.widgets import Button, Input

from free_plaud.app.config import Settings
from free_plaud.notes.schemas import Note
from free_plaud.retrieval.models import AskResponse, Citation, UsedSource
from free_plaud.tui.app import ASK_STRATEGIES, COMPACT_WIDTH, AskPane, FreePlaudApp, ask_file


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
    started = threading.Event()
    release = threading.Event()

    def fake_ask_file(file_path: Path, question: str, strategy: str) -> AskResponse:
        calls.append(strategy)
        started.set()
        release.wait(timeout=2)
        return _answer(question)

    monkeypatch.setattr('free_plaud.tui.app.ask_file', fake_ask_file)

    async def run_app() -> None:
        app = FreePlaudApp()
        async with app.run_test(size=(100, 30)) as pilot:
            app.query_one('#ask-file-path', Input).value = str(sample)
            app.query_one('#ask-question', Input).value = 'O que o benchmark mede?'
            await pilot.click('#ask-submit')
            assert await asyncio.to_thread(started.wait, 2)
            await pilot.click('#ask-submit')
            release.set()
            await pilot.pause(0.5)
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
            assert str(submit.label) == 'Perguntar'

    asyncio.run(run_app())


def test_tui_layout_mounts_at_supported_sizes() -> None:
    def assert_inside(parent, child) -> None:  # noqa: ANN001
        parent_region = parent.region
        child_region = child.region
        assert child_region.x >= parent_region.x
        assert child_region.y >= parent_region.y
        assert child_region.x + child_region.width <= parent_region.x + parent_region.width
        assert child_region.y + child_region.height < parent_region.y + parent_region.height

    async def run_app() -> None:
        for size in ((80, 24), (100, 30), (120, 36)):
            app = FreePlaudApp()
            async with app.run_test(size=size) as pilot:
                await pilot.pause()
                form_card = app.query_one('#ask-form-card')
                assert app.query_one('#nav-panel')
                assert form_card
                assert app.query_one('#ask-result-card')
                for selector in ('#strategy-lexical', '#strategy-vector', '#strategy-hybrid', '#ask-submit'):
                    assert_inside(form_card, app.query_one(selector))

    asyncio.run(run_app())


def test_tui_layout_reflows_when_terminal_resizes() -> None:
    def assert_visible(app: FreePlaudApp, selector: str) -> None:
        region = app.query_one(selector).region
        assert region.x >= 0
        assert region.y >= 0
        assert region.x + region.width <= app.size.width
        assert region.y + region.height <= app.size.height

    async def run_app() -> None:
        app = FreePlaudApp()
        async with app.run_test(size=(120, 36)) as pilot:
            await pilot.pause()
            assert not app.screen.has_class('compact')
            assert app.size.width >= COMPACT_WIDTH
            assert app.query_one('#strategy-row').region.height == 3
            assert app.query_one('#strategy-lexical').region.y == app.query_one('#strategy-hybrid').region.y

            await pilot.resize_terminal(80, 24)
            await pilot.pause(0.3)
            assert app.screen.has_class('compact')
            assert app.size.width < COMPACT_WIDTH
            assert app.query_one('#strategy-row').region.height == 6
            assert app.query_one('#strategy-hybrid').region.y > app.query_one('#strategy-lexical').region.y
            for selector in (
                '#nav-panel',
                '#ask-form-card',
                '#strategy-lexical',
                '#strategy-vector',
                '#strategy-hybrid',
                '#ask-submit',
                '#ask-result-card',
            ):
                assert_visible(app, selector)

            await pilot.resize_terminal(120, 36)
            await pilot.pause(0.3)
            assert not app.screen.has_class('compact')
            assert app.query_one('#strategy-row').region.height == 3

    asyncio.run(run_app())


def test_tui_buttons_do_not_use_default_active_flash() -> None:
    pure_white = (248, 240, 255)

    def assert_not_pure_white(button: Button) -> None:
        color = button.styles.color
        assert (color.r, color.g, color.b) != pure_white

    def assert_border_rgb(button: Button, rgb: tuple[int, int, int]) -> None:
        color = button.styles.border.top[1]
        assert (color.r, color.g, color.b) == rgb

    async def run_app() -> None:
        app = FreePlaudApp()
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            assert {button.active_effect_duration for button in app.query(Button)} == {0}
            assert app.query_one('#nav-ask', Button).styles.outline.left is not None

            await pilot.click('#nav-notes')
            await pilot.pause(0.05)
            assert not app.query_one('#nav-notes', Button).has_class('-active')
            assert app.query_one('#nav-notes', Button).styles.outline.left is not None

            await pilot.click('#nav-ask')
            for selector in ('#strategy-lexical', '#strategy-vector', '#strategy-hybrid', '#ask-submit'):
                button = app.query_one(selector, Button)
                button.focus()
                await pilot.pause(0.05)
                assert_not_pure_white(button)
                assert not button.has_class('-active')
                expected_border = (126, 34, 206) if selector == '#ask-submit' else (56, 35, 77)
                assert_border_rgb(button, expected_border)

    asyncio.run(run_app())
