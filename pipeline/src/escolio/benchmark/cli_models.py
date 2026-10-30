"""Comando `compare-models`: roda o compare uma vez por modelo na mesma suíte."""

import json
from pathlib import Path
from typing import get_args

import typer

from escolio.app.config import get_settings
from escolio.app.paths import ensure_runtime_dirs
from escolio.benchmark.datasets import load_benchmark_suite
from escolio.benchmark.model_compare import (
    NOME_RELATORIO,
    arquivos_da_suite,
    build_models_report,
    comparar_modelos,
    gravar_registros,
    hash_suite,
    parse_modelos,
)
from escolio.benchmark.runners import benchmark_compare_dir
from escolio.benchmark.service import build_settings_snapshot
from escolio.providers.answer import AnswerProviderName, get_answer_provider
from escolio.providers.embed import (
    EmbeddingConfigurationError,
    get_embedder,
    validate_runtime_embedding_model,
)

ANSWER_PROVIDER_NAMES = get_args(AnswerProviderName)


def compare_models(
    suite_path: Path = typer.Option(..., '--suite', '-u', help="Manifesto JSON com casos de benchmark."),
    models: str = typer.Option(..., '--models', '-m', help="Modelos separados por vírgula, ex.: qchat:latest,qwen2.5:7b."),
    saida_dir: Path = typer.Option(..., '--saida-dir', help="Pasta dos JSONs por modelo e do relatório Markdown."),
    answer_provider: str = typer.Option('ollama', '--answer-provider', help="Provider generativo: ollama, lmstudio ou openai-compatible."),
    answer_base_url: str | None = typer.Option(None, '--answer-base-url', help="Base URL do provider (padrão: a do provider ou das settings)."),
    top_k: int = typer.Option(3, '--top-k', min=1),
    chunk_size: int = typer.Option(800, '--chunk-size', min=1),
    overlap: int = typer.Option(120, '--overlap', min=0),
    embedding_model: str | None = typer.Option(None, '--embedding-model', help="Override do embedding model da comparacao vetorial."),
) -> None:
    """Roda o compare uma vez por modelo na mesma suíte e grava um JSON por modelo e um relatório único."""
    settings = get_settings()
    ensure_runtime_dirs(settings)
    suite = load_benchmark_suite(suite_path)
    try:
        alvos = parse_modelos(models)
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from None
    if answer_provider not in ANSWER_PROVIDER_NAMES or answer_provider == 'extractive':
        raise typer.BadParameter("answer-provider deve ser ollama, lmstudio ou openai-compatible.")
    resolved_embedding_model = embedding_model or settings.embedding_model
    try:
        validate_runtime_embedding_model(resolved_embedding_model)
    except EmbeddingConfigurationError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from None

    def fabrica(alvo):
        return get_answer_provider(
            answer_provider,  # type: ignore[arg-type]
            model=alvo.modelo,
            base_url=answer_base_url or settings.answer_base_url,
            api_key=settings.answer_api_key,
            temperature=settings.answer_temperature,
            max_tokens=settings.answer_max_tokens,
            timeout_seconds=settings.answer_timeout_seconds,
        )

    suite_hash = hash_suite(arquivos_da_suite(suite_path, suite, settings.workspace_dir))
    embedder = get_embedder(resolved_embedding_model, device=settings.embedding_device)
    registros = comparar_modelos(
        suite,
        alvos,
        workspace_dir=settings.workspace_dir,
        trabalho_dir=benchmark_compare_dir(settings.results_dir, suite.suite_name) / 'modelos',
        provider_name=answer_provider,
        fabrica=fabrica,
        embedder=embedder,
        suite_hash=suite_hash,
        top_k=top_k,
        chunk_size=chunk_size,
        overlap=overlap,
        settings_snapshot=build_settings_snapshot(settings),
    )
    caminhos = gravar_registros(registros, saida_dir)
    comando = (
        f'python -m escolio benchmark compare-models --suite {suite_path} --models {models} '
        f'--answer-provider {answer_provider} --saida-dir {saida_dir}'
    )
    relatorio = saida_dir / NOME_RELATORIO
    relatorio.write_text(build_models_report(registros, comando=comando), encoding='utf-8', newline='\n')
    payload = {
        'ok': any(registro.erro is None for registro in registros),
        'relatorio': str(relatorio),
        'modelos': [
            {'modelo': registro.metadados.modelo, 'erro': registro.erro, 'json': str(caminhos[registro.metadados.modelo])}
            for registro in registros
        ],
    }
    typer.echo(json.dumps(payload, ensure_ascii=True, indent=2))
    if not payload['ok']:
        raise typer.Exit(code=1)
