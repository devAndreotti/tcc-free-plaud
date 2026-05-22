import json
from typing import Literal

import typer

from free_plaud.app.cli_paths import compose_path
from free_plaud.app.config import get_settings
from free_plaud.corpus.ask import answer_corpus_with_citations
from free_plaud.corpus.service import index_corpus_file, index_corpus_path
from free_plaud.providers.embed import get_embedder
from free_plaud.storage.sqlite import init_sqlite
from free_plaud.storage.vector import LocalVectorStore

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


@app.command('ask')
def ask(
    question: str = typer.Option(..., '--question', '-q', help='Pergunta em linguagem natural contra o corpus.'),
    top_k: int = typer.Option(6, '--top-k', min=1, help='Quantidade maxima de chunks recuperados.'),
    strategy: Literal['lexical', 'vector', 'hybrid'] = typer.Option(
        'hybrid',
        '--strategy',
        '-s',
        help='Estrategia de retrieval: lexical, vector ou hybrid.',
    ),
) -> None:
    """Pergunta contra todos os chunks persistidos no corpus local."""
    settings = get_settings()
    connection = init_sqlite(settings.sqlite_path)
    vector_store = None
    embedder = None
    if strategy in {'vector', 'hybrid'}:
        vector_store = LocalVectorStore(settings.vector_store_dir, collection_name=settings.vector_collection_name)
        embedder = get_embedder(settings.embedding_model)

    try:
        response = answer_corpus_with_citations(
            question,
            connection=connection,
            vector_store=vector_store,
            embedder=embedder,
            strategy=strategy,
            top_k=top_k,
        )
        typer.echo(json.dumps(response.model_dump(mode='json'), ensure_ascii=True, indent=2))
    finally:
        connection.close()
