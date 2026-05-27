import json

import typer

from free_plaud.providers.answer import test_answer_provider
from free_plaud.providers.model_discovery import list_answer_models

app = typer.Typer(help='Opera providers de resposta LLM.', no_args_is_help=True)


@app.command('test-answer')
def test_answer() -> None:
    result = test_answer_provider()
    typer.echo(json.dumps(result.model_dump(mode='json'), ensure_ascii=True, indent=2))


@app.command('list-models')
def list_models() -> None:
    result = list_answer_models()
    typer.echo(json.dumps(result.model_dump(mode='json'), ensure_ascii=True, indent=2))
