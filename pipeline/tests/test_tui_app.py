import asyncio
import threading
from pathlib import Path

import pytest
from textual.widgets import Button, Input

from free_plaud.app.config import Settings
from free_plaud.corpus.models import (
    CorpusDiscoveryResult,
    CorpusIndexBatchResult,
    CorpusResetResult,
    CorpusSkippedPath,
    CorpusStatusResult,
)
from free_plaud.notes.schemas import Note
from free_plaud.retrieval.models import AskResponse, Citation, UsedSource
from free_plaud.tui.app import (
    ASK_MODES,
    ASK_STRATEGIES,
    COMPACT_WIDTH,
    ActionCell,
    AskPane,
    FreePlaudApp,
    _bullet_help,
    ask_file,
)


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
    assert ASK_MODES == ('corpus', 'file')


def test_tui_help_text_uses_spaced_bullets() -> None:
    assert _bullet_help('Ask item.', 'Notes item.', 'Benchmark item.') == (
        '- Ask item.\n\n- Notes item.\n\n- Benchmark item.'
    )


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


def test_tui_ask_button_runs_corpus_by_default(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_ask_corpus(question: str, strategy: str) -> AskResponse:
        captured.update(question=question, strategy=strategy)
        return _answer(question)

    monkeypatch.setattr('free_plaud.tui.app.ask_corpus', fake_ask_corpus)

    async def run_app() -> None:
        app = FreePlaudApp()
        async with app.run_test(size=(100, 30)) as pilot:
            app.query_one('#ask-question', Input).value = 'O que o benchmark mede?'
            await pilot.click('#ask-submit')
            await pilot.pause(0.5)

    asyncio.run(run_app())

    assert captured == {
        'question': 'O que o benchmark mede?',
        'strategy': 'hybrid',
    }


def test_tui_ask_button_runs_file_mode_when_selected(monkeypatch, tmp_path: Path) -> None:
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
            await pilot.click('#mode-file')
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
            assert ask_pane.selected_mode == 'corpus'
            assert app.query_one('#mode-corpus', ActionCell).has_class('strategy-active')
            assert app.query_one('#strategy-hybrid', ActionCell).has_class('strategy-active')

            await pilot.click('#strategy-vector')
            assert ask_pane.selected_strategy == 'vector'
            assert app.query_one('#strategy-vector', ActionCell).has_class('strategy-active')
            assert not app.query_one('#strategy-hybrid', ActionCell).has_class('strategy-active')

            await pilot.click('#mode-file')
            assert ask_pane.selected_mode == 'file'
            assert app.query_one('#mode-file', ActionCell).has_class('strategy-active')
            assert not app.query_one('#mode-corpus', ActionCell).has_class('strategy-active')

    asyncio.run(run_app())


def test_tui_ask_button_ignores_double_click_while_running(monkeypatch, tmp_path: Path) -> None:
    sample = tmp_path / 'sample.md'
    sample.write_text('# Sample\n\nTexto.\n', encoding='utf-8')
    calls: list[str] = []
    started = threading.Event()
    release = threading.Event()

    def fake_ask_corpus(question: str, strategy: str) -> AskResponse:
        calls.append(strategy)
        started.set()
        release.wait(timeout=2)
        return _answer(question)

    monkeypatch.setattr('free_plaud.tui.app.ask_corpus', fake_ask_corpus)

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
            assert not app.query_one('#ask-submit', ActionCell).disabled

    asyncio.run(run_app())

    assert calls == ['hybrid']


def test_tui_ask_button_restores_state_after_worker_error(monkeypatch, tmp_path: Path) -> None:
    sample = tmp_path / 'sample.md'
    sample.write_text('# Sample\n\nTexto.\n', encoding='utf-8')

    def fail_ask_corpus(question: str, strategy: str) -> AskResponse:
        raise FileNotFoundError('arquivo quebrado')

    monkeypatch.setattr('free_plaud.tui.app.ask_corpus', fail_ask_corpus)

    async def run_app() -> None:
        app = FreePlaudApp()
        async with app.run_test(size=(100, 30)) as pilot:
            app.query_one('#ask-file-path', Input).value = str(sample)
            app.query_one('#ask-question', Input).value = 'O que o benchmark mede?'
            await pilot.click('#ask-submit')
            await pilot.pause(0.5)
            submit = app.query_one('#ask-submit', ActionCell)
            assert not submit.disabled
            assert str(submit.content) == 'Perguntar'

    asyncio.run(run_app())


def test_tui_clear_button_resets_ask_response(monkeypatch) -> None:
    calls = 0

    def fake_ask_corpus(question: str, strategy: str) -> AskResponse:
        nonlocal calls
        calls += 1
        return _answer(question)

    monkeypatch.setattr('free_plaud.tui.app.ask_corpus', fake_ask_corpus)

    async def run_app() -> None:
        app = FreePlaudApp()
        async with app.run_test(size=(100, 30)) as pilot:
            app.query_one('#ask-question', Input).value = 'O que o benchmark mede?'
            await pilot.click('#ask-submit')
            await pilot.pause(0.5)
            await pilot.click('#ask-clear')
            await pilot.pause(0.1)
            assert not app.query_one('#ask-clear', ActionCell).disabled

    asyncio.run(run_app())

    assert calls == 1


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
                for selector in (
                    '#strategy-lexical',
                    '#strategy-vector',
                    '#strategy-hybrid',
                    '#ask-submit',
                    '#ask-clear',
                ):
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
            assert app.query_one('#strategy-row').region.height == 3
            assert app.query_one('#strategy-lexical').region.y == app.query_one('#strategy-hybrid').region.y
            for selector in (
                '#nav-panel',
                '#ask-form-card',
                '#strategy-lexical',
                '#strategy-vector',
                '#strategy-hybrid',
                '#mode-corpus',
                '#mode-file',
                '#ask-submit',
                '#ask-clear',
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

    def assert_not_pure_white(control) -> None:
        color = control.styles.color
        assert (color.r, color.g, color.b) != pure_white

    def assert_no_chrome(control) -> None:
        assert all(edge[0] == '' for edge in control.styles.border)
        assert all(edge[0] == '' for edge in control.styles.outline)

    async def run_app() -> None:
        app = FreePlaudApp()
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            assert {button.active_effect_duration for button in app.query(Button)} == {0}
            assert all(not control.has_class('-active') for control in app.query(ActionCell))
            assert app.query_one('#nav-ask', Button).styles.outline.left is not None

            await pilot.click('#nav-notes')
            await pilot.pause(0.05)
            assert not app.query_one('#nav-notes', Button).has_class('-active')
            assert app.query_one('#nav-notes', Button).styles.outline.left is not None

            await pilot.click('#nav-ask')
            for selector in (
                '#mode-corpus',
                '#mode-file',
                '#strategy-lexical',
                '#strategy-vector',
                '#strategy-hybrid',
                '#ask-submit',
                '#ask-clear',
            ):
                control = app.query_one(selector, ActionCell)
                control.focus()
                await pilot.pause(0.05)
                assert_not_pure_white(control)
                assert not control.has_class('-active')
                assert_no_chrome(control)

    asyncio.run(run_app())


def test_tui_notes_can_index_folder_and_reset_with_confirmation(monkeypatch, tmp_path: Path) -> None:
    captured: dict[str, object] = {}

    def fake_index_folder(path: Path, *, rebuild: bool) -> CorpusIndexBatchResult:
        captured['index_path'] = path
        captured['rebuild'] = rebuild
        return CorpusIndexBatchResult(
            source_path=str(path),
            recursive=True,
            status='success',
            total_found=2,
            indexed_count=2,
            failed_count=0,
            skipped_count=0,
            results=[],
        )

    def fake_reset(confirm: str) -> CorpusResetResult:
        captured['reset_confirm'] = confirm
        return CorpusResetResult(
            dry_run=False,
            would_delete_notes=1,
            would_delete_chunks=2,
            would_delete_vectors=3,
            deleted_notes=1,
            deleted_chunks=2,
            deleted_vectors=3,
            status='reset',
        )

    monkeypatch.setattr('free_plaud.tui.app.index_corpus_folder', fake_index_folder)
    monkeypatch.setattr('free_plaud.tui.app.reset_corpus_from_tui', fake_reset)
    monkeypatch.setattr(
        'free_plaud.tui.app.corpus_status_from_tui',
        lambda: CorpusStatusResult(
            sqlite_path='db',
            vector_store_dir='vec',
            vector_collection_name='test',
            notes_count=0,
            sqlite_chunks_count=0,
            vector_chunks_count=0,
            stale_vector_chunks_count=0,
            missing_vector_chunks_count=0,
            status='empty',
        ),
    )
    monkeypatch.setattr('free_plaud.tui.app.list_corpus_notes', lambda: [])

    async def run_app() -> None:
        app = FreePlaudApp()
        async with app.run_test(size=(120, 36)) as pilot:
            await pilot.click('#nav-notes')
            await pilot.pause(0.1)
            app.query_one('#notes-folder-path', Input).value = str(tmp_path)
            await pilot.click('#notes-index')
            await pilot.pause(0.5)
            app.query_one('#notes-reset-confirm', Input).value = 'LIMPAR'
            await pilot.click('#notes-reset')
            await pilot.pause(0.5)

    asyncio.run(run_app())

    assert captured['index_path'] == tmp_path
    assert captured['rebuild'] is False
    assert captured['reset_confirm'] == 'LIMPAR'


def test_tui_notes_rejects_empty_folder_before_index(monkeypatch) -> None:
    calls = 0

    def fake_index_folder(path: Path, *, rebuild: bool) -> CorpusIndexBatchResult:
        nonlocal calls
        calls += 1
        raise AssertionError('indexacao nao deve iniciar com pasta vazia')

    monkeypatch.setattr('free_plaud.tui.app.index_corpus_folder', fake_index_folder)

    async def run_app() -> None:
        app = FreePlaudApp()
        async with app.run_test(size=(120, 36)) as pilot:
            await pilot.click('#nav-notes')
            await pilot.pause(0.1)
            await pilot.click('#notes-index')
            await pilot.pause(0.3)
            assert not app.query_one('#notes-index', ActionCell).disabled

    asyncio.run(run_app())

    assert calls == 0


def test_tui_notes_runs_preflight_before_index(monkeypatch, tmp_path: Path) -> None:
    events: list[tuple[str, object]] = []

    def fake_preflight_folder(path: str) -> CorpusDiscoveryResult:
        events.append(('preflight', path))
        return CorpusDiscoveryResult(
            root_path=str(tmp_path),
            recursive=True,
            files=[tmp_path / 'nota.md', tmp_path / 'nested' / 'aula.txt'],
            skipped=[CorpusSkippedPath(path=str(tmp_path / 'image.png'), reason='unsupported_extension')],
        )

    def fake_index_folder(path: Path, *, rebuild: bool) -> CorpusIndexBatchResult:
        events.append(('index', path))
        return CorpusIndexBatchResult(
            source_path=str(path),
            recursive=True,
            status='success',
            total_found=2,
            indexed_count=2,
            failed_count=0,
            skipped_count=1,
            results=[],
        )

    monkeypatch.setattr('free_plaud.tui.app.preflight_corpus_folder', fake_preflight_folder)
    monkeypatch.setattr('free_plaud.tui.app.index_corpus_folder', fake_index_folder)
    monkeypatch.setattr(
        'free_plaud.tui.app.corpus_status_from_tui',
        lambda: CorpusStatusResult(
            sqlite_path='db',
            vector_store_dir='vec',
            vector_collection_name='test',
            notes_count=0,
            sqlite_chunks_count=0,
            vector_chunks_count=0,
            stale_vector_chunks_count=0,
            missing_vector_chunks_count=0,
            status='empty',
        ),
    )
    monkeypatch.setattr('free_plaud.tui.app.list_corpus_notes', lambda: [])

    async def run_app() -> None:
        app = FreePlaudApp()
        async with app.run_test(size=(120, 36)) as pilot:
            await pilot.click('#nav-notes')
            await pilot.pause(0.1)
            app.query_one('#notes-folder-path', Input).value = str(tmp_path)
            await pilot.click('#notes-index')
            await pilot.pause(0.5)

    asyncio.run(run_app())

    assert events == [
        ('preflight', str(tmp_path)),
        ('index', tmp_path),
    ]


def test_tui_reset_requires_literal_confirmation(monkeypatch) -> None:
    calls = 0

    def fake_reset(confirm: str) -> CorpusResetResult:
        nonlocal calls
        calls += 1
        return CorpusResetResult(dry_run=False, would_delete_notes=0, would_delete_chunks=0, would_delete_vectors=0)

    monkeypatch.setattr('free_plaud.tui.app.reset_corpus_from_tui', fake_reset)

    async def run_app() -> None:
        app = FreePlaudApp()
        async with app.run_test(size=(120, 36)) as pilot:
            await pilot.click('#nav-notes')
            await pilot.pause(0.1)
            app.query_one('#notes-reset-confirm', Input).value = 'limpar'
            await pilot.click('#notes-reset')
            await pilot.pause(0.3)

    asyncio.run(run_app())

    assert calls == 0


def test_tui_benchmark_runs_suite_comparison(monkeypatch, tmp_path: Path) -> None:
    captured: dict[str, object] = {}

    class Summary:
        def __init__(self, strategy: str) -> None:
            self.strategy = strategy
            self.query_count = 4
            self.mrr = 1.0
            self.recall_at_3 = 1.0
            self.duration_ms = 10
            self.avg_query_latency_ms = 2.5

    class Result:
        comparison_id = 'cmp-test'
        suite_name = 'suite-test'
        summaries = {
            'lexical': Summary('lexical'),
            'vector': Summary('vector'),
            'hybrid': Summary('hybrid'),
        }

    def fake_compare(path: Path):
        captured['suite_path'] = path
        return Result()

    monkeypatch.setattr('free_plaud.tui.app.compare_suite_from_tui', fake_compare)

    async def run_app() -> None:
        app = FreePlaudApp()
        async with app.run_test(size=(120, 36)) as pilot:
            await pilot.click('#nav-benchmark')
            await pilot.pause(0.1)
            app.query_one('#benchmark-suite-path', Input).value = str(tmp_path / 'suite.json')
            await pilot.click('#benchmark-run')
            await pilot.pause(0.5)

    asyncio.run(run_app())

    assert captured['suite_path'] == tmp_path / 'suite.json'
