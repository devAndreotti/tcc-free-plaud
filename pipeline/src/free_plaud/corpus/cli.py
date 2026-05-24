import json
from typing import Literal

import typer

from free_plaud.app.cli_paths import compose_path
from free_plaud.app.config import get_settings
from free_plaud.corpus.ask import answer_corpus_with_citations
from free_plaud.corpus.service import (
    benchmark_corpus_indexing,
    get_corpus_status,
    index_corpus_file,
    index_corpus_path,
    perf_benchmark_corpus,
    rebuild_corpus,
    reset_corpus,
)
from free_plaud.providers.embed import describe_embedding_config, get_embedder
from free_plaud.storage.sqlite import init_sqlite
from free_plaud.storage.vector import LocalVectorStore

app = typer.Typer(help='Comandos para operar o corpus local indexado.', no_args_is_help=True)


@app.command('status')
def status() -> None:
    """Mostra consistencia entre SQLite e Chroma sem modificar dados."""
    settings = get_settings()
    result = get_corpus_status(settings=settings)
    typer.echo(json.dumps(result.model_dump(mode='json'), ensure_ascii=True, indent=2))


@app.command('embedding-info')
def embedding_info() -> None:
    """Mostra modelo de embedding e device efetivo."""
    settings = get_settings()
    result = describe_embedding_config(settings.embedding_model, device=settings.embedding_device)
    typer.echo(json.dumps(result.model_dump(mode='json'), ensure_ascii=True, indent=2))


@app.command('reset')
def reset(
    dry_run: bool = typer.Option(False, '--dry-run', help='Simula a limpeza sem apagar dados.'),
    yes: bool = typer.Option(False, '--yes', help='Executa a limpeza do corpus local.'),
) -> None:
    """Limpa notas/chunks e vetores do corpus ativo com preview seguro."""
    settings = get_settings()
    result = reset_corpus(settings=settings, dry_run=(dry_run or not yes))
    typer.echo(json.dumps(result.model_dump(mode='json'), ensure_ascii=True, indent=2))


@app.command('rebuild')
def rebuild(
    path_parts: list[str] = typer.Argument(..., metavar='PATH'),
    chunk_size: int | None = typer.Option(None, '--chunk-size', min=1),
    overlap: int | None = typer.Option(None, '--overlap', min=0),
    recursive: bool = typer.Option(False, '--recursive', help='Indexa subpastas recursivamente quando PATH for diretorio.'),
    commit_mode: Literal['auto', 'atomic', 'microbatch'] = typer.Option('auto', '--commit-mode'),
    dry_run: bool = typer.Option(False, '--dry-run', help='Simula rebuild sem apagar ou indexar.'),
    yes: bool = typer.Option(False, '--yes', help='Executa reset e indexacao do corpus.'),
) -> None:
    """Reconstroi o corpus ativo a partir de arquivo ou pasta."""
    settings = get_settings()
    target = compose_path(path_parts)
    result = rebuild_corpus(
        target,
        settings=settings,
        chunk_size=chunk_size,
        overlap=overlap,
        recursive=recursive,
        commit_mode=commit_mode,
        dry_run=(dry_run or not yes),
    )
    typer.echo(json.dumps(result.model_dump(mode='json'), ensure_ascii=True, indent=2))
    if result.status == 'failed':
        raise typer.Exit(code=1)


@app.command('index-benchmark')
def index_benchmark(
    files: int = typer.Option(100, '--files', min=1, help='Quantidade de arquivos suportados sinteticos.'),
    repeat: int = typer.Option(2, '--repeat', min=1, help='Quantidade de rodadas sobre o mesmo corpus temporario.'),
    chunk_size: int | None = typer.Option(None, '--chunk-size', min=1),
    overlap: int | None = typer.Option(None, '--overlap', min=0),
    commit_mode: Literal['auto', 'atomic', 'microbatch'] = typer.Option('auto', '--commit-mode'),
) -> None:
    """Mede indexacao de corpus em workspace temporario nao destrutivo."""
    settings = get_settings()
    result = benchmark_corpus_indexing(
        files=files,
        repeat=repeat,
        settings=settings,
        chunk_size=chunk_size,
        overlap=overlap,
        commit_mode=commit_mode,
    )
    typer.echo(json.dumps(result.model_dump(mode='json'), ensure_ascii=True, indent=2))
    if result.status == 'failed':
        raise typer.Exit(code=1)


@app.command('perf-benchmark')
def perf_benchmark(
    files: int = typer.Option(100, '--files', min=1, help='Quantidade de arquivos suportados sinteticos.'),
    repeat: int = typer.Option(1, '--repeat', min=1, help='Quantidade de rodadas de indexacao.'),
    ask_repeat: int = typer.Option(10, '--ask-repeat', min=0, help='Quantidade de perguntas apos indexar.'),
    commit_mode: Literal['auto', 'atomic', 'microbatch'] = typer.Option('auto', '--commit-mode'),
    chunk_size: int | None = typer.Option(None, '--chunk-size', min=1),
    overlap: int | None = typer.Option(None, '--overlap', min=0),
    include_cold_start: bool = typer.Option(False, '--include-cold-start', help='Mede init e primeiro embed do provider.'),
) -> None:
    """Mede performance de indexacao + ask e salva JSON em data/results/corpus_perf."""
    settings = get_settings()
    result = perf_benchmark_corpus(
        files=files,
        repeat=repeat,
        ask_repeat=ask_repeat,
        settings=settings,
        chunk_size=chunk_size,
        overlap=overlap,
        commit_mode=commit_mode,
        include_cold_start=include_cold_start,
    )
    typer.echo(json.dumps(result.model_dump(mode='json'), ensure_ascii=True, indent=2))
    if result.status == 'failed':
        raise typer.Exit(code=1)


@app.command('index')
def index(
    path_parts: list[str] = typer.Argument(..., metavar='PATH'),
    chunk_size: int | None = typer.Option(None, '--chunk-size', min=1),
    overlap: int | None = typer.Option(None, '--overlap', min=0),
    recursive: bool = typer.Option(False, '--recursive', help='Indexa subpastas recursivamente quando PATH for diretorio.'),
    commit_mode: Literal['auto', 'atomic', 'microbatch'] = typer.Option('auto', '--commit-mode'),
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
            commit_mode=commit_mode,
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
        embedder = get_embedder(settings.embedding_model, device=settings.embedding_device)

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
