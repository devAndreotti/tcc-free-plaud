import json

import typer

from free_plaud.app.cli_paths import compose_path
from free_plaud.app.config import get_settings
from free_plaud.corpus.service import index_corpus_file, index_corpus_path

app = typer.Typer(help='Comandos para operar o corpus local indexado.', no_args_is_help=True)


@app.command('index')
def index(
    path_parts: list[str] = typer.Argument(..., metavar='PATH'),
    chunk_size: int | None = typer.Option(None, '--chunk-size', min=1),
    overlap: int | None = typer.Option(None, '--overlap', min=0),
    recursive: bool = typer.Option(False, '--recursive', help='Indexa subpastas recursivamente quando PATH for diretorio.'),
) -> None:
    """Indexa um arquivo ou pasta suportada no corpus local."""
    settings = get_settings()
    target = compose_path(path_parts)
    if target.is_dir():
        result = index_corpus_path(
            target,
            settings=settings,
            chunk_size=chunk_size,
            overlap=overlap,
            recursive=recursive,
        )
    else:
        result = index_corpus_file(
            target,
            settings=settings,
            chunk_size=chunk_size,
            overlap=overlap,
        )
    typer.echo(json.dumps(result.model_dump(mode='json'), ensure_ascii=True, indent=2))
    if result.status == 'failed':
        raise typer.Exit(code=1)
