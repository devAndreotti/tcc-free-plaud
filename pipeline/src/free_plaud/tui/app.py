from pathlib import Path
from typing import Literal, cast

from rich.panel import Panel
from rich.table import Table
from textual import work
from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Button, Footer, Header, Input, Label, ListItem, ListView, RichLog, Select, Static

from free_plaud.app.config import Settings, get_settings
from free_plaud.ingest.loaders import load_document
from free_plaud.notes.structurer import structure_document
from free_plaud.providers.embed import get_embedder
from free_plaud.retrieval.rag import answer_with_citations
from free_plaud.retrieval.models import AskResponse
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


class NavPanel(Vertical):
    def compose(self) -> ComposeResult:
        yield Static('free-plaud', id='nav-title')
        yield ListView(
            ListItem(Label('Ask'), id='nav-ask'),
            ListItem(Label('Notes'), id='nav-notes'),
            ListItem(Label('Benchmark'), id='nav-benchmark'),
            id='nav-list',
        )


class AskPane(Vertical):
    def compose(self) -> ComposeResult:
        yield Static('Ask sobre arquivo local', classes='section-title')
        yield Static('Carrega arquivo, estrutura nota em memoria e chama answer_with_citations.', classes='muted')
        yield Label('Arquivo')
        yield Input(placeholder=r'D:\caminho\arquivo.md', id='ask-file-path')
        yield Label('Estrategia')
        yield Select(
            [(strategy, strategy) for strategy in ASK_STRATEGIES],
            value='hybrid',
            allow_blank=False,
            id='ask-strategy',
        )
        yield Label('Pergunta')
        yield Input(placeholder='O que este documento diz?', id='ask-question')
        yield Button('Executar ask', id='ask-submit')
        yield RichLog(markup=True, wrap=True, id='ask-output')

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id != 'ask-submit':
            return

        file_input = self.query_one('#ask-file-path', Input)
        question_input = self.query_one('#ask-question', Input)
        strategy_select = self.query_one('#ask-strategy', Select)
        output = self.query_one('#ask-output', RichLog)

        strategy = cast(AskStrategy, strategy_select.value)
        output.clear()
        output.write('[#c7afd9]Executando pipeline local...[/]')
        self._run_ask(Path(file_input.value), question_input.value, strategy)

    @work(thread=True)
    def _run_ask(self, file_path: Path, question: str, strategy: AskStrategy) -> None:
        try:
            response = ask_file(file_path, question, strategy)
        except Exception as exc:  # noqa: BLE001 - UI precisa renderizar erro operacional.
            self.app.call_from_thread(self._render_error, exc)
            return
        self.app.call_from_thread(self._render_response, response)

    def _render_error(self, exc: Exception) -> None:
        output = self.query_one('#ask-output', RichLog)
        output.clear()
        output.write(Panel(str(exc), title='Erro', border_style='#fb7185'))

    def _render_response(self, response: AskResponse) -> None:
        output = self.query_one('#ask-output', RichLog)
        output.clear()

        if response.no_answer:
            body = response.reason_for_no_answer or 'no_answer'
            if response.limitations:
                body += '\n\n' + '\n'.join(f'- {item}' for item in response.limitations)
            output.write(Panel(body, title='no_answer', border_style='#fbbf24'))
        else:
            output.write(Panel(response.answer or '', title='Resposta', border_style='#d946ef'))

        if response.citations:
            table = Table(title='Citacoes', border_style='#4c1d95')
            table.add_column('chunk')
            table.add_column('span')
            table.add_column('fonte')
            table.add_column('snippet')
            for citation in response.citations:
                table.add_row(
                    citation.chunk_id,
                    f'{citation.char_start}-{citation.char_end}',
                    citation.source_path or '',
                    citation.snippet,
                )
            output.write(table)

        if response.used_sources:
            sources = ', '.join(source.source_path or source.doc_id for source in response.used_sources)
            output.write(f'[#8f6daa]Fontes usadas:[/] {sources}')

        output.write(f'[#8f6daa]latencia_ms:[/] {response.latency_ms}')


class PlaceholderPane(Vertical):
    def __init__(self, title: str, description: str, **kwargs: object) -> None:
        super().__init__(**kwargs)
        self._title = title
        self._description = description

    def compose(self) -> ComposeResult:
        yield Static(self._title, classes='section-title')
        yield Static(self._description, classes='muted')


class FreePlaudApp(App[None]):
    CSS_PATH = Path(__file__).with_name('app.tcss')
    TITLE = 'free-plaud TUI'
    BINDINGS = [('q', 'quit', 'Sair')]

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Horizontal(id='content'):
            yield NavPanel(id='nav-panel')
            with Container(id='main-panel'):
                yield AskPane(id='ask-pane', classes='screen-pane')
                yield PlaceholderPane(
                    'Notes',
                    'Slice futura: persistencia SQLite e listagem de notas.',
                    id='notes-pane',
                    classes='screen-pane hidden',
                )
                yield PlaceholderPane(
                    'Benchmark',
                    'Slice futura: compare_benchmark_suite com suite.json.',
                    id='benchmark-pane',
                    classes='screen-pane hidden',
                )
        yield Footer()

    def on_mount(self) -> None:
        self.query_one('#nav-list', ListView).index = 0

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        if event.list_view.id != 'nav-list' or event.item.id is None:
            return
        target = {
            'nav-ask': 'ask',
            'nav-notes': 'notes',
            'nav-benchmark': 'benchmark',
        }.get(event.item.id)
        if target:
            self._show_pane(target)

    def _show_pane(self, pane: str) -> None:
        for pane_id in ('ask', 'notes', 'benchmark'):
            widget = self.query_one(f'#{pane_id}-pane')
            widget.set_class(pane_id != pane, 'hidden')


def main() -> None:
    FreePlaudApp().run()


if __name__ == '__main__':
    main()
