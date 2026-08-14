from pathlib import Path
from typing import Literal

from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from textual import events, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Vertical
from textual.geometry import Size
from textual.message import Message
from textual.widgets import (
    Button,
    Footer,
    Header,
    Input,
    Label,
    RichLog,
    Select,
    Static,
)

from free_plaud.app.config import (
    Settings,
    get_settings,
    reset_user_settings,
    save_user_settings,
    user_settings_path_for,
)
from free_plaud.app.doctor import run_doctor
from free_plaud.app.doctor_format import doctor_report_text
from free_plaud.app.local_env import (
    answer_api_key_is_configured,
    local_env_path_for,
    save_answer_api_key,
)
from free_plaud.app.settings_catalog import settings_catalog_payload
from free_plaud.app.settings_presets import apply_settings_preset, list_settings_presets
from free_plaud.corpus.cancellation import CancellationToken
from free_plaud.corpus.models import CorpusDiscoveryResult, CorpusIndexProgress
from free_plaud.corpus.runtime import CorpusRuntime
from free_plaud.ingest.loaders import load_document
from free_plaud.notes.structurer import structure_document
from free_plaud.providers.answer import test_answer_provider
from free_plaud.providers.embed import get_embedder
from free_plaud.providers.model_discovery import list_answer_models
from free_plaud.providers.provisioning import detect_runtime, runtime_hint
from free_plaud.retrieval.models import AskResponse
from free_plaud.retrieval.rag import answer_with_citations
from free_plaud.storage.vector import LocalVectorStore
from free_plaud.tui.actions import (
    ask_corpus,
    compare_suite_from_tui,
    corpus_status_from_tui,
    index_corpus_folder,
    list_corpus_notes,
    preflight_corpus_folder,
    reset_corpus_from_tui,
)

AskMode = Literal['corpus', 'file']
AskStrategy = Literal['lexical', 'vector', 'hybrid']
ASK_MODES: tuple[AskMode, ...] = ('corpus', 'file')
ASK_STRATEGIES: tuple[AskStrategy, ...] = ('lexical', 'vector', 'hybrid')
COMPACT_WIDTH = 92


def _bullet_help(*items: str) -> str:
    return '\n\n'.join(f'- {item}' for item in items)


def ask_file(
    file_path: Path | str,
    question: str,
    strategy: AskStrategy,
    *,
    settings: Settings | None = None,
    runtime: CorpusRuntime | None = None,
) -> AskResponse:
    """Executa o fluxo Ask sobre um arquivo local, sem persistir nota em SQLite."""
    cleaned_question = question.strip()
    if not cleaned_question:
        raise ValueError('Pergunta vazia.')
    if strategy not in ASK_STRATEGIES:
        raise ValueError("strategy deve ser 'lexical', 'vector' ou 'hybrid'.")

    resolved_path = Path(file_path).expanduser()
    if not resolved_path.exists():
        raise FileNotFoundError(f'Arquivo nao encontrado: {resolved_path}')

    resolved_settings = settings or get_settings()
    document = load_document(resolved_path)
    note = structure_document(document)

    if strategy == 'lexical':
        return answer_with_citations(
            note,
            cleaned_question,
            resolved_settings.retrieval_top_k,
            strategy=strategy,
        )

    if runtime is not None:
        vector_store = runtime.get_vector_store()
        embedder = runtime.get_embedder()
    else:
        vector_store = LocalVectorStore(
            resolved_settings.vector_store_dir,
            collection_name=resolved_settings.vector_collection_name,
        )
        embedder = get_embedder(resolved_settings.embedding_model, device=resolved_settings.embedding_device)
    return answer_with_citations(
        note,
        cleaned_question,
        resolved_settings.retrieval_top_k,
        strategy=strategy,
        vector_store=vector_store,
        embedder=embedder,
    )


def _short_path(path: str | None, max_length: int = 56) -> str:
    if not path or len(path) <= max_length:
        return path or ''
    return '...' + path[-(max_length - 3) :]


def _progress_rate_and_eta(progress: CorpusIndexProgress) -> tuple[str, str]:
    if progress.processed_count <= 0 or progress.elapsed_ms <= 0:
        return '-', '-'
    elapsed_seconds = progress.elapsed_ms / 1000
    rate = progress.processed_count / elapsed_seconds
    rate_text = f'{rate:.2f}/s'
    if progress.total_found <= progress.processed_count or rate <= 0:
        return rate_text, '-'
    eta_seconds = int((progress.total_found - progress.processed_count) / rate)
    minutes, seconds = divmod(max(eta_seconds, 0), 60)
    return rate_text, f'{minutes:02d}:{seconds:02d}'


def _settings_summary(settings: Settings) -> str:
    rows = settings_catalog_payload(settings)
    core_keys = {'retrieval_top_k', 'default_chunk_size', 'default_chunk_overlap', 'embedding_model'}
    lines = [f'{row["label"]}: {row["display_value"]}' for row in rows if row['key'] in core_keys]
    warnings = [row['warning'] for row in rows if row['warning']]
    if warnings:
        lines.append('')
        lines.extend(f'- {warning}' for warning in warnings if warning)
    return '\n'.join(lines)


def _settings_status_message(settings: Settings, doctor_text: str) -> str:
    return (
        f'user_settings={user_settings_path_for(settings)}\n'
        f'local_env={local_env_path_for(settings)}\n'
        f'answer_api_key={"configurada" if answer_api_key_is_configured(settings=settings) else "ausente"}\n\n'
        f'{_settings_summary(settings)}\n\n'
        f'Doctor\n{doctor_text}'
    )


def _provider_test_message(result, hint: str | None = None) -> str:
    lines = [
        f'provider={result.provider}',
        f'model={result.model}',
        f'base_url={result.base_url}',
        f'status={result.status}',
        f'latencia_ms={result.latency_ms}',
        f'erro={result.error or "-"}',
    ]
    if hint:
        lines.extend(['', hint])
    return '\n'.join(lines)


