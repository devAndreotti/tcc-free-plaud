"""Registro de vaults (corpora independentes) em `data_dir/vaults.json`."""

from __future__ import annotations

import json
import os
import re
import shutil
import sqlite3
import unicodedata
from datetime import datetime
from pathlib import Path

from pydantic import BaseModel, ValidationError, field_validator

from escolio.app.config import Settings, get_settings, vault_dir

REGISTRY_FILENAME = "vaults.json"
MIGRATED_VAULT_ID = "obsidian"
DEFAULT_VAULT_NAME = "Obsidian"

# Ids do conjunto de ícones de UI/src/components/Icons.tsx (sem o sufixo "Icon").
VAULT_ICONS = (
    "notes",
    "ask",
    "graph",
    "layers",
    "chart",
    "sparkle",
    "stars",
    "code",
    "folder",
    "mic",
    "vault",
    "file",
)
VAULT_COLORS = ("violet", "blue", "green", "amber", "rose", "teal", "slate")


class VaultError(ValueError):
    """Operacao de vault recusada (regra de negocio ou registro invalido)."""


class Vault(BaseModel):
    id: str
    name: str
    icon: str
    color: str
    folders: list[str] = []
    embedding_model: str | None = None
    created_at: str
    sqlite_path: str | None = None
    vector_store_dir: str | None = None

    @field_validator("icon")
    @classmethod
    def _icon_known(cls, value: str) -> str:
        if value not in VAULT_ICONS:
            raise ValueError(f"icone invalido: {value}")
        return value

    @field_validator("color")
    @classmethod
    def _color_known(cls, value: str) -> str:
        if value not in VAULT_COLORS:
            raise ValueError(f"cor invalida: {value}")
        return value


class VaultRegistry(BaseModel):
    active: str
    vaults: list[Vault]


def registry_path(base: Settings) -> Path:
    return base.data_dir / REGISTRY_FILENAME


def _now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _corpus_roots(sqlite_path: Path) -> list[str]:
    if not sqlite_path.exists():
        return []
    uri = f"file:{sqlite_path.as_posix()}?mode=ro"
    try:
        connection = sqlite3.connect(uri, uri=True)
    except sqlite3.Error:
        return []
    try:
        rows = connection.execute("SELECT root FROM corpus_roots ORDER BY root").fetchall()
    except sqlite3.Error:
        return []
    finally:
        connection.close()
    return [str(row[0]) for row in rows]


def _migrate(base: Settings) -> VaultRegistry:
    roots = _corpus_roots(base.sqlite_path)
    name = Path(roots[0]).name if roots and Path(roots[0]).name else DEFAULT_VAULT_NAME
    vault = Vault(
        id=MIGRATED_VAULT_ID,
        name=name,
        icon="notes",
        color="violet",
        folders=roots,
        embedding_model=base.embedding_model,
        created_at=_now(),
        sqlite_path=str(base.sqlite_path),
        vector_store_dir=str(base.vector_store_dir),
    )
    return VaultRegistry(active=vault.id, vaults=[vault])


def save_registry(registry: VaultRegistry, base: Settings) -> None:
    path = registry_path(base)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    payload = json.dumps(registry.model_dump(), ensure_ascii=False, indent=2) + "\n"
    tmp.write_text(payload, encoding="utf-8")
    os.replace(tmp, path)


def load_registry(base: Settings) -> VaultRegistry:
    path = registry_path(base)
    if not path.exists():
        registry = _migrate(base)
        save_registry(registry, base)
        return registry
    try:
        registry = VaultRegistry.model_validate(json.loads(path.read_text(encoding="utf-8")))
    except (OSError, ValueError, ValidationError) as exc:
        raise VaultError(
            f"vaults.json invalido em {path}: {exc}. Corrija ou remova o arquivo; nada foi sobrescrito."
        ) from exc
    if not any(vault.id == registry.active for vault in registry.vaults):
        raise VaultError(f"vaults.json: vault ativa '{registry.active}' nao existe em {path}.")
    return registry


def _slugify(name: str) -> str:
    ascii_name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_name.lower()).strip("-")
    return slug or "vault"


def _unique_id(name: str, registry: VaultRegistry) -> str:
    taken = {vault.id for vault in registry.vaults}
    base_id = _slugify(name)
    candidate, counter = base_id, 2
    while candidate in taken:
        candidate = f"{base_id}-{counter}"
        counter += 1
    return candidate


def _find(registry: VaultRegistry, vault_id: str) -> Vault:
    for vault in registry.vaults:
        if vault.id == vault_id:
            return vault
    raise VaultError(f"vault nao encontrada: {vault_id}")


def _clean_name(name: str) -> str:
    cleaned = name.strip()
    if not cleaned:
        raise VaultError("o nome da vault nao pode ser vazio")
    return cleaned


def create_vault(
    name: str,
    icon: str,
    color: str,
    folders: list[str],
    base: Settings,
) -> Vault:
    registry = load_registry(base)
    cleaned = _clean_name(name)
    vault = Vault(
        id=_unique_id(cleaned, registry),
        name=cleaned,
        icon=icon,
        color=color,
        folders=[str(folder) for folder in folders],
        embedding_model=base.embedding_model,
        created_at=_now(),
    )
    vault_dir(base, vault.id).mkdir(parents=True, exist_ok=True)
    registry.vaults.append(vault)
    save_registry(registry, base)
    return vault


def update_vault(
    vault_id: str,
    base: Settings,
    *,
    name: str | None = None,
    icon: str | None = None,
    color: str | None = None,
    folders: list[str] | None = None,
) -> Vault:
    registry = load_registry(base)
    current = _find(registry, vault_id)
    patch: dict[str, object] = {}
    if name is not None:
        patch["name"] = _clean_name(name)
    if icon is not None:
        patch["icon"] = icon
    if color is not None:
        patch["color"] = color
    if folders is not None:
        patch["folders"] = [str(folder) for folder in folders]
    updated = Vault.model_validate({**current.model_dump(), **patch})
    registry.vaults[registry.vaults.index(current)] = updated
    save_registry(registry, base)
    return updated


def delete_vault(vault_id: str, base: Settings) -> Vault:
    registry = load_registry(base)
    vault = _find(registry, vault_id)
    if len(registry.vaults) == 1:
        raise VaultError("nao e possivel excluir a unica vault")
    registry.vaults = [item for item in registry.vaults if item.id != vault_id]
    if registry.active == vault_id:
        registry.active = registry.vaults[0].id
    save_registry(registry, base)
    get_settings.cache_clear()
    # So apaga o que o app criou; origem e caminhos customizados (vault migrada) ficam intactos.
    if vault.sqlite_path is None and vault.vector_store_dir is None:
        folder = vault_dir(base, vault.id)
        if folder.exists():
            shutil.rmtree(folder)
    return vault


def set_active(vault_id: str, base: Settings) -> Vault:
    registry = load_registry(base)
    vault = _find(registry, vault_id)
    registry.active = vault_id
    save_registry(registry, base)
    get_settings.cache_clear()
    return vault


def active_vault(base: Settings) -> Vault:
    registry = load_registry(base)
    return _find(registry, registry.active)
