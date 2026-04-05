from pathlib import Path

from typer.testing import CliRunner

from free_plaud.app.config import Settings
from free_plaud.cli import app

runner = CliRunner()


def test_root_help_works() -> None:
    result = runner.invoke(app, ['--help'])
    assert result.exit_code == 0
    assert 'ingest' in result.stdout
    assert 'benchmark' in result.stdout


def test_doctor_creates_runtime_directories(monkeypatch, tmp_path: Path) -> None:
    settings = Settings(
        workspace_dir=tmp_path,
        data_dir=tmp_path / 'data',
        notes_dir=tmp_path / 'data' / 'corpus' / 'notes',
        datasets_dir=tmp_path / 'data' / 'datasets',
        results_dir=tmp_path / 'data' / 'results',
        sqlite_path=tmp_path / 'data' / 'results' / 'free_plaud.sqlite3',
        vector_store_dir=tmp_path / 'data' / 'results' / 'vector_store',
    )

    monkeypatch.setattr('free_plaud.cli.get_settings', lambda: settings)

    result = runner.invoke(app, ['doctor'])

    assert result.exit_code == 0
    assert settings.data_dir.exists()
    assert settings.notes_dir.exists()
    assert settings.datasets_dir.exists()
    assert settings.results_dir.exists()
    assert settings.vector_store_dir.exists()