def _model_discovery_message(result) -> str:
    lines = [
        f'provider={result.provider}',
        f'base_url={result.base_url or "-"}',
        f'status={result.status}',
        f'latencia_ms={result.latency_ms}',
        f'cached={result.cached}',
        f'mensagem={result.message or "-"}',
    ]
    if result.models:
        lines.extend(['', 'Modelos:'])
        lines.extend(f'- {model.label}' for model in result.models)
        lines.extend(['', 'Copie um modelo para answer_model e clique Salvar.'])
    return '\n'.join(lines)


class ActionCell(Static, can_focus=True):
    class Pressed(Message):
        def __init__(self, cell: 'ActionCell') -> None:
            super().__init__()
            self.cell = cell

    BINDINGS = [
        Binding('enter', 'press', 'Ativar', show=False),
        Binding('space', 'press', 'Ativar', show=False),
    ]

    def on_click(self, event: events.Click) -> None:
        event.stop()
        self.action_press()

    def action_press(self) -> None:
        if not self.disabled:
            self.post_message(self.Pressed(self))


class NavPanel(Vertical):
    def compose(self) -> ComposeResult:
        settings = get_settings()
        yield Static('free-plaud', id='nav-brand')
        yield Static('RAG local', id='nav-subtitle')
        with Vertical(id='nav-actions'):
            yield Button('Ask', id='nav-ask', classes='nav-button nav-active')
            yield Button('Notes', id='nav-notes', classes='nav-button')
            yield Button('Benchmark', id='nav-benchmark', classes='nav-button')
            yield Button('Settings', id='nav-settings', classes='nav-button')
        with Vertical(id='nav-meta'):
            yield Static('modelo', classes='nav-meta-label')
            yield Static(settings.embedding_model, id='nav-meta-model', classes='nav-meta-value')
            yield Static('device', classes='nav-meta-label')
            yield Static(settings.embedding_device, id='nav-meta-device', classes='nav-meta-value')
            yield Static('top_k', classes='nav-meta-label')
            yield Static(str(settings.retrieval_top_k), id='nav-meta-top-k', classes='nav-meta-value')


class AskPane(Vertical):
    selected_mode: AskMode
    selected_strategy: AskStrategy
    _ask_running: bool

    def __init__(self, **kwargs: object) -> None:
        super().__init__(**kwargs)
        settings = get_settings()
        self.selected_mode = 'corpus'
        self.selected_strategy = settings.default_ask_strategy
        self._ask_running = False

    def compose(self) -> ComposeResult:
        with Container(id='ask-hero'):
            yield Static('Ask local', classes='hero-title')
            yield Static('Pergunte contra o corpus indexado ou contra um arquivo isolado.', classes='hero-subtitle')

        with Container(id='ask-form-card'):
            yield Static('Consulta', classes='card-title')
            yield Label('Modo', id='mode-label')
            with Container(id='mode-row'):
                yield ActionCell('Corpus', id='mode-corpus', classes='strategy-button strategy-active')
                yield ActionCell('Arquivo', id='mode-file', classes='strategy-button')
            with Container(id='ask-input-row'):
                with Container(id='ask-file-field', classes='ask-field'):
                    yield Label('Arquivo', id='file-label')
                    yield Input(placeholder=r'D:\caminho\arquivo.md', id='ask-file-path')
                with Container(id='ask-question-field', classes='ask-field'):
                    yield Label('Pergunta', id='question-label')
                    yield Input(placeholder='O que este documento diz?', id='ask-question')
            yield Label('Estrategia', id='strategy-label')
            with Container(id='ask-control-row'):
                for strategy in ASK_STRATEGIES:
                    label = strategy.capitalize()
                    classes = 'strategy-button strategy-active' if strategy == self.selected_strategy else 'strategy-button'
                    yield ActionCell(label, id=f'strategy-{strategy}', classes=classes)
                yield ActionCell('Perguntar', id='ask-submit', classes='primary-action')
                yield ActionCell('Limpar', id='ask-clear', classes='strategy-button')

        with Container(id='ask-result-card'):
            yield Static('Resposta', classes='card-title')
            yield RichLog(markup=True, wrap=True, id='ask-output')

    def on_mount(self) -> None:
        self._sync_mode_controls()
        self._render_empty_state()

    def on_action_cell_pressed(self, event: ActionCell.Pressed) -> None:
        control_id = event.cell.id or ''
        if control_id.startswith('mode-'):
            event.stop()
            if not self._ask_running:
                self._select_mode(control_id.removeprefix('mode-'))
            return

        if control_id.startswith('strategy-'):
            event.stop()
            if not self._ask_running:
                self._select_strategy(control_id.removeprefix('strategy-'))
            return

        if control_id == 'ask-clear':
            event.stop()
            if not self._ask_running:
                self._render_empty_state()
            return

        if control_id != 'ask-submit':
            return

        event.stop()
        if self._ask_running:
            return

        file_input = self.query_one('#ask-file-path', Input)
        question_input = self.query_one('#ask-question', Input)
        output = self.query_one('#ask-output', RichLog)

        self._set_running(True)
        output.clear()
        message = 'Recuperando evidencias...'
        if self.selected_mode == 'corpus' and self.app.corpus_indexing_partial:
            message += '\n\nCorpus em indexacao micro-lote. Resposta pode usar somente parte ja commitada.'
        output.write(Panel(message, title='Executando', border_style='#7c3aed'))
        if self.selected_mode == 'corpus':
            self._run_corpus_ask(question_input.value, self.selected_strategy)
        else:
            self._run_file_ask(Path(file_input.value), question_input.value, self.selected_strategy)

    def _select_mode(self, mode: str) -> None:
        if mode not in ASK_MODES:
            return
        self.selected_mode = mode  # type: ignore[assignment]
        self._sync_mode_controls()

    def _sync_mode_controls(self) -> None:
        for candidate in ASK_MODES:
            control = self.query_one(f'#mode-{candidate}', ActionCell)
            control.set_class(candidate == self.selected_mode, 'strategy-active')
        file_input = self.query_one('#ask-file-path', Input)
        file_input.disabled = self.selected_mode == 'corpus'

    def _select_strategy(self, strategy: str) -> None:
        if strategy not in ASK_STRATEGIES:
            return
        self.selected_strategy = strategy  # type: ignore[assignment]
        for candidate in ASK_STRATEGIES:
            control = self.query_one(f'#strategy-{candidate}', ActionCell)
            control.set_class(candidate == strategy, 'strategy-active')

    def _set_running(self, running: bool) -> None:
        self._ask_running = running
        submit = self.query_one('#ask-submit', ActionCell)
        clear = self.query_one('#ask-clear', ActionCell)
        submit.disabled = running
        clear.disabled = running
        submit.update('Executando...' if running else 'Perguntar')
        for mode in ASK_MODES:
            self.query_one(f'#mode-{mode}', ActionCell).disabled = running
        for strategy in ASK_STRATEGIES:
            self.query_one(f'#strategy-{strategy}', ActionCell).disabled = running
        if not running:
            self._sync_mode_controls()

    @work(thread=True)
    def _run_file_ask(self, file_path: Path, question: str, strategy: AskStrategy) -> None:
        try:
            response = ask_file(file_path, question, strategy, runtime=self.app.corpus_runtime)
        except Exception as exc:
            self.app.call_from_thread(self._render_error, exc)
            return
        self.app.call_from_thread(self._render_response, response)

    @work(thread=True)
    def _run_corpus_ask(self, question: str, strategy: AskStrategy) -> None:
        try:
            response = ask_corpus(question, strategy, runtime=self.app.corpus_runtime)
        except Exception as exc:
            self.app.call_from_thread(self._render_error, exc)
            return
        self.app.call_from_thread(self._render_response, response)

    def _render_empty_state(self) -> None:
        output = self.query_one('#ask-output', RichLog)
        output.clear()
        output.write(
            Panel(
                _bullet_help(
                    'Modo Corpus usa SQLite + Chroma ja indexados.',
                    'Modo Arquivo consulta um arquivo isolado.',
                    'A resposta, citacoes, fontes e latencia aparecem aqui.',
                ),
                title='Pronto',
                border_style='#372150',
            )
        )

    def _render_error(self, exc: Exception) -> None:
        output = self.query_one('#ask-output', RichLog)
        output.clear()
        output.write(Panel(str(exc), title='Erro', border_style='#fb7185'))
        self._set_running(False)

    def _render_response(self, response: AskResponse) -> None:
        output = self.query_one('#ask-output', RichLog)
        output.clear()

        if response.no_answer:
            body = response.reason_for_no_answer or 'no_answer'
            if response.limitations:
                body += '\n\n' + '\n'.join(f'- {item}' for item in response.limitations)
            output.write(Panel(body, title='no_answer', border_style='#fbbf24'))
        else:
            output.write(Panel(response.answer or '', title='Resposta', border_style='#f04ddf'))

        if response.citations:
            table = Table(title='Citacoes', border_style='#372150')
            table.add_column('chunk', overflow='fold')
            table.add_column('span', no_wrap=True)
            table.add_column('fonte', overflow='fold')
            table.add_column('snippet', overflow='fold')
            for citation in response.citations:
                table.add_row(
                    citation.chunk_id,
                    f'{citation.char_start}-{citation.char_end}',
                    _short_path(citation.source_path),
                    citation.snippet,
                )
            output.write(table)

        if response.used_sources:
            sources = ', '.join(_short_path(source.source_path) or source.doc_id for source in response.used_sources)
            output.write(Text.assemble(('Fontes usadas: ', '#8f6daa'), sources))

        output.write(Text.assemble(('latencia_ms: ', '#8f6daa'), str(response.latency_ms)))
        self._set_running(False)


