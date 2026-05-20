from pathlib import Path
from typing import Literal

from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from textual import work
from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Button, Footer, Header, Input, Label, RichLog, Static

from free_plaud.app.config import Settings, get_settings
from free_plaud.ingest.loaders import load_document
from free_plaud.notes.structurer import structure_document
from free_plaud.providers.embed import get_embedder
from free_plaud.retrieval.models import AskResponse
from free_plaud.retrieval.rag import answer_with_citations
from free_plaud.storage.vector import LocalVectorStore

AskStrategy = Literal['lexical', 'vector', 'hybrid']
ASK_STRATEGIES: tuple[AskStrategy, ...] = ('lexical', 'vector', 'hybrid')


def ask_file(
    file_path: Path | str,
    question: str,
    strategy: AskStrategy,
    *,
    settings: Settings | None = None,
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

    vector_store = LocalVectorStore(
        resolved_settings.vector_store_dir,
        collection_name=resolved_settings.vector_collection_name,
    )
    embedder = get_embedder(resolved_settings.embedding_model)
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


class NavPanel(Vertical):
    def compose(self) -> ComposeResult:
        settings = get_settings()
        yield Static('free-plaud', id='nav-brand')
        yield Static('RAG local', id='nav-subtitle')
        with Vertical(id='nav-actions'):
            yield Button('Ask', id='nav-ask', classes='nav-button nav-active')
            yield Button('Notes', id='nav-notes', classes='nav-button nav-planned')
            yield Button('Benchmark', id='nav-benchmark', classes='nav-button nav-planned')
        with Vertical(id='nav-meta'):
            yield Static('modelo', classes='nav-meta-label')
            yield Static(settings.embedding_model, classes='nav-meta-value')
            yield Static('top_k', classes='nav-meta-label')
            yield Static(str(settings.retrieval_top_k), classes='nav-meta-value')


class AskPane(Vertical):
    selected_strategy: AskStrategy
    _ask_running: bool

    def __init__(self, **kwargs: object) -> None:
        super().__init__(**kwargs)
        self.selected_strategy = 'hybrid'
        self._ask_running = False

    def compose(self) -> ComposeResult:
        with Container(id='ask-hero'):
            yield Static('Ask local', classes='hero-title')
            yield Static('Consulte um arquivo sem persistir nota no SQLite.', classes='hero-subtitle')

        with Container(id='ask-form-card'):
            yield Static('Consulta', classes='card-title')
            yield Label('Arquivo')
            yield Input(placeholder=r'D:\caminho\arquivo.md', id='ask-file-path')
            yield Label('Pergunta')
            yield Input(placeholder='O que este documento diz?', id='ask-question')
            yield Label('Estrategia')
            with Horizontal(id='strategy-row'):
                yield Button('lexical', id='strategy-lexical', classes='strategy-button')
                yield Button('vector', id='strategy-vector', classes='strategy-button')
                yield Button('hybrid', id='strategy-hybrid', classes='strategy-button strategy-active')
                yield Button('Executar ask', id='ask-submit', classes='primary-action')

        with Container(id='ask-result-card'):
            yield Static('Resposta', classes='card-title')
            yield RichLog(markup=True, wrap=True, id='ask-output')

    def on_mount(self) -> None:
        self._render_empty_state()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        button_id = event.button.id or ''
        if button_id.startswith('strategy-'):
            event.stop()
            if not self._ask_running:
                self._select_strategy(button_id.removeprefix('strategy-'))
            return

        if button_id != 'ask-submit':
            return

        event.stop()
        if self._ask_running:
            return

        file_input = self.query_one('#ask-file-path', Input)
        question_input = self.query_one('#ask-question', Input)
        output = self.query_one('#ask-output', RichLog)

        self._set_running(True)
        output.clear()
        output.write(Panel('Estruturando nota e recuperando evidencias...', title='Executando', border_style='#7c3aed'))
        self._run_ask(Path(file_input.value), question_input.value, self.selected_strategy)

    def _select_strategy(self, strategy: str) -> None:
        if strategy not in ASK_STRATEGIES:
            return
        self.selected_strategy = strategy  # type: ignore[assignment]
        for candidate in ASK_STRATEGIES:
            button = self.query_one(f'#strategy-{candidate}', Button)
            button.set_class(candidate == strategy, 'strategy-active')

    def _set_running(self, running: bool) -> None:
        self._ask_running = running
        submit = self.query_one('#ask-submit', Button)
        submit.disabled = running
        submit.label = 'Executando...' if running else 'Executar ask'
        for strategy in ASK_STRATEGIES:
            self.query_one(f'#strategy-{strategy}', Button).disabled = running

    @work(thread=True)
    def _run_ask(self, file_path: Path, question: str, strategy: AskStrategy) -> None:
        try:
            response = ask_file(file_path, question, strategy)
        except Exception as exc:  # noqa: BLE001 - UI precisa renderizar erro operacional.
            self.app.call_from_thread(self._render_error, exc)
            return
        self.app.call_from_thread(self._render_response, response)

    def _render_empty_state(self) -> None:
        output = self.query_one('#ask-output', RichLog)
        output.clear()
        output.write(
            Panel(
                'Informe um arquivo, escolha a estrategia e execute o ask.\n'
                'A resposta, citacoes, fontes e latencia aparecem aqui.',
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

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Horizontal(id='content'):
            yield NavPanel(id='nav-panel')
            with Container(id='main-panel'):
                yield AskPane(id='ask-pane', classes='screen-pane')
                yield PlaceholderPane(
                    'Notes',
                    'Planejado: persistencia SQLite e listagem de notas.',
                    id='notes-pane',
                    classes='screen-pane hidden',
                )
                yield PlaceholderPane(
                    'Benchmark',
                    'Planejado: compare_benchmark_suite com suite.json.',
                    id='benchmark-pane',
                    classes='screen-pane hidden',
                )
        yield Footer()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        button_id = event.button.id or ''
        if button_id not in {'nav-ask', 'nav-notes', 'nav-benchmark'}:
            return
        event.stop()
        self._show_pane(button_id.removeprefix('nav-'))

    def _show_pane(self, pane: str) -> None:
        for pane_id in ('ask', 'notes', 'benchmark'):
            self.query_one(f'#{pane_id}-pane').set_class(pane_id != pane, 'hidden')
            self.query_one(f'#nav-{pane_id}', Button).set_class(pane_id == pane, 'nav-active')


def main() -> None:
    FreePlaudApp().run()


if __name__ == '__main__':
    main()
