import importlib.util
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest
from typer.testing import CliRunner

from escolio.app.config import Settings, get_settings, settings_for_vault
from escolio.app.vaults import (
    VaultError,
    create_vault,
    delete_vault,
    load_registry,
    registry_path,
    set_active,
    update_vault,
)
from escolio.storage.sqlite import init_sqlite, list_corpus_roots


def _base(root: Path) -> Settings:
    data = root / "data"
    return Settings(
        data_dir=data,
        results_dir=data / "results",
        sqlite_path=data / "results" / "escolio.sqlite3",
        vector_store_dir=data / "results" / "vector_store",
        notes_dir=data / "corpus" / "notes",
    )


def _add_corpus_root(base: Settings, root: Path) -> None:
    connection = init_sqlite(base.sqlite_path)
    try:
        connection.execute(
            "INSERT INTO corpus_roots (root, last_indexed_at) VALUES (?, ?)",
            (str(root), datetime.now(UTC).isoformat()),
        )
        connection.commit()
    finally:
        connection.close()


def test_vault_migra_banco_existente_sem_vaults_json(tmp_path: Path) -> None:
    base = _base(tmp_path)
    origin = tmp_path / "Obsidian-Core"
    origin.mkdir()
    _add_corpus_root(base, origin)
    assert not registry_path(base).exists()

    registry = load_registry(base)

    assert registry.active == "obsidian"
    assert [v.id for v in registry.vaults] == ["obsidian"]
    vault = registry.vaults[0]
    assert vault.name == "Obsidian-Core"
    assert vault.folders == [str(origin)]
    assert vault.sqlite_path == str(base.sqlite_path)
    assert vault.vector_store_dir == str(base.vector_store_dir)
    assert vault.embedding_model == base.embedding_model
    assert registry_path(base).exists()


def test_vault_migra_sem_banco_usa_nome_padrao(tmp_path: Path) -> None:
    registry = load_registry(_base(tmp_path))
    assert registry.vaults[0].name == "Obsidian"
    assert registry.vaults[0].folders == []


def test_vault_registro_invalido_levanta_erro_sem_sobrescrever(tmp_path: Path) -> None:
    base = _base(tmp_path)
    path = registry_path(base)
    path.parent.mkdir(parents=True)
    path.write_text("{ nao e json", encoding="utf-8")

    with pytest.raises(VaultError, match="vaults.json invalido"):
        load_registry(base)
    assert path.read_text(encoding="utf-8") == "{ nao e json"


def test_vault_create_gera_slug_unico_e_bancos_isolados(tmp_path: Path) -> None:
    base = _base(tmp_path)
    first = create_vault("Culinária", "layers", "amber", [], base)
    second = create_vault("Culinaria", "layers", "rose", [], base)
    assert first.id == "culinaria"
    assert second.id == "culinaria-2"
    assert first.embedding_model == base.embedding_model
    assert (base.data_dir / "vaults" / first.id).is_dir()

    settings_a = settings_for_vault(first, base)
    settings_b = settings_for_vault(second, base)
    assert settings_a.sqlite_path == base.data_dir / "vaults" / first.id / "escolio.sqlite3"
    assert settings_a.vector_store_dir == base.data_dir / "vaults" / first.id / "vector_store"
    assert settings_a.notes_dir == base.data_dir / "vaults" / first.id / "notes"
    assert settings_a.results_dir == base.results_dir

    origin = tmp_path / "receitas"
    origin.mkdir()
    _add_corpus_root(settings_a, origin)
    connection_b = init_sqlite(settings_b.sqlite_path)
    try:
        assert list_corpus_roots(connection_b) == []
    finally:
        connection_b.close()


def test_vault_create_recusa_icone_e_cor_fora_da_lista(tmp_path: Path) -> None:
    base = _base(tmp_path)
    with pytest.raises(ValueError):
        create_vault("X", "emoji-nao-existe", "violet", [], base)
    with pytest.raises(ValueError):
        create_vault("X", "notes", "neon", [], base)


def test_vault_update_altera_so_os_campos_enviados(tmp_path: Path) -> None:
    base = _base(tmp_path)
    vault = create_vault("Trabalho", "folder", "blue", ["/a"], base)
    updated = update_vault(vault.id, base, name="Trabalho 2", folders=["/b"])
    assert updated.name == "Trabalho 2"
    assert updated.folders == ["/b"]
    assert updated.color == "blue"


def test_vault_delete_recusa_a_unica_vault(tmp_path: Path) -> None:
    base = _base(tmp_path)
    only = load_registry(base).vaults[0]
    with pytest.raises(VaultError, match="unica vault"):
        delete_vault(only.id, base)


def test_vault_delete_apaga_so_pasta_padrao_nunca_a_origem(tmp_path: Path) -> None:
    base = _base(tmp_path)
    load_registry(base)
    origin = tmp_path / "origem"
    origin.mkdir()
    (origin / "nota.md").write_text("# nota", encoding="utf-8")
    vault = create_vault("Culinaria", "layers", "amber", [str(origin)], base)
    init_sqlite(settings_for_vault(vault, base).sqlite_path).close()

    delete_vault(vault.id, base)

    assert not (base.data_dir / "vaults" / vault.id).exists()
    assert (origin / "nota.md").exists()
    assert vault.id not in [v.id for v in load_registry(base).vaults]


def test_vault_delete_vault_migrada_so_remove_do_registro(tmp_path: Path) -> None:
    base = _base(tmp_path)
    migrated = load_registry(base).vaults[0]
    other = create_vault("Outra", "notes", "green", [], base)
    init_sqlite(base.sqlite_path).close()

    delete_vault(migrated.id, base)

    assert base.sqlite_path.exists()
    assert [v.id for v in load_registry(base).vaults] == [other.id]
    assert load_registry(base).active == other.id


