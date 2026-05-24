import json
from typing import Any

import typer

from free_plaud.app.config import editable_settings_payload, get_settings, reset_user_settings, save_user_settings, user_settings_path_for

app = typer.Typer(help='Configura preferencias do app em user_settings.json.', no_args_is_help=True)


def _parse_value(raw: str) -> Any:
    cleaned = raw.strip()
    if cleaned.lower() in {'true', 'false'}:
        return cleaned.lower() == 'true'
    if cleaned.lower() in {'null', 'none', ''}:
        return None
    try:
        return int(cleaned)
    except ValueError:
        return cleaned


@app.command('show')
def show() -> None:
    settings = get_settings()
    payload = {
        'path': str(user_settings_path_for(settings)),
        'settings': editable_settings_payload(settings),
    }
    typer.echo(json.dumps(payload, ensure_ascii=True, indent=2))


@app.command('set')
def set_value(key: str, value: str) -> None:
    updated = save_user_settings({key: _parse_value(value)})
    typer.echo(json.dumps(editable_settings_payload(updated), ensure_ascii=True, indent=2))


@app.command('reset')
def reset() -> None:
    settings = reset_user_settings()
    typer.echo(json.dumps(editable_settings_payload(settings), ensure_ascii=True, indent=2))
