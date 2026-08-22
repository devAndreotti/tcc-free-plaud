import json
from typing import Literal

import typer

from free_plaud.providers.answer import test_answer_provider
from free_plaud.providers.model_discovery import list_answer_models
from free_plaud.providers.provisioning import (
    MODEL_CATALOG,
    PullProgress,
    catalog_entry,
    detect_runtime,
    ensure_model,
)
from free_plaud.providers.smoke import run_provider_smoke_local

app = typer.Typer(help='Opera providers de resposta LLM.', no_args_is_help=True)


@app.command('test-answer')
def test_answer() -> None:
    result = test_answer_provider()
    typer.echo(json.dumps(result.model_dump(mode='json'), ensure_ascii=True, indent=2))


@app.command('list-models')
def list_models() -> None:
    result = list_answer_models()
    typer.echo(json.dumps(result.model_dump(mode='json'), ensure_ascii=True, indent=2))


@app.command('catalog')
def catalog() -> None:
    """Lista os presets de modelo local curados (velocidade vs qualidade)."""
    entries = [
        {
            'catalog_id': entry.catalog_id,
            'label': entry.label,
            'pull_name': entry.pull_name,
            'parameter_size': entry.parameter_size,
            'quantization': entry.quantization,
            'context_tokens': entry.context_tokens,
            'min_vram_gb': entry.min_vram_gb,
            'profile': entry.profile,
        }
        for entry in MODEL_CATALOG
    ]
    typer.echo(json.dumps(entries, ensure_ascii=True, indent=2))


@app.command('status')
def status() -> None:
    """Diagnostica se o runtime local esta pronto e se o modelo esta instalado."""
    report = detect_runtime()
    typer.echo(json.dumps(report.model_dump(mode='json'), ensure_ascii=True, indent=2))


@app.command('pull')
def pull(model: str = typer.Argument(..., metavar='MODEL', help='catalog_id (ex: gemma-veloz) ou tag Ollama.')) -> None:
    """Baixa o modelo quantizado via Ollama, mostrando o progresso do download."""
    entry = catalog_entry(model)
    target = entry.pull_name if entry else model

    def _print_progress(progress: PullProgress) -> None:
        if progress.completed is not None and progress.total:
            pct = (progress.completed / progress.total) * 100
            typer.echo(f'{progress.status}: {pct:.1f}%', err=True)
        else:
            typer.echo(progress.status, err=True)

    result = ensure_model(target, on_progress=_print_progress)
    typer.echo(json.dumps(result.model_dump(mode='json'), ensure_ascii=True, indent=2))
    if not result.ok:
        raise typer.Exit(code=1)


@app.command('smoke-local')
def smoke_local(
    strategy: Literal['lexical', 'vector', 'hybrid'] = typer.Option(
        'lexical',
        '--strategy',
        help='Estrategia do Ask: lexical, vector ou hybrid.',
    ),
    top_k: int = typer.Option(4, '--top-k', min=1, max=20, help='Quantidade de chunks recuperados no smoke.'),
    keep_workspace: bool = typer.Option(False, '--keep-workspace', help='Mantem pasta temporaria do smoke para depuracao.'),
) -> None:
    """Roda smoke local opcional com corpus temporario C/D e pergunta inexistente."""
    result = run_provider_smoke_local(strategy=strategy, top_k=top_k, keep_workspace=keep_workspace)
    typer.echo(json.dumps(result.model_dump(mode='json'), ensure_ascii=True, indent=2))
