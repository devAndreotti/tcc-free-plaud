from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table

from free_plaud.app.config import get_settings, reset_user_settings, user_settings_path_for
from free_plaud.app.local_env import local_env_path_for, save_answer_api_key
from free_plaud.app.settings_catalog import get_setting_spec, save_catalog_setting, settings_catalog_payload
from free_plaud.app.settings_presets import apply_settings_preset, list_settings_presets, preview_settings_preset
from free_plaud.corpus.runtime import CorpusRuntime
from free_plaud.providers.model_discovery import list_answer_models

console = Console()
PURPLE = '#a21caf'
PURPLE_DIM = '#7c3aed'
PINK = '#e84fe6'
TEXT = '#f8f0ff'
TEXT_DIM = '#c4b5fd'


def _print_header() -> None:
    console.print(Panel(f'[bold {TEXT}]free-plaud terminal[/bold {TEXT}]  [{TEXT_DIM}]v0.1[/{TEXT_DIM}]', border_style=PURPLE))


def _clear_screen() -> None:
    if console.is_terminal:
        console.clear()


def _layer_label(layer: str) -> str:
    return 'Simples' if layer == 'simple' else 'Avancado'


def _settings_rows() -> list[dict[str, object]]:
    return settings_catalog_payload()


def _show_settings_table() -> None:
    settings = get_settings()
    table = Table(title=f'Configuracoes ({user_settings_path_for(settings)})', border_style=PURPLE_DIM)
    table.add_column('#', justify='right')
    table.add_column('camada')
    table.add_column('grupo')
    table.add_column('campo')
    table.add_column('valor')
    table.add_column('descricao')
    for row in settings_catalog_payload(settings):
        value = row['display_value']
        if row['warning']:
            value = f'{value} [yellow](!)[/yellow]'
        table.add_row(str(row['index']), _layer_label(str(row['layer'])), row['group'], row['label'], str(value), row['description'])
    console.print(table)
    console.print(f'[{TEXT_DIM}]local_env: {local_env_path_for(settings)}[/{TEXT_DIM}]')


def _preset_changes_text(changes) -> str:  # noqa: ANN001
    if not changes:
        return 'Sem mudancas em relacao a configuracao atual.'
    return '\n'.join(f'- {key}: {change.before} -> {change.after}' for key, change in changes.items())


def _show_presets_table() -> None:
    table = Table(title='Presets', border_style=PURPLE_DIM)
    table.add_column('preset')
    table.add_column('uso')
    table.add_column('valores')
    for preset in list_settings_presets():
        values = ', '.join(f'{key}={value}' for key, value in preset.values.items())
        table.add_row(preset.key, preset.description, values)
    console.print(table)


def _presets_menu(runtime: CorpusRuntime) -> None:
    _show_presets_table()
    keys = [preset.key for preset in list_settings_presets()]
    preset_key = Prompt.ask('Preset', choices=keys, default='cpu_rapido')
    action = Prompt.ask('Acao', choices=['preview', 'apply'], default='preview')
    if action == 'preview':
        preview = preview_settings_preset(preset_key)
        console.print(Panel(_preset_changes_text(preview.changes), title=f'Preview {preset_key}', border_style=PURPLE_DIM))
        return
    result = apply_settings_preset(preset_key)
    runtime.clear()
    console.print(Panel(_preset_changes_text(result.changes), title=f'Preset aplicado: {preset_key}', border_style='green'))


def _models_menu(runtime: CorpusRuntime) -> None:
    result = list_answer_models()
    border = 'green' if result.status == 'ok' else 'yellow' if result.status in {'not_applicable', 'offline'} else 'red'
    header = (
        f'provider={result.provider}\n'
        f'base_url={result.base_url or "-"}\n'
        f'status={result.status}\n'
        f'latencia_ms={result.latency_ms}\n'
        f'cached={result.cached}\n'
        f'mensagem={result.message or "-"}'
    )
    console.print(Panel(header, title='Listar modelos', border_style=border))
    if not result.models:
        return

    table = Table(title='Modelos encontrados', border_style=PURPLE_DIM)
    table.add_column('#', justify='right')
    table.add_column('modelo')
    for index, model in enumerate(result.models, start=1):
        table.add_row(str(index), model.label)
    console.print(table)

    choices = [str(index) for index in range(1, len(result.models) + 1)]
    choice = Prompt.ask('Escolha modelo ou ENTER para manter', choices=[*choices, ''], default='')
    if not choice:
        return
    selected = result.models[int(choice) - 1]
    save_catalog_setting('answer_model', selected.id)
    runtime.clear()
    console.print(f'[green]answer_model salvo: {selected.id}[/green]')


def _print_catalog_warnings() -> None:
    warnings = [row for row in settings_catalog_payload() if row['warning']]
    for row in warnings:
        console.print(f'[yellow]{row["label"]}: {row["warning"]}[/yellow]')


def _print_setting_choices() -> None:
    rows = _settings_rows()
    for layer in ('simple', 'advanced'):
        console.print(f'[bold {PINK}]{_layer_label(layer)}[/bold {PINK}]')
        for row in rows:
            if row['layer'] == layer:
                console.print(f'[{TEXT_DIM}][{row["index"]}][/{TEXT_DIM}] {row["label"]} ({row["key"]})')
        console.print()
    console.print(f'[{TEXT_DIM}][P][/{TEXT_DIM}] Presets')
    console.print(f'[{TEXT_DIM}][M][/{TEXT_DIM}] Listar modelos do provider')
    console.print(f'[{TEXT_DIM}][R][/{TEXT_DIM}] Resetar user_settings.json')
    console.print()


def settings_menu(runtime: CorpusRuntime) -> None:
    _clear_screen()
    _print_header()
    _show_settings_table()
    _print_catalog_warnings()
    console.print()
    _print_setting_choices()
    choice = Prompt.ask('Setting', default='0')
    if choice == '0':
        return
    if choice.lower() == 'p':
        _presets_menu(runtime)
        return
    if choice.lower() == 'm':
        _models_menu(runtime)
        return
    if choice.lower() == 'r':
        reset_user_settings()
        runtime.clear()
        console.print('[green]Configuracoes resetadas.[/green]')
        return
    rows = _settings_rows()
    selected = next((row for row in rows if str(row['index']) == choice), None)
    if selected is None:
        console.print('[yellow]Opcao invalida.[/yellow]')
        return
    spec = get_setting_spec(str(selected['key']))
    if selected['key'] == 'answer_api_key':
        value = Prompt.ask('FREE_PLAUD_ANSWER_API_KEY (vazio remove)', password=console.is_terminal, default='')
        path = save_answer_api_key(value)
        runtime.clear()
        if value.strip():
            console.print(f'[green]answer_api_key salva em {path}.[/green]')
        else:
            console.print(f'[green]answer_api_key removida de {path}.[/green]')
        return
    choices = [option.value for option in spec.options] or None
    current = selected['value']
    value = Prompt.ask(spec.label, choices=choices, default='' if current is None else str(current))
    save_catalog_setting(spec.key, value)
    runtime.clear()
    console.print(f'[green]{spec.label} salvo.[/green]')