class NotesPane(Vertical):
    _operation_running: bool

    def __init__(self, **kwargs: object) -> None:
        super().__init__(**kwargs)
        self._operation_running = False
        self._progress_messages: list[str] = []
        self._cancel_token: CancellationToken | None = None

    def compose(self) -> ComposeResult:
        settings = get_settings()
        with Container(id='notes-hero'):
            yield Static('Notes', classes='hero-title')
            yield Static('Indexe pastas recursivas e opere o corpus local.', classes='hero-subtitle')
        with Container(id='notes-form-card'):
            yield Static('Corpus', classes='card-title')
            yield Label('Pasta')
            yield Input(value=str(settings.default_corpus_path or ''), placeholder=r'D:\caminho\pasta', id='notes-folder-path')
            with Container(id='notes-action-row'):
                yield ActionCell('Status', id='notes-status', classes='strategy-button')
                yield ActionCell('Indexar pasta', id='notes-index', classes='strategy-button')
                yield ActionCell('Rebuild pasta', id='notes-rebuild', classes='strategy-button')
                yield ActionCell('Limpar DB', id='notes-reset', classes='primary-action')
                yield ActionCell('Cancelar', id='notes-cancel', classes='strategy-button')
            yield Label('Confirmacao para limpar')
            yield Input(placeholder='Digite LIMPAR', id='notes-reset-confirm')
        with Container(id='notes-result-card'):
            yield Static('Banco local', classes='card-title')
            yield RichLog(markup=True, wrap=True, id='notes-output')

    def on_mount(self) -> None:
        self._render_message(
            _bullet_help(
                'Status mostra consistencia entre SQLite e Chroma.',
                'Indexar pasta adiciona arquivos suportados, incluindo subpastas.',
                'Rebuild pasta limpa e recria o corpus pela pasta escolhida.',
                'Limpar DB apaga notas, chunks e vetores apos digitar LIMPAR.',
            )
        )
        self._set_running(False)

    def on_action_cell_pressed(self, event: ActionCell.Pressed) -> None:
        control_id = event.cell.id or ''
        if control_id == 'notes-cancel':
            event.stop()
            self._cancel_index()
            return
        if not control_id.startswith('notes-') or self._operation_running:
            return
        event.stop()
        self.handle_action(control_id)

    def handle_action(self, control_id: str) -> None:
        if self._operation_running:
            return
        if control_id == 'notes-status':
            self._set_running(True)
            self._run_status()
            return
        if control_id in {'notes-index', 'notes-rebuild'}:
            folder = self.query_one('#notes-folder-path', Input).value
            try:
                preflight = preflight_corpus_folder(folder)
            except Exception as exc:
                self._render_error(exc)
                return
            self._progress_messages = []
            self._render_preflight(preflight, rebuild=control_id == 'notes-rebuild')
            self._cancel_token = CancellationToken()
            self._set_running(True)
            self._run_index(Path(preflight.root_path), control_id == 'notes-rebuild', self._cancel_token)
            return
        if control_id == 'notes-reset':
            confirm = self.query_one('#notes-reset-confirm', Input).value
            if confirm.strip() != 'LIMPAR':
                self._render_error(ValueError('Digite LIMPAR para confirmar reset do corpus.'))
                return
            self._set_running(True)
            self._run_reset(confirm)

    def _set_running(self, running: bool) -> None:
        self._operation_running = running
        for selector in ('#notes-status', '#notes-index', '#notes-rebuild', '#notes-reset'):
            self.query_one(selector, ActionCell).disabled = running
        self.query_one('#notes-cancel', ActionCell).disabled = not running

    def load_defaults(self, settings: Settings) -> None:
        if not self._operation_running:
            self.query_one('#notes-folder-path', Input).value = str(settings.default_corpus_path or '')

    def _cancel_index(self) -> None:
        if self._cancel_token is None or not self._operation_running:
            return
        self._cancel_token.cancel()
        self._render_message('Cancelando indexacao...')

    @work(thread=True)
    def _run_status(self) -> None:
        try:
            status = corpus_status_from_tui()
            notes = list_corpus_notes()
        except Exception as exc:
            self.app.call_from_thread(self._render_error, exc)
            return
        self.app.call_from_thread(self._render_status, status, notes)

    @work(thread=True)
    def _run_index(self, folder_path: Path, rebuild: bool, cancel_token: CancellationToken) -> None:
        try:
            def report_progress(progress: CorpusIndexProgress) -> None:
                self.app.call_from_thread(self._render_index_progress, progress)

            result = index_corpus_folder(
                folder_path,
                rebuild=rebuild,
                runtime=self.app.corpus_runtime,
                progress=report_progress,
                cancel_token=cancel_token,
            )
            status = corpus_status_from_tui()
            notes = list_corpus_notes()
        except Exception as exc:
            self.app.call_from_thread(self._render_error, exc)
            return
        self.app.call_from_thread(self._render_index_result, result, status, notes)

    @work(thread=True)
    def _run_reset(self, confirm: str) -> None:
        try:
            result = reset_corpus_from_tui(confirm, runtime=self.app.corpus_runtime)
            status = corpus_status_from_tui()
            notes = list_corpus_notes()
        except Exception as exc:
            self.app.call_from_thread(self._render_error, exc)
            return
        self.app.call_from_thread(self._render_reset_result, result, status, notes)

    def _render_message(self, message: str) -> None:
        output = self.query_one('#notes-output', RichLog)
        output.clear()
        output.write(Panel(message, title='Pronto', border_style='#372150'))

    def _render_error(self, exc: Exception) -> None:
        output = self.query_one('#notes-output', RichLog)
        output.clear()
        output.write(Panel(str(exc), title='Erro', border_style='#fb7185'))
        self.app.corpus_indexing_partial = False
        self._cancel_token = None
        self._set_running(False)

    def _render_preflight(self, preflight: CorpusDiscoveryResult, *, rebuild: bool) -> None:
        output = self.query_one('#notes-output', RichLog)
        output.clear()
        output.write(
            Panel(
                f'pasta={_short_path(preflight.root_path, 72)}\n'
                f'acao={"rebuild" if rebuild else "indexar"}\n'
                f'encontrados={len(preflight.files)}\n'
                f'ignorados={len(preflight.skipped)}\n'
                'status=iniciando',
                title='Preflight',
                border_style='#7c3aed',
            )
        )

    def _render_index_progress(self, progress: CorpusIndexProgress) -> None:
        output = self.query_one('#notes-output', RichLog)
        self.app.corpus_indexing_partial = progress.commit_mode_resolved == 'microbatch' and progress.phase not in {
            'finished',
            'failed',
            'cancelled',
        }
        if progress.message:
            self._progress_messages.append(progress.message)
            self._progress_messages = self._progress_messages[-10:]
        last_messages = '\n'.join(f'- {message}' for message in self._progress_messages)
        current_path = _short_path(progress.current_path, 72)
        rate_text, eta_text = _progress_rate_and_eta(progress)
        body = (
            f'fase={progress.phase}\n'
            f'modo={progress.commit_mode_requested}->{progress.commit_mode_resolved}\n'
            f'lote={progress.batch_index}/{progress.batch_total}\n'
            f'processados={progress.processed_count}/{progress.total_found}\n'
            f'indexados={progress.indexed_count}\n'
            f'commitados={progress.committed_count}\n'
            f'ask_parcial={"sim" if progress.commit_mode_resolved == "microbatch" and progress.phase != "finished" else "nao"}\n'
            f'inalterados={progress.unchanged_count}\n'
            f'falhas={progress.failed_count}\n'
            f'ignorados={progress.skipped_count}\n'
            f'warmup_ms={progress.warmup_ms}\n'
            f'embedding_ms={progress.embedding_ms}\n'
            f'writing_ms={progress.writing_ms}\n'
            f'tempo_ms={progress.elapsed_ms}\n'
            f'taxa={rate_text}\n'
            f'eta={eta_text}'
        )
        if current_path:
            body += f'\natual={current_path}'
        if last_messages:
            body += f'\n\nultimas:\n{last_messages}'

        output.clear()
        output.write(Panel(body, title='Indexando', border_style='#7c3aed'))

    def _render_status(self, status, notes, *, clear: bool = True) -> None:
        output = self.query_one('#notes-output', RichLog)
        if clear:
            output.clear()
        status_table = Table(title='Status', border_style='#372150')
        status_table.add_column('campo')
        status_table.add_column('valor')
        for key, value in (
            ('status', status.status),
            ('notes', str(status.notes_count)),
            ('sqlite_chunks', str(status.sqlite_chunks_count)),
            ('vector_chunks', str(status.vector_chunks_count)),
            ('stale_vectors', str(status.stale_vector_chunks_count)),
            ('missing_vectors', str(status.missing_vector_chunks_count)),
            ('embedding_mismatches', str(status.embedding_model_mismatch_count)),
        ):
            status_table.add_row(key, value)
        output.write(status_table)

        notes_table = Table(title='Notas', border_style='#372150')
        notes_table.add_column('note_id', overflow='fold')
        notes_table.add_column('titulo', overflow='fold')
        notes_table.add_column('fonte', overflow='fold')
        for note in notes[:20]:
            notes_table.add_row(note.note_id, note.title, _short_path(str(note.source_path)))
        if not notes:
            notes_table.add_row('-', 'sem notas', '-')
        output.write(notes_table)
        self._cancel_token = None
        self._set_running(False)

    def _render_index_result(self, result, status, notes) -> None:
        output = self.query_one('#notes-output', RichLog)
        self.app.corpus_indexing_partial = False
        output.clear()
        output.write(
            Panel(
                f'status={result.status}\n'
                f'encontrados={result.total_found}\n'
                f'indexados={result.indexed_count}\n'
                f'inalterados={result.unchanged_count}\n'
                f'falhas={result.failed_count}\n'
                f'ignorados={result.skipped_count}',
                title='Indexacao',
                border_style='#7c3aed',
            )
        )
        self._render_status(status, notes, clear=False)

    def _render_reset_result(self, result, status, notes) -> None:
        output = self.query_one('#notes-output', RichLog)
        self.app.corpus_indexing_partial = False
        output.clear()
        output.write(
            Panel(
                f'notas_apagadas={result.deleted_notes}\n'
                f'chunks_apagados={result.deleted_chunks}\n'
                f'vetores_apagados={result.deleted_vectors}',
                title='Reset',
                border_style='#fb7185',
            )
        )
        self._render_status(status, notes, clear=False)


