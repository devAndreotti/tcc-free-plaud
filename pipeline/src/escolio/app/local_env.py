import os
from pathlib import Path

from escolio.app.config import Settings, get_settings
from escolio.app.legacy import LEGACY_ENV_PREFIX

ANSWER_API_KEY_ENV = 'ESCOLIO_ANSWER_API_KEY'
LEGACY_ANSWER_API_KEY_ENV = LEGACY_ENV_PREFIX + 'ANSWER_API_KEY'


def local_env_path_for(settings: Settings | None = None) -> Path:
    resolved = settings or get_settings()
    return resolved.workspace_dir / 'pipeline' / '.env'


def _parse_env_line(line: str) -> tuple[str, str] | None:
    stripped = line.strip()
    if not stripped or stripped.startswith('#') or '=' not in stripped:
        return None
    key, value = stripped.split('=', 1)
    key = key.strip()
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        value = value[1:-1]
    return key, value


def _read_env_value(path: Path, key: str) -> str | None:
    if not path.exists():
        return None
    for line in path.read_text(encoding='utf-8').splitlines():
        parsed = _parse_env_line(line)
        if parsed is not None and parsed[0] == key:
            return parsed[1]
    return None


def _format_env_value(key: str, value: str) -> str:
    if any(char.isspace() or char == '#' for char in value):
        escaped = value.replace('\\', '\\\\').replace('"', '\\"')
        return f'{key}="{escaped}"'
    return f'{key}={value}'


def upsert_local_env_value(key: str, value: str | None, *, settings: Settings | None = None) -> Path:
    path = local_env_path_for(settings)
    lines = path.read_text(encoding='utf-8').splitlines() if path.exists() else []
    next_lines: list[str] = []
    found = False
    cleaned_value = value.strip() if value is not None else ''

    for line in lines:
        parsed = _parse_env_line(line)
        if parsed is not None and parsed[0] == key:
            found = True
            if cleaned_value:
                next_lines.append(_format_env_value(key, cleaned_value))
            continue
        next_lines.append(line)

    if cleaned_value and not found:
        next_lines.append(_format_env_value(key, cleaned_value))

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('\n'.join(next_lines).rstrip() + ('\n' if next_lines else ''), encoding='utf-8')
    return path


def load_local_env(*, settings: Settings | None = None, override: bool = False) -> None:
    path = local_env_path_for(settings)
    if not path.exists():
        return
    for line in path.read_text(encoding='utf-8').splitlines():
        parsed = _parse_env_line(line)
        if parsed is None:
            continue
        key, value = parsed
        if override or key not in os.environ:
            os.environ[key] = value


def _remove_legacy_answer_key_line(*, settings: Settings | None = None) -> None:
    path = local_env_path_for(settings)
    if path.exists() and _read_env_value(path, LEGACY_ANSWER_API_KEY_ENV) is not None:
        upsert_local_env_value(LEGACY_ANSWER_API_KEY_ENV, None, settings=settings)


def save_answer_api_key(api_key: str, *, settings: Settings | None = None) -> Path:
    """Grava a chave como ESCOLIO_ANSWER_API_KEY e migra o .env (remove a linha FREE_PLAUD_ antiga)."""
    cleaned = api_key.strip()
    path = upsert_local_env_value(ANSWER_API_KEY_ENV, cleaned or None, settings=settings)
    _remove_legacy_answer_key_line(settings=settings)
    os.environ.pop(LEGACY_ANSWER_API_KEY_ENV, None)
    if cleaned:
        os.environ[ANSWER_API_KEY_ENV] = cleaned
    else:
        os.environ.pop(ANSWER_API_KEY_ENV, None)
    get_settings.cache_clear()
    return path


def answer_api_key_is_configured(*, settings: Settings | None = None) -> bool:
    if os.environ.get(ANSWER_API_KEY_ENV) or os.environ.get(LEGACY_ANSWER_API_KEY_ENV):
        return True
    path = local_env_path_for(settings)
    return bool(_read_env_value(path, ANSWER_API_KEY_ENV) or _read_env_value(path, LEGACY_ANSWER_API_KEY_ENV))
