import json
from typing import Literal

import typer

from free_plaud.providers.answer import test_answer_provider
from free_plaud.providers.model_discovery import list_answer_models
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