class BenchmarkPane(Vertical):
    _operation_running: bool

    def __init__(self, **kwargs: object) -> None:
        super().__init__(**kwargs)
        self._operation_running = False

    def compose(self) -> ComposeResult:
        default_suite = get_settings().datasets_dir / 'manual_validation' / 'suite.json'
        with Container(id='benchmark-hero'):
            yield Static('Benchmark', classes='hero-title')
            yield Static('Compare lexical, vector e hybrid em uma suite.', classes='hero-subtitle')
        with Container(id='benchmark-form-card'):
            yield Static('Suite', classes='card-title')
            yield Label('suite.json')
            yield Input(value=str(default_suite), id='benchmark-suite-path')
            with Container(id='benchmark-action-row'):
                yield ActionCell('Comparar', id='benchmark-run', classes='primary-action')
        with Container(id='benchmark-result-card'):
            yield Static('Resultado', classes='card-title')
            yield RichLog(markup=True, wrap=True, id='benchmark-output')

    def on_mount(self) -> None:
        output = self.query_one('#benchmark-output', RichLog)
        output.write(
            Panel(
                _bullet_help(
                    'Informe o suite.json.',
                    'Comparar roda lexical, vector e hybrid.',
                    'O resultado mostra MRR, Recall@3 e latencia media.',
                ),
                title='Pronto',
                border_style='#372150',
            )
        )

    def on_action_cell_pressed(self, event: ActionCell.Pressed) -> None:
        control_id = event.cell.id or ''
        if control_id != 'benchmark-run' or self._operation_running:
            return
        event.stop()
        self.handle_action(control_id)

    def handle_action(self, control_id: str) -> None:
        if control_id != 'benchmark-run' or self._operation_running:
            return
        self._set_running(True)
        suite = Path(self.query_one('#benchmark-suite-path', Input).value)
        output = self.query_one('#benchmark-output', RichLog)
        output.clear()
        output.write(Panel('Executando benchmark...', title='Executando', border_style='#7c3aed'))
        self._run_benchmark(suite)

    def _set_running(self, running: bool) -> None:
        self._operation_running = running
        self.query_one('#benchmark-run', ActionCell).disabled = running

    @work(thread=True)
    def _run_benchmark(self, suite_path: Path) -> None:
        try:
            result = compare_suite_from_tui(suite_path, runtime=self.app.corpus_runtime)
        except Exception as exc:
            self.app.call_from_thread(self._render_error, exc)
            return
        self.app.call_from_thread(self._render_result, result)

    def _render_error(self, exc: Exception) -> None:
        output = self.query_one('#benchmark-output', RichLog)
        output.clear()
        output.write(Panel(str(exc), title='Erro', border_style='#fb7185'))
        self._set_running(False)

    def _render_result(self, result) -> None:
        output = self.query_one('#benchmark-output', RichLog)
        output.clear()
        output.write(Panel(f'{result.comparison_id}\n{result.suite_name}', title='Comparacao', border_style='#7c3aed'))
        table = Table(title='Metricas', border_style='#372150')
        table.add_column('strategy')
        table.add_column('queries', justify='right')
        table.add_column('MRR', justify='right')
        table.add_column('Recall@3', justify='right')
        table.add_column('latencia media', justify='right')
        for strategy in ('lexical', 'vector', 'hybrid'):
            summary = result.summaries[strategy]
            table.add_row(
                summary.strategy,
                str(summary.query_count),
                f'{summary.mrr:.4f}',
                f'{summary.recall_at_3:.4f}',
                f'{summary.avg_query_latency_ms:.1f} ms',
            )
        output.write(table)
        self._set_running(False)


