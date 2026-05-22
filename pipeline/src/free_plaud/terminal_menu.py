from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table

from free_plaud.tui.actions import (
    ask_corpus,
    compare_suite_from_tui,
    corpus_status_from_tui,
    index_corpus_folder,
    list_corpus_notes,
    reset_corpus_from_tui,
)

console = Console()
PURPLE = '#a21caf'
PURPLE_DIM = '#7c3aed'
PINK = '#e84fe6'
TEXT = '#f8f0ff'
TEXT_DIM = '#c4b5fd'


def _print_header() -> None:
    console.print(
        Panel(
            f'[bold {TEXT}]free-plaud terminal[/bold {TEXT}]  [{TEXT_DIM}]v0.1[/{TEXT_DIM}]',
            border_style=PURPLE,
        )
    )


def _print_options() -> None:
    console.print(f'[bold {PINK}]ACOES:[/bold {PINK}]')
    console.print()
    console.print(f'[{TEXT_DIM}][1][/{TEXT_DIM}] Status do corpus')
    console.print(f'[{TEXT_DIM}][2][/{TEXT_DIM}] Perguntar ao corpus')
    console.print(f'[{TEXT_DIM}][3][/{TEXT_DIM}] Indexar pasta recursiva')
    console.print(f'[{TEXT_DIM}][4][/{TEXT_DIM}] Rebuild por pasta recursiva')
    console.print(f'[{TEXT_DIM}][5][/{TEXT_DIM}] Limpar banco do corpus')
    console.print(f'[{TEXT_DIM}][6][/{TEXT_DIM}] Rodar benchmark compare')
    console.print(f'[{TEXT_DIM}][0][/{TEXT_DIM}] Sair')
    console.print()


def _show_status() -> None:
    status = corpus_status_from_tui()
    notes = list_corpus_notes()
    table = Table(title='Status do corpus', border_style=PURPLE_DIM)
    table.add_column('campo')
    table.add_column('valor')
    for key, value in (
        ('status', status.status),
        ('notes', str(status.notes_count)),
        ('sqlite_chunks', str(status.sqlite_chunks_count)),
        ('vector_chunks', str(status.vector_chunks_count)),
        ('stale_vectors', str(status.stale_vector_chunks_count)),
        ('missing_vectors', str(status.missing_vector_chunks_count)),
    ):
        table.add_row(key, value)
    console.print(table)
    if notes:
        console.print(f'[{TEXT_DIM}]Notas: {", ".join(note.note_id for note in notes[:8])}[/{TEXT_DIM}]')


def _ask() -> None:
    question = Prompt.ask('Pergunta').strip()
    strategy = Prompt.ask('Strategy', choices=['lexical', 'vector', 'hybrid'], default='hybrid')
    response = ask_corpus(question, strategy)  # type: ignore[arg-type]
    if response.no_answer:
        console.print(Panel(response.reason_for_no_answer or 'no_answer', title='no_answer', border_style='yellow'))
    else:
        console.print(Panel(response.answer or '', title='Resposta', border_style=PINK))
    if response.citations:
        console.print(f'[{TEXT_DIM}]Citacoes: {len(response.citations)} | Fontes: {len(response.used_sources)}[/{TEXT_DIM}]')


def _index(*, rebuild: bool) -> None:
    folder = Path(Prompt.ask('Pasta')).expanduser()
    result = index_corpus_folder(folder, rebuild=rebuild)
    console.print(
        Panel(
            f'status={result.status}\n'
            f'encontrados={result.total_found}\n'
            f'indexados={result.indexed_count}\n'
            f'falhas={result.failed_count}\n'
            f'ignorados={result.skipped_count}',
            title='Indexacao',
            border_style=PURPLE_DIM if result.status == 'success' else 'yellow',
        )
    )


def _reset() -> None:
    console.print('[bold red]Isto apaga notes/chunks SQLite e vetores Chroma do corpus ativo.[/bold red]')
    confirm = Prompt.ask('Digite LIMPAR para confirmar')
    result = reset_corpus_from_tui(confirm)
    console.print(
        Panel(
            f'notas={result.deleted_notes}\nchunks={result.deleted_chunks}\nvetores={result.deleted_vectors}',
            title='Reset',
            border_style='red',
        )
    )


def _benchmark() -> None:
    suite = Path(Prompt.ask('Suite JSON')).expanduser()
    result = compare_suite_from_tui(suite)
    table = Table(title=result.comparison_id, border_style=PURPLE_DIM)
    table.add_column('strategy')
    table.add_column('MRR', justify='right')
    table.add_column('Recall@3', justify='right')
    table.add_column('latencia media', justify='right')
    for strategy in ('lexical', 'vector', 'hybrid'):
        summary = result.summaries[strategy]
        table.add_row(
            strategy,
            f'{summary.mrr:.4f}',
            f'{summary.recall_at_3:.4f}',
            f'{summary.avg_query_latency_ms:.1f} ms',
        )
    console.print(table)


def run_terminal_menu() -> None:
    """Menu simples para operar corpus sem abrir TUI Textual."""
    while True:
        _print_header()
        _print_options()
        choice = Prompt.ask('Escolha', default='0')
        try:
            if choice == '0':
                console.print('Sair')
                return
            if choice == '1':
                _show_status()
            elif choice == '2':
                _ask()
            elif choice == '3':
                _index(rebuild=False)
            elif choice == '4':
                _index(rebuild=True)
            elif choice == '5':
                _reset()
            elif choice == '6':
                _benchmark()
            else:
                console.print('[yellow]Opcao invalida.[/yellow]')
        except Exception as exc:  # noqa: BLE001 - menu precisa sobreviver a erro operacional.
            console.print(Panel(str(exc), title='Erro', border_style='red'))
