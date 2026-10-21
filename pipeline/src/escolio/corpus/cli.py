import json
from typing import Literal

import typer

from escolio.app.cli_paths import compose_path
from escolio.app.config import get_settings
from escolio.corpus.ask import answer_corpus_with_citations
from escolio.corpus.service import (
    benchmark_corpus_indexing,
    get_corpus_status,
    index_corpus_file,
    index_corpus_path,
    perf_benchmark_corpus,
    rebuild_corpus,
    reset_corpus,
)
from escolio.providers.answer import get_answer_provider
from escolio.providers.embed import (
    EmbeddingConfigurationError,
    describe_embedding_config,
    get_embedder,
    validate_runtime_embedding_model,
)
from escolio.storage.sqlite import init_sqlite
from escolio.storage.vector import LocalVectorStore

app = typer.Typer(help='Comandos para operar o corpus local indexado.', no_args_is_help=True)


@app.command('status')
def status() -> None:
    """Mostra consistência entre SQLite e Chroma sem modificar dados."""
    settings = get_settings()
    result = get_corpus_status(settings=settings)
    typer.echo(json.dumps(result.model_dump(mode='json'), ensure_ascii=True, indent=2))


@app.command('embedding-info')
def embedding_info() -> None:
    """Mostra o modelo de busca semântica e o dispositivo efetivo."""
    settings = get_settings()
    result = describe_embedding_config(settings.embedding_model, device=settings.embedding_device)
    typer.echo(json.dumps(result.model_dump(mode='json'), ensure_ascii=True, indent=2))


@app.command('reset')
def reset(
    dry_run: bool = typer.Option(False, '--dry-run', help='Simula a limpeza sem apagar dados.'),
    yes: bool = typer.Option(False, '--yes', help='Executa a limpeza do corpus local.'),
) -> None:
    """Limpa notas, trechos e vetores do corpus ativo com prévia segura."""
    settings = get_settings()
    result = reset_corpus(settings=settings, dry_run=(dry_run or not yes))
    typer.echo(json.dumps(result.model_dump(mode='json'), ensure_ascii=True, indent=2))


@app.command('rebuild')
def rebuild(
    path_parts: list[str] = typer.Argument(..., metavar='PATH'),
    chunk_size: int | None = typer.Option(None, '--chunk-size', min=1),
    overlap: int | None = typer.Option(None, '--overlap', min=0),
    recursive: bool = typer.Option(False, '--recursive', help='Indexa subpastas recursivamente quando PATH for uma pasta.'),
    commit_mode: Literal['auto', 'atomic', 'microbatch'] = typer.Option('auto', '--commit-mode'),
    dry_run: bool = typer.Option(False, '--dry-run', help='Simula rebuild sem apagar ou indexar.'),
    yes: bool = typer.Option(False, '--yes', help='Executa reset e indexação do corpus.'),
) -> None:
    """Reconstrói o corpus ativo a partir de arquivo ou pasta."""
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
    files: int = typer.Option(100, '--files', min=1, help='Quantidade de arquivos suportados sintéticos.'),
    repeat: int = typer.Option(2, '--repeat', min=1, help='Quantidade de rodadas sobre o mesmo corpus temporário.'),
    chunk_size: int | None = typer.Option(None, '--chunk-size', min=1),
    overlap: int | None = typer.Option(None, '--overlap', min=0),
    commit_mode: Literal['auto', 'atomic', 'microbatch'] = typer.Option('auto', '--commit-mode'),
) -> None:
    """Mede a indexação de corpus em workspace temporário e não destrutivo."""
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
    files: int = typer.Option(100, '--files', min=1, help='Quantidade de arquivos suportados sintéticos.'),
    repeat: int = typer.Option(1, '--repeat', min=1, help='Quantidade de rodadas de indexação.'),
    ask_repeat: int = typer.Option(10, '--ask-repeat', min=0, help='Quantidade de perguntas após indexar.'),
    commit_mode: Literal['auto', 'atomic', 'microbatch'] = typer.Option('auto', '--commit-mode'),
    chunk_size: int | None = typer.Option(None, '--chunk-size', min=1),
    overlap: int | None = typer.Option(None, '--overlap', min=0),
    include_cold_start: bool = typer.Option(False, '--include-cold-start', help='Mede a inicialização e o primeiro uso do modelo de busca semântica.'),
) -> None:
    """Mede o desempenho da indexação e das perguntas e salva JSON em data/results/corpus_perf."""
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
    recursive: bool = typer.Option(False, '--recursive', help='Indexa subpastas recursivamente quando PATH for uma pasta.'),
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
    top_k: int | None = typer.Option(
        None,
        '--top-k',
        min=1,
        help='Quantidade máxima de trechos recuperados. Sem a opção, usa a configuração de trechos por pergunta.',
    ),
    strategy: Literal['lexical', 'vector', 'hybrid'] = typer.Option(
        'hybrid',
        '--strategy',
        '-s',
        help='Estratégia de recuperação: lexical, vector ou hybrid.',
    ),
    debug: bool = typer.Option(False, '--debug', help='Inclui sinais de recuperação para ajuste do Ask.'),
    root: str | None = typer.Option(None, '--root', help='Restringe a pergunta às notas sob esta pasta indexada.'),
) -> None:
    """Pergunta contra todos os trechos persistidos no corpus local."""
    settings = get_settings()
    connection = init_sqlite(settings.sqlite_path)
    vector_store = None
    embedder = None
    if strategy in {'vector', 'hybrid'}:
        try:
            validate_runtime_embedding_model(settings.embedding_model)
        except EmbeddingConfigurationError as exc:
            connection.close()
            typer.echo(str(exc), err=True)
            raise typer.Exit(code=1) from None
        vector_store = LocalVectorStore(settings.vector_store_dir, collection_name=settings.vector_collection_name)
        try:
            embedder = get_embedder(settings.embedding_model, device=settings.embedding_device)
        except EmbeddingConfigurationError as exc:
            connection.close()
            typer.echo(str(exc), err=True)
            raise typer.Exit(code=1) from None

    try:
        response = answer_corpus_with_citations(
            question,
            connection=connection,
            vector_store=vector_store,
            embedder=embedder,
            strategy=strategy,
            top_k=top_k or settings.retrieval_top_k,
            include_debug=debug,
            source_root=root,
            answer_provider=get_answer_provider(
                settings.answer_provider,
                model=settings.answer_model,
                base_url=settings.answer_base_url,
                api_key=settings.answer_api_key,
                temperature=settings.answer_temperature,
                max_tokens=settings.answer_max_tokens,
                timeout_seconds=settings.answer_timeout_seconds,
            ),
        )
        payload = response.model_dump(mode='json') if debug else response.model_dump(mode='json', exclude={'debug'})
        typer.echo(json.dumps(payload, ensure_ascii=True, indent=2))
    finally:
        connection.close()