class SettingsPane(Vertical):
    selected_device: str
    selected_strategy: str
    selected_commit_mode: str
    recursive_default: bool
    _doctor_running: bool
    _doctor_request_id: int

    def __init__(self, **kwargs: object) -> None:
        super().__init__(**kwargs)
        settings = get_settings()
        self.selected_device = settings.embedding_device
        self.selected_answer_provider = settings.answer_provider
        self.selected_strategy = settings.default_ask_strategy
        self.selected_commit_mode = settings.corpus_commit_mode
        self.recursive_default = settings.corpus_recursive_default
        self.advanced_visible = False
        self._doctor_running = False
        self._doctor_request_id = 0

    def compose(self) -> ComposeResult:
        settings = get_settings()
        with Container(id='settings-hero'):
            yield Static('Settings', classes='hero-title')
            yield Static('Preferencias do app salvas em user_settings.json.', classes='hero-subtitle')
        with Container(id='settings-form-card'):
            yield Static('Simples', classes='card-title')
            with Container(id='settings-preset-row'):
                for preset in list_settings_presets():
                    yield ActionCell(preset.label, id=f'settings-preset-{preset.key}', classes='strategy-button')
            with Container(id='settings-device-row'):
                yield ActionCell('Auto', id='settings-device-auto', classes='strategy-button')
                yield ActionCell('CPU', id='settings-device-cpu', classes='strategy-button')
                yield ActionCell('CUDA', id='settings-device-cuda', classes='strategy-button')
            yield Static('Provider de resposta', classes='section-label')
            with Container(id='settings-provider-row'):
                yield ActionCell('Extractive', id='settings-provider-extractive', classes='strategy-button')
                yield ActionCell('Ollama', id='settings-provider-ollama', classes='strategy-button')
                yield ActionCell('LM Studio', id='settings-provider-lmstudio', classes='strategy-button')
                yield ActionCell('OpenAI', id='settings-provider-openai-compatible', classes='strategy-button')
            with Container(id='settings-answer-section'):
                yield Static('Modelo de resposta - escolha da lista (Listar modelos)', classes='field-caption')
                with Container(id='settings-answer-row'):
                    yield Select(
                        [(settings.answer_model, settings.answer_model)] if settings.answer_model else [],
                        value=settings.answer_model if settings.answer_model else Select.BLANK,
                        allow_blank=True,
                        prompt='Selecione um modelo (Listar modelos)',
                        id='settings-answer-model',
                    )
            with Container(id='settings-answer-key-section'):
                yield Static('Chave de API - so para provider remoto (OpenAI); salva no .env local', classes='field-caption')
                yield Input(
                    placeholder='FREE_PLAUD_ANSWER_API_KEY (vazio nao altera)',
                    id='settings-answer-api-key',
                    password=True,
                )
            yield Static('Recuperacao', classes='section-label')
            with Container(id='settings-strategy-row'):
                yield ActionCell('Lexical', id='settings-strategy-lexical', classes='strategy-button')
                yield ActionCell('Vector', id='settings-strategy-vector', classes='strategy-button')
                yield ActionCell('Hybrid', id='settings-strategy-hybrid', classes='strategy-button')
                yield ActionCell('Recursivo', id='settings-recursive', classes='strategy-button')
            yield Static('Corpus - pasta do vault a indexar (vira sua base de busca; nao e a pasta do modelo)', classes='section-label')
            with Container(id='settings-path-row'):
                yield Input(value=str(settings.default_corpus_path or ''), placeholder=r'D:\caminho\pasta', id='settings-corpus-path')
            with Container(id='settings-action-row'):
                yield ActionCell('Salvar', id='settings-save', classes='primary-action')
                yield ActionCell('Testar provider', id='settings-test-provider', classes='strategy-button')
                yield ActionCell('Listar modelos', id='settings-list-models', classes='strategy-button')
                yield ActionCell('Resetar', id='settings-reset', classes='strategy-button')
                yield ActionCell('Avancado', id='settings-advanced-toggle', classes='strategy-button')
            with Container(id='settings-advanced-fields', classes='hidden'):
                yield Static('Avancado', classes='card-title')
                yield Input(value=settings.embedding_model, placeholder='embedding_model', id='settings-model')
                with Container(id='settings-number-row'):
                    yield Input(value=str(settings.retrieval_top_k), placeholder='top_k', id='settings-top-k')
                    yield Input(value=str(settings.default_chunk_size), placeholder='chunk_size', id='settings-chunk-size')
                    yield Input(value=str(settings.default_chunk_overlap), placeholder='overlap', id='settings-overlap')
                with Container(id='settings-commit-row'):
                    yield ActionCell('Auto', id='settings-commit-auto', classes='strategy-button')
                    yield ActionCell('Atomic', id='settings-commit-atomic', classes='strategy-button')
                    yield ActionCell('Microbatch', id='settings-commit-microbatch', classes='strategy-button')
                with Container(id='settings-answer-advanced-row'):
                    yield Input(value=str(settings.answer_base_url or ''), placeholder='answer_base_url', id='settings-answer-base-url')
                    yield Input(value=str(settings.answer_temperature), placeholder='temperature', id='settings-answer-temperature')
                    yield Input(value=str(settings.answer_timeout_seconds), placeholder='timeout', id='settings-answer-timeout')
                with Container(id='settings-worker-row'):
                    yield Input(
                        value=str(settings.corpus_embedding_batch_size),
                        placeholder='embedding_batch',
                        id='settings-embedding-batch',
                    )
                    yield Input(value=str(settings.corpus_index_workers), placeholder='workers', id='settings-workers')
        with Container(id='settings-result-card'):
            yield Static('Estado', classes='card-title')
            yield RichLog(markup=True, wrap=True, id='settings-output')

    def on_mount(self) -> None:
        self._sync_controls()
        settings = get_settings()
        self._render_message(_settings_status_message(settings, 'aguardando abertura da aba Settings.'))

    def refresh_doctor(self) -> None:
        if self._doctor_running:
            return
        settings = get_settings()
        self._doctor_running = True
        self._doctor_request_id += 1
        request_id = self._doctor_request_id
        self._render_message(_settings_status_message(settings, 'carregando...'))
        self._run_doctor(settings, request_id)

    def on_action_cell_pressed(self, event: ActionCell.Pressed) -> None:
        control_id = event.cell.id or ''
        if control_id.startswith('settings-preset-'):
            event.stop()
            self._apply_preset(control_id.removeprefix('settings-preset-'))
            return
        if control_id.startswith('settings-device-'):
            event.stop()
            self.selected_device = control_id.removeprefix('settings-device-')
            self._sync_controls()
            return
        if control_id.startswith('settings-provider-'):
            event.stop()
            self.selected_answer_provider = control_id.removeprefix('settings-provider-')
            self._sync_controls()
            return
        if control_id.startswith('settings-strategy-'):
            event.stop()
            self.selected_strategy = control_id.removeprefix('settings-strategy-')
            self._sync_controls()
            return
        if control_id.startswith('settings-commit-'):
            event.stop()
            self.selected_commit_mode = control_id.removeprefix('settings-commit-')
            self._sync_controls()
            return
        if control_id == 'settings-advanced-toggle':
            event.stop()
            self.advanced_visible = not self.advanced_visible
            self._sync_controls()
            return
        if control_id == 'settings-recursive':
            event.stop()
            self.recursive_default = not self.recursive_default
            self._sync_controls()
            return
        if control_id == 'settings-save':
            event.stop()
            self._save()
            return
        if control_id == 'settings-test-provider':
            event.stop()
            self._doctor_request_id += 1
            self._doctor_running = False
            self._render_message('Testando provider...')
            self._run_provider_test()
            return
        if control_id == 'settings-list-models':
            event.stop()
            self._doctor_request_id += 1
            self._doctor_running = False
            self._render_message('Listando modelos...')
            self._run_model_discovery()
            return
        if control_id == 'settings-reset':
            event.stop()
            settings = reset_user_settings()
            self.app.corpus_runtime.clear()
            self.app.refresh_settings_nav(settings)
            self._load_from_settings(settings)
            self._sync_controls()
            self._render_message('Configuracoes resetadas.')

    def _apply_preset(self, preset_key: str) -> None:
        try:
            result = apply_settings_preset(preset_key)
        except Exception as exc:
            self._render_error(exc)
            return
        self.app.corpus_runtime.clear()
        self.app.refresh_settings_nav(result.settings)
        self._load_from_settings(result.settings)
        self._sync_controls()
        self._doctor_running = False
        self._doctor_request_id += 1
        self._render_message(f'Preset {result.preset.key} aplicado. Doctor sera atualizado.')
        self.refresh_doctor()

    def _load_from_settings(self, settings: Settings) -> None:
        self.selected_device = settings.embedding_device
        self.selected_answer_provider = settings.answer_provider
        self.selected_strategy = settings.default_ask_strategy
        self.selected_commit_mode = settings.corpus_commit_mode
        self.recursive_default = settings.corpus_recursive_default
        self.query_one('#settings-model', Input).value = settings.embedding_model
        self._set_model_options([], selected=settings.answer_model)
        self.query_one('#settings-answer-base-url', Input).value = str(settings.answer_base_url or '')
        self.query_one('#settings-answer-temperature', Input).value = str(settings.answer_temperature)
        self.query_one('#settings-answer-timeout', Input).value = str(settings.answer_timeout_seconds)
        self.query_one('#settings-top-k', Input).value = str(settings.retrieval_top_k)
        self.query_one('#settings-chunk-size', Input).value = str(settings.default_chunk_size)
        self.query_one('#settings-overlap', Input).value = str(settings.default_chunk_overlap)
        self.query_one('#settings-corpus-path', Input).value = str(settings.default_corpus_path or '')
        self.query_one('#settings-embedding-batch', Input).value = str(settings.corpus_embedding_batch_size)
        self.query_one('#settings-workers', Input).value = str(settings.corpus_index_workers)
        self.query_one('#settings-answer-api-key', Input).value = ''

    def _current_answer_model(self) -> str:
        value = self.query_one('#settings-answer-model', Select).value
        return '' if value is Select.BLANK else str(value).strip()

    def _set_model_options(self, models: list[str], *, selected: str | None = None) -> None:
        select = self.query_one('#settings-answer-model', Select)
        current = selected if selected is not None else self._current_answer_model()
        options = list(dict.fromkeys(model for model in [current, *models] if model))
        select.set_options([(model, model) for model in options])
        if current and current in options:
            select.value = current

    def _sync_controls(self) -> None:
        for device in ('auto', 'cpu', 'cuda'):
            self.query_one(f'#settings-device-{device}', ActionCell).set_class(device == self.selected_device, 'strategy-active')
        for provider in ('extractive', 'ollama', 'lmstudio', 'openai-compatible'):
            self.query_one(f'#settings-provider-{provider}', ActionCell).set_class(
                provider == self.selected_answer_provider,
                'strategy-active',
            )
        for strategy in ASK_STRATEGIES:
            self.query_one(f'#settings-strategy-{strategy}', ActionCell).set_class(
                strategy == self.selected_strategy,
                'strategy-active',
            )
        for mode in ('auto', 'atomic', 'microbatch'):
            self.query_one(f'#settings-commit-{mode}', ActionCell).set_class(mode == self.selected_commit_mode, 'strategy-active')
        recursive = self.query_one('#settings-recursive', ActionCell)
        recursive.update('Recursivo: Sim' if self.recursive_default else 'Recursivo: Nao')
        recursive.set_class(self.recursive_default, 'strategy-active')
        advanced = self.query_one('#settings-advanced-fields')
        advanced.set_class(not self.advanced_visible, 'hidden')
        advanced_toggle = self.query_one('#settings-advanced-toggle', ActionCell)
        advanced_toggle.update('Avancado: Sim' if self.advanced_visible else 'Avancado')
        advanced_toggle.set_class(self.advanced_visible, 'strategy-active')
        uses_model = self.selected_answer_provider != 'extractive'
        uses_api_key = self.selected_answer_provider == 'openai-compatible'
        self.query_one('#settings-answer-section').set_class(not uses_model, 'hidden')
        self.query_one('#settings-answer-key-section').set_class(not uses_api_key, 'hidden')

    def _save(self) -> None:
        try:
            values = {
                'embedding_device': self.selected_device,
                'embedding_model': self.query_one('#settings-model', Input).value,
                'answer_provider': self.selected_answer_provider,
                'answer_model': self._current_answer_model(),
                'answer_base_url': self.query_one('#settings-answer-base-url', Input).value.strip() or None,
                'answer_temperature': float(self.query_one('#settings-answer-temperature', Input).value),
                'answer_timeout_seconds': int(self.query_one('#settings-answer-timeout', Input).value),
                'retrieval_top_k': int(self.query_one('#settings-top-k', Input).value),
                'default_ask_strategy': self.selected_strategy,
                'default_chunk_size': int(self.query_one('#settings-chunk-size', Input).value),
                'default_chunk_overlap': int(self.query_one('#settings-overlap', Input).value),
                'corpus_commit_mode': self.selected_commit_mode,
                'default_corpus_path': self.query_one('#settings-corpus-path', Input).value.strip() or None,
                'corpus_recursive_default': self.recursive_default,
                'corpus_embedding_batch_size': int(self.query_one('#settings-embedding-batch', Input).value),
                'corpus_index_workers': int(self.query_one('#settings-workers', Input).value),
            }
            updated = save_user_settings(values)
            api_key = self.query_one('#settings-answer-api-key', Input).value.strip()
            api_key_path = None
            if api_key:
                api_key_path = save_answer_api_key(api_key, settings=updated)
        except Exception as exc:
            self._render_error(exc)
            return
        self.app.corpus_runtime.clear()
        self.app.refresh_settings_nav(updated)
        self.query_one('#settings-answer-api-key', Input).value = ''
        message = 'Configuracoes salvas. Runtime limpo.'
        if api_key_path is not None:
            message += f'\nanswer_api_key salva em {api_key_path}.'
        self._render_message(message)

    def _render_message(self, message: str) -> None:
        output = self.query_one('#settings-output', RichLog)
        output.clear()
        output.write(Panel(message, title='Settings', border_style='#7c3aed'))

    @work(thread=True)
    def _run_provider_test(self) -> None:
        try:
            result = test_answer_provider()
            hint = runtime_hint(detect_runtime()) if result.status == 'error' else None
        except Exception as exc:
            self.app.call_from_thread(self._render_error, exc)
            return
        self.app.call_from_thread(self._render_provider_test, result, hint)

    def _render_provider_test(self, result, hint: str | None = None) -> None:
        self._render_message(_provider_test_message(result, hint))

    @work(thread=True)
    def _run_model_discovery(self) -> None:
        try:
            result = list_answer_models()
        except Exception as exc:
            self.app.call_from_thread(self._render_error, exc)
            return
        self.app.call_from_thread(self._render_model_discovery, result)

    def _render_model_discovery(self, result) -> None:
        self._render_message(_model_discovery_message(result))
        self._set_model_options([model.id for model in result.models])

    @work(thread=True)
    def _run_doctor(self, settings: Settings, request_id: int) -> None:
        try:
            report = run_doctor(settings=settings)
        except Exception as exc:
            self.app.call_from_thread(self._render_doctor_error, settings, exc, request_id)
            return
        self.app.call_from_thread(self._render_doctor, settings, report, request_id)

    def _render_doctor(self, settings: Settings, report, request_id: int) -> None:
        if request_id != self._doctor_request_id:
            return
        self._doctor_running = False
        self._render_message(_settings_status_message(settings, doctor_report_text(report)))

    def _render_doctor_error(self, settings: Settings, exc: Exception, request_id: int) -> None:
        if request_id != self._doctor_request_id:
            return
        self._doctor_running = False
        self._render_message(_settings_status_message(settings, f'erro: {exc}'))

    def _render_error(self, exc: Exception) -> None:
        output = self.query_one('#settings-output', RichLog)
        output.clear()
        output.write(Panel(str(exc), title='Erro', border_style='#fb7185'))


