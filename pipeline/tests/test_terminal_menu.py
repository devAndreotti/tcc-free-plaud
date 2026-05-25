import json
from pathlib import Path

from typer.testing import CliRunner

from free_plaud.app.config import get_settings
from free_plaud.app.doctor_models import DoctorCheck, DoctorReport
from free_plaud.cli import app
from free_plaud.providers.answer import AnswerProviderTestResult

runner = CliRunner()


def test_terminal_menu_can_open_and_exit() -> None:
    result = runner.invoke(app, ['menu'], input='0\n')

    assert result.exit_code == 0
    assert 'free-plaud terminal' in result.stdout
    assert 'ACOES:\n\n' in result.stdout
    assert '[8] Diagnostico' in result.stdout
    assert '[9] Testar provider' in result.stdout
    assert '[0] Sair\n\n' in result.stdout
    assert 'Sair' in result.stdout


def test_terminal_menu_can_update_embedding_device(monkeypatch, tmp_path: Path) -> None:
    results_dir = tmp_path / 'data' / 'results'
    monkeypatch.setenv('FREE_PLAUD_RESULTS_DIR', str(results_dir))
    get_settings.cache_clear()

    result = runner.invoke(app, ['menu'], input='7\n2\ncuda\n0\n')

    assert result.exit_code == 0
    payload = json.loads((results_dir / 'user_settings.json').read_text(encoding='utf-8'))
    assert payload['embedding_device'] == 'cuda'
    get_settings.cache_clear()


def test_terminal_settings_menu_uses_human_catalog(monkeypatch, tmp_path: Path) -> None:
    results_dir = tmp_path / 'data' / 'results'
    monkeypatch.setenv('FREE_PLAUD_RESULTS_DIR', str(results_dir))
    get_settings.cache_clear()

    result = runner.invoke(app, ['menu'], input='7\n0\n0\n')

    assert result.exit_code == 0
    assert 'Simples' in result.stdout
    assert 'Avancado' in result.stdout
    assert 'Provedor de resposta' in result.stdout
    assert 'Modelo de resposta' in result.stdout
    assert 'Chunks por pergunta' in result.stdout
    assert 'Tamanho do chunk' in result.stdout
    assert 'Sobreposição' in result.stdout
    assert 'answer_api_key' in result.stdout
    get_settings.cache_clear()


def test_terminal_settings_menu_can_apply_preset(monkeypatch, tmp_path: Path) -> None:
    results_dir = tmp_path / 'data' / 'results'
    monkeypatch.setenv('FREE_PLAUD_WORKSPACE_DIR', str(tmp_path))
    monkeypatch.setenv('FREE_PLAUD_RESULTS_DIR', str(results_dir))
    get_settings.cache_clear()

    result = runner.invoke(app, ['menu'], input='7\nP\ncpu_rapido\napply\n0\n')

    assert result.exit_code == 0
    assert 'Presets' in result.stdout
    payload = json.loads((results_dir / 'user_settings.json').read_text(encoding='utf-8'))
    assert payload['embedding_model'] == 'chroma-default'
    assert payload['embedding_device'] == 'cpu'
    get_settings.cache_clear()


def test_terminal_menu_can_update_answer_api_key(monkeypatch, tmp_path: Path) -> None:
    results_dir = tmp_path / 'data' / 'results'
    monkeypatch.setenv('FREE_PLAUD_WORKSPACE_DIR', str(tmp_path))
    monkeypatch.setenv('FREE_PLAUD_RESULTS_DIR', str(results_dir))
    monkeypatch.delenv('FREE_PLAUD_ANSWER_API_KEY', raising=False)
    get_settings.cache_clear()

    result = runner.invoke(app, ['menu'], input='7\n17\nsk-menu-test\n0\n')

    assert result.exit_code == 0
    local_env = tmp_path / 'pipeline' / '.env'
    assert 'FREE_PLAUD_ANSWER_API_KEY=sk-menu-test' in local_env.read_text(encoding='utf-8')
    assert not (results_dir / 'user_settings.json').exists()
    get_settings.cache_clear()


def test_terminal_menu_can_show_doctor(monkeypatch) -> None:
    monkeypatch.setattr(
        'free_plaud.terminal_menu.run_doctor',
        lambda: DoctorReport(
            status='ok',
            checks=[DoctorCheck(code='corpus', status='ok', message='Corpus consistente.', latency_ms=1)],
            latency_ms=1,
            ok_count=1,
            warning_count=0,
            error_count=0,
        ),
    )

    result = runner.invoke(app, ['menu'], input='8\n\n0\n')

    assert result.exit_code == 0
    assert 'Diagnostico' in result.stdout
    assert 'corpus' in result.stdout
    assert 'Corpus consistente.' in result.stdout


def test_terminal_menu_can_test_provider(monkeypatch) -> None:
    monkeypatch.setattr(
        'free_plaud.terminal_menu.test_answer_provider',
        lambda: AnswerProviderTestResult(
            provider='ollama',
            model='llama3.1:8b',
            base_url='http://localhost:11434/v1',
            status='ok',
            latency_ms=7,
            error=None,
        ),
    )

    result = runner.invoke(app, ['menu'], input='9\n\n0\n')

    assert result.exit_code == 0
    assert 'Testar provider' in result.stdout
    assert 'ollama' in result.stdout
    assert 'ok' in result.stdout