def test_vault_delete_da_ativa_ativa_outra(tmp_path: Path) -> None:
    base = _base(tmp_path)
    migrated = load_registry(base).vaults[0]
    active = create_vault("Ativa", "notes", "violet", [], base)
    set_active(active.id, base)

    delete_vault(active.id, base)

    registry = load_registry(base)
    assert registry.active == migrated.id


def test_vault_get_settings_troca_sqlite_sem_mexer_em_results_dir(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("ESCOLIO_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("ESCOLIO_RESULTS_DIR", str(tmp_path / "data" / "results"))
    monkeypatch.delenv("ESCOLIO_SQLITE_PATH", raising=False)
    get_settings.cache_clear()
    try:
        base = get_settings()
        migrated = load_registry(base).vaults[0]
        culinaria = create_vault("Culinaria", "layers", "amber", [], base)
        results_before = get_settings().results_dir

        set_active(culinaria.id, base)
        assert get_settings().sqlite_path == base.data_dir / "vaults" / culinaria.id / "escolio.sqlite3"
        assert get_settings().results_dir == results_before

        set_active(migrated.id, base)
        assert get_settings().sqlite_path == Path(migrated.sqlite_path)
        assert get_settings().results_dir == results_before
    finally:
        get_settings.cache_clear()


def test_vault_get_settings_respeita_sqlite_explicito(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("ESCOLIO_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("ESCOLIO_SQLITE_PATH", str(tmp_path / "fixo.sqlite3"))
    get_settings.cache_clear()
    try:
        base = get_settings()
        create_vault("Outra", "notes", "green", [], base)
        set_active(create_vault("Mais", "notes", "teal", [], base).id, base)
        assert get_settings().sqlite_path == tmp_path / "fixo.sqlite3"
    finally:
        get_settings.cache_clear()


def test_vault_cli_list_e_use(tmp_path: Path, monkeypatch) -> None:
    from escolio.vault_cli import app as vault_app

    monkeypatch.setenv("ESCOLIO_DATA_DIR", str(tmp_path / "data"))
    get_settings.cache_clear()
    try:
        base = Settings()
        create_vault("Culinaria", "layers", "amber", [], base)
        runner = CliRunner()

        listed = runner.invoke(vault_app, ["list"])
        assert listed.exit_code == 0
        assert "* obsidian" in listed.output
        assert "culinaria" in listed.output

        used = runner.invoke(vault_app, ["use", "culinaria"])
        assert used.exit_code == 0
        assert json.loads(registry_path(base).read_text(encoding="utf-8"))["active"] == "culinaria"

        missing = runner.invoke(vault_app, ["use", "nao-existe"])
        assert missing.exit_code == 1
    finally:
        get_settings.cache_clear()


def _load_ui_main_isolated(monkeypatch, root: Path):
    monkeypatch.setitem(
        sys.modules,
        "webview",
        SimpleNamespace(create_window=lambda *a, **k: None, start=lambda *a, **k: None),
    )
    path = Path(__file__).resolve().parents[2] / "UI" / "main.py"
    spec = importlib.util.spec_from_file_location("escolio_ui_main_vault_test", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    # Api() le o registro de vaults; aponta para um diretorio temporario, nunca para data/ real.
    module.base_settings = lambda: _base(root)
    return module


def test_vault_api_select_vault_troca_runtime(tmp_path: Path, monkeypatch) -> None:
    module = _load_ui_main_isolated(monkeypatch, tmp_path)
    base = _base(tmp_path)
    first = load_registry(base).vaults[0]
    second = create_vault("Culinaria", "layers", "amber", [], base)

    api = module.Api()
    old_runtime = api.runtime
    assert api.listVaults()["active"] == first.id

    result = api.selectVault(second.id)

    assert result["ok"] is True
    assert api.runtime is not old_runtime
    assert api.runtime._settings.sqlite_path == settings_for_vault(second, base).sqlite_path
    assert api.listVaults()["active"] == second.id
    assert old_runtime._settings.sqlite_path == settings_for_vault(first, base).sqlite_path


def test_vault_api_delete_exige_confirmacao_pelo_nome(tmp_path: Path, monkeypatch) -> None:
    module = _load_ui_main_isolated(monkeypatch, tmp_path)
    base = _base(tmp_path)
    load_registry(base)
    extra = create_vault("Extra", "notes", "rose", [], base)
    api = module.Api()

    assert api.deleteVault(extra.id, "errado")["ok"] is False
    assert extra.id in [v["id"] for v in api.listVaults()["vaults"]]
    assert api.deleteVault(extra.id, "Extra")["ok"] is True
    assert extra.id not in [v["id"] for v in api.listVaults()["vaults"]]


def test_vault_api_delete_da_ativa_com_banco_aberto_apaga_a_pasta(tmp_path: Path, monkeypatch) -> None:
    # Regressao: no Windows, apagar a vault ativa com o Chroma/SQLite abertos falhava (arquivo em uso).
    module = _load_ui_main_isolated(monkeypatch, tmp_path)
    base = _base(tmp_path)
    load_registry(base)
    extra = create_vault("Extra", "notes", "rose", [], base)
    set_active(extra.id, base)
    api = module.Api()
    api.runtime.get_vector_store()
    init_sqlite(api.runtime._settings.sqlite_path).close()
    folder = settings_for_vault(extra, base).sqlite_path.parent
    assert folder.exists()

    result = api.deleteVault(extra.id, "Extra")

    assert result["ok"] is True, result
    assert not folder.exists()
    assert api.listVaults()["active"] != extra.id
    assert api.runtime._settings.sqlite_path != settings_for_vault(extra, base).sqlite_path