class PlaceholderPane(Vertical):
    def __init__(self, title: str, description: str, **kwargs: object) -> None:
        super().__init__(**kwargs)
        self._title = title
        self._description = description

    def compose(self) -> ComposeResult:
        with Container(classes='placeholder-card'):
            yield Static(self._title, classes='hero-title')
            yield Static(self._description, classes='hero-subtitle')


class FreePlaudApp(App[None]):
    CSS_PATH = Path(__file__).with_name('app.tcss')
    TITLE = 'free-plaud'
    SUB_TITLE = 'RAG local'
    BINDINGS = [('q', 'quit', 'Sair')]

    def __init__(self, **kwargs: object) -> None:
        super().__init__(**kwargs)
        self.corpus_runtime = CorpusRuntime()
        self.corpus_indexing_partial = False

    def on_mount(self) -> None:
        self._sync_responsive_classes(self.size)
        self._disable_button_flash()

    def on_resize(self, event: events.Resize) -> None:
        self._sync_responsive_classes(event.size)

    def _sync_responsive_classes(self, size: Size) -> None:
        self.screen.set_class(size.width < COMPACT_WIDTH, 'compact')

    def _disable_button_flash(self) -> None:
        for button in self.query(Button):
            button.active_effect_duration = 0

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Container(id='content'):
            yield NavPanel(id='nav-panel')
            with Container(id='main-panel'):
                yield AskPane(id='ask-pane', classes='screen-pane')
                yield NotesPane(id='notes-pane', classes='screen-pane hidden')
                yield BenchmarkPane(id='benchmark-pane', classes='screen-pane hidden')
                yield SettingsPane(id='settings-pane', classes='screen-pane hidden')
        yield Footer()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        button_id = event.button.id or ''
        if button_id not in {'nav-ask', 'nav-notes', 'nav-benchmark', 'nav-settings'}:
            return
        event.stop()
        self._show_pane(button_id.removeprefix('nav-'))

    def on_action_cell_pressed(self, event: ActionCell.Pressed) -> None:
        control_id = event.cell.id or ''
        if control_id.startswith('notes-'):
            event.stop()
            self.query_one(NotesPane).handle_action(control_id)
        elif control_id == 'benchmark-run':
            event.stop()
            self.query_one(BenchmarkPane).handle_action(control_id)

    def _show_pane(self, pane: str) -> None:
        for pane_id in ('ask', 'notes', 'benchmark', 'settings'):
            self.query_one(f'#{pane_id}-pane').set_class(pane_id != pane, 'hidden')
            self.query_one(f'#nav-{pane_id}', Button).set_class(pane_id == pane, 'nav-active')
        if pane == 'settings':
            self.query_one(SettingsPane).refresh_doctor()

    def refresh_settings_nav(self, settings: Settings) -> None:
        self.query_one('#nav-meta-model', Static).update(settings.embedding_model)
        self.query_one('#nav-meta-device', Static).update(settings.embedding_device)
        self.query_one('#nav-meta-top-k', Static).update(str(settings.retrieval_top_k))
        ask_pane = self.query_one(AskPane)
        if not ask_pane._ask_running:
            ask_pane._select_strategy(settings.default_ask_strategy)
        self.query_one(NotesPane).load_defaults(settings)


def main() -> None:
    FreePlaudApp().run()


if __name__ == '__main__':
    main()
