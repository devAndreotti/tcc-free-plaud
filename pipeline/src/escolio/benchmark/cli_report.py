"""Comandos `report-ia` e `faithfulness`: relatórios e avaliação offline do benchmark."""

import json
from pathlib import Path

import typer

from escolio.benchmark.compare_flags import gravar_faithfulness
from escolio.benchmark.faithfulness import (
    build_faithfulness_report,
    make_openai_compatible_judge,
)
from escolio.benchmark.ia_report import build_ia_report
from escolio.benchmark.runners import BenchmarkComparisonResult
from escolio.providers.answer import AnswerProviderError


def report_ia(
    extractive_path: Path = typer.Option(..., '--extractive', help="JSON do compare com a resposta extrativa."),
    generativo_path: Path = typer.Option(..., '--generativo', help="JSON do compare com o provider generativo."),
    saida: Path = typer.Option(..., '--saida', help="Arquivo Markdown de saída."),
) -> None:
    """Monta o relatório em Markdown com a IA local contra o extractive."""
    extractive = BenchmarkComparisonResult.model_validate_json(extractive_path.read_text(encoding='utf-8'))
    generativo = BenchmarkComparisonResult.model_validate_json(generativo_path.read_text(encoding='utf-8'))
    try:
        markdown = build_ia_report(extractive, generativo)
    except ValueError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from None
    saida.parent.mkdir(parents=True, exist_ok=True)
    saida.write_text(markdown, encoding='utf-8', newline='\n')
    typer.echo(json.dumps({'ok': True, 'saida': str(saida)}, ensure_ascii=True, indent=2))


def faithfulness(
    results_path: Path = typer.Option(..., '--results', help="JSON do compare com --registrar-respostas."),
    judge_model: str = typer.Option(..., '--judge-model', help="Modelo juiz; use um modelo forte e rode offline."),
    judge_base_url: str = typer.Option(..., '--judge-base-url', help="Base URL OpenAI-compatible do juiz."),
    saida: Path = typer.Option(..., '--saida', help="Arquivo JSON de saída."),
    judge_api_key: str | None = typer.Option(None, '--judge-api-key', help="Chave do juiz, se o endpoint exigir."),
    timeout: int = typer.Option(120, '--timeout', min=1, help="Timeout por chamada ao juiz, em segundos."),
    mesclar_em: Path | None = typer.Option(None, '--mesclar-em', help="JSON do compare onde gravar a chave faithfulness (além do --saida)."),
    estrategia: str | None = typer.Option(None, '--estrategia', help="Estratégia do bloco faithfulness (padrão: a do chat, default_ask_strategy)."),
) -> None:
    """Faithfulness semântica com juiz LLM (offline; fora do gate do CI)."""
    comparison = BenchmarkComparisonResult.model_validate_json(results_path.read_text(encoding='utf-8'))
    try:
        judge = make_openai_compatible_judge(judge_base_url, judge_model, api_key=judge_api_key, timeout=timeout)
        report = build_faithfulness_report(comparison, judge, judge_model=judge_model, judge_base_url=judge_base_url)
        payload = gravar_faithfulness(
            report, comparison, saida=saida, mesclar_em=mesclar_em, estrategia=estrategia
        )
    except (ValueError, AnswerProviderError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from None
    typer.echo(json.dumps(payload, ensure_ascii=True, indent=2))
