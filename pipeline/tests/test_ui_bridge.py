import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace

from free_plaud.app.doctor_models import DoctorCheck, DoctorReport
from free_plaud.retrieval.models import AskResponse, Citation, UsedSource


def _load_ui_main(monkeypatch):
    monkeypatch.setitem(sys.modules, 'webview', SimpleNamespace(create_window=lambda *a, **k: None, start=lambda *a, **k: None))
    path = Path(__file__).resolve().parents[2] / 'UI' / 'main.py'
    spec = importlib.util.spec_from_file_location('free_plaud_ui_main_test', path)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_desktop_api_send_message_uses_real_corpus_ask(monkeypatch) -> None:
    module = _load_ui_main(monkeypatch)
    citation = Citation(
        note_id='note-ui',
        note_version=1,
        chunk_id='chunk-ui',
        snippet='Trecho usado na resposta.',
        source_path='vault/nota.md',
        char_start=10,
        char_end=37,
    )
    response = AskResponse(
        query='Pergunta?',
        status='answer',
        no_answer=False,
        answer='Resposta gerada pelo corpus.',
        claims=[],
        citations=[citation],
        limitations=[],
        reason_for_no_answer=None,
        used_sources=[UsedSource(doc_id='note-ui', note_version=1, source_path='vault/nota.md', chunk_ids=['chunk-ui'])],
        latency_ms=42,
    )
    monkeypatch.setattr(module, 'ask_corpus', lambda question, strategy, runtime: response)

    text = module.Api().sendMessage('Pergunta?')

    assert 'Resposta gerada pelo corpus.' in text
    assert 'Fontes:' in text
    assert 'vault/nota.md' in text
    assert 'latencia_ms: 42' in text


def test_desktop_api_send_message_abstains_without_answer(monkeypatch) -> None:
    module = _load_ui_main(monkeypatch)
    response = AskResponse(
        query='Pergunta?',
        status='no_answer',
        no_answer=True,
        answer=None,
        claims=[],
        citations=[],
        limitations=['Sem evidência suficiente.'],
        reason_for_no_answer='no_retrieval_hits',
        used_sources=[],
        latency_ms=7,
    )
    monkeypatch.setattr(module, 'ask_corpus', lambda question, strategy, runtime: response)

    text = module.Api().sendMessage('Pergunta?')

    assert 'Não encontrei resposta no corpus indexado.' in text
    assert 'no_retrieval_hits' in text
    assert 'Sem evidência suficiente.' in text


def test_desktop_api_index_vault_returns_batch_summary(monkeypatch, tmp_path: Path) -> None:
    module = _load_ui_main(monkeypatch)
    calls: list[Path] = []

    def fake_index_corpus_folder(path: Path, *, runtime):  # noqa: ANN001
        calls.append(path)
        return SimpleNamespace(
            status='success',
            total_found=3,
            indexed_count=2,
            unchanged_count=1,
            failed_count=0,
            skipped_count=0,
        )

    monkeypatch.setattr(module, 'index_corpus_folder', fake_index_corpus_folder)

    result = module.Api().indexVault(str(tmp_path))

    assert calls == [tmp_path]
    assert result == {
        'ok': True,
        'status': 'success',
        'total_found': 3,
        'indexed_count': 2,
        'unchanged_count': 1,
        'failed_count': 0,
        'skipped_count': 0,
    }


def test_desktop_api_exposes_settings_catalog(monkeypatch) -> None:
    module = _load_ui_main(monkeypatch)

    result = module.Api().getBackendSettings()

    keys = {row['key'] for row in result['settings_catalog']}
    assert {'retrieval_top_k', 'default_chunk_size', 'default_chunk_overlap', 'answer_api_key'} <= keys


def test_desktop_api_exposes_doctor_report(monkeypatch) -> None:
    module = _load_ui_main(monkeypatch)
    monkeypatch.setattr(
        module,
        'run_doctor',
        lambda: DoctorReport(
            status='warning',
            checks=[DoctorCheck(code='corpus', status='warning', message='Corpus vazio.', latency_ms=2)],
            latency_ms=2,
            ok_count=0,
            warning_count=1,
            error_count=0,
        ),
    )

    result = module.Api().getDoctor()

    assert result['status'] == 'warning'
    assert result['checks'][0]['code'] == 'corpus'
    assert result['checks'][0]['message'] == 'Corpus vazio.'


def test_desktop_api_saves_backend_setting(monkeypatch, tmp_path: Path) -> None:
    module = _load_ui_main(monkeypatch)
    calls: list[tuple[str, object]] = []

    def fake_save_catalog_setting(key: str, value: object):  # noqa: ANN001
        calls.append((key, value))

    monkeypatch.setattr(module, 'save_catalog_setting', fake_save_catalog_setting)

    result = module.Api().saveBackendSetting('retrieval_top_k', '9')

    assert result == {'ok': True}
    assert calls == [('retrieval_top_k', '9')]
