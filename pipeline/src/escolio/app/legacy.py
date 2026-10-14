"""Compatibilidade com os nomes anteriores do projeto (free-plaud).

Centraliza tudo que aceita nomes antigos: variaveis FREE_PLAUD_*, o SQLite
free_plaud.sqlite3 e a collection free_plaud_chunks. Quem usa o nome novo
nunca cai aqui; o fallback so entra quando o novo nome nao existe.
"""

import os
from collections.abc import Iterable
from pathlib import Path

from dotenv import dotenv_values

ENV_PREFIX = 'ESCOLIO_'
LEGACY_ENV_PREFIX = 'FREE_PLAUD_'
DEFAULT_SQLITE_FILENAME = 'escolio.sqlite3'
LEGACY_SQLITE_FILENAME = 'free_plaud.sqlite3'
DEFAULT_CHROMA_COLLECTION = 'escolio_chunks'
LEGACY_CHROMA_COLLECTION = 'free_plaud_chunks'


def legacy_env_values(field_names: Iterable[str], env_files: Iterable[str | Path]) -> dict[str, str]:
    """Valores FREE_PLAUD_* (do ambiente e dos .env) para campos que ainda nao tem ESCOLIO_*.

    Ordem de prioridade: ambiente acima de .env; .env posterior acima do anterior.
    Quem chama deve colocar esta fonte abaixo das fontes ESCOLIO_*.
    """
    names = list(field_names)
    values: dict[str, str] = {}
    for path in env_files:
        file_path = Path(path)
        if not file_path.is_file():
            continue
        for key, value in dotenv_values(file_path).items():
            if value is None or not key or not key.startswith(LEGACY_ENV_PREFIX):
                continue
            field = key[len(LEGACY_ENV_PREFIX):].lower()
            if field in names:
                values[field] = value
    for field in names:
        legacy_key = LEGACY_ENV_PREFIX + field.upper()
        if legacy_key in os.environ:
            values[field] = os.environ[legacy_key]
    return values


def resolve_legacy_sqlite_path(path: Path) -> Path:
    """Usa free_plaud.sqlite3 quando o escolio.sqlite3 padrao ainda nao existe."""
    if path.name != DEFAULT_SQLITE_FILENAME or path.exists():
        return path
    legacy = path.with_name(LEGACY_SQLITE_FILENAME)
    return legacy if legacy.exists() else path
