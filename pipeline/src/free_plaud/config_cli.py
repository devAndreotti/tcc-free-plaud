import json
from typing import Any

import typer

from free_plaud.app.config import (
    editable_settings_payload,
    get_settings,
    reset_user_settings,
    save_user_settings,
    user_settings_path_for,
)
from free_plaud.app.settings_presets import (
    apply_settings_preset,
    list_settings_presets,
    preview_settings_preset,
)

app = typer.Typer(help='Configura preferencias do app em user_settings.json.', no_args_is_help=True)
preset_app = typer.Typer(help='Lista, previsualiza e aplica presets transacionais.', no_args_is_help=True)


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


@preset_app.command('list')
def list_presets() -> None:
    payload = [preset.model_dump(mode='json') for preset in list_settings_presets()]
    typer.echo(json.dumps(payload, ensure_ascii=True, indent=2))


@preset_app.command('preview')
def preview_preset(name: str) -> None:
    preview = preview_settings_preset(name)
    payload = {
        'preset': preview.preset.model_dump(mode='json'),
        'values': preview.values,
        'changes': {key: change.model_dump(mode='json') for key, change in preview.changes.items()},
    }
    typer.echo(json.dumps(payload, ensure_ascii=True, indent=2))


@preset_app.command('apply')
def apply_preset(name: str) -> None:
    result = apply_settings_preset(name)
    payload = {
        'preset': result.preset.model_dump(mode='json'),
        'values': result.values,
        'changes': {key: change.model_dump(mode='json') for key, change in result.changes.items()},
        'settings': editable_settings_payload(result.settings),
    }
    typer.echo(json.dumps(payload, ensure_ascii=True, indent=2))


app.add_typer(preset_app, name='preset')
