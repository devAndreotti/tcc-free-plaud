import json

import typer

from free_plaud.app.cli_paths import compose_path
from free_plaud.app.config import get_settings
from free_plaud.corpus.service import index_corpus_file

app = typer.Typer(help='Comandos para operar o corpus local indexado.', no_args_is_help=True)


@app.command('index')
def index(
    path_parts: list[str] = typer.Argument(..., metavar='PATH'),
    chunk_size: int | None = typer.Option(None, '--chunk-size', min=1),
    overlap: int | None = typer.Option(None, '--overlap', min=0),
) -> None:
    """Indexa um arquivo suportado no corpus local."""
    settings = get_settings()
    result = index_corpus_file(
        compose_path(path_parts),
        settings=settings,
        chunk_size=chunk_size,
        overlap=overlap,
    )
    typer.echo(json.dumps(result.model_dump(mode='json'), ensure_ascii=True, indent=2))
    if result.status == 'failed':
        raise typer.Exit(code=1)
