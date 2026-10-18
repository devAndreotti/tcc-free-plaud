import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace

from escolio.app.doctor_models import DoctorCheck, DoctorReport
from escolio.providers.answer import AnswerProviderTestResult
from escolio.providers.model_discovery import ModelDiscoveryResult, ModelInfo
from escolio.retrieval.models import AnswerClaim, AskResponse, Citation, UsedSource


def _load_ui_main(monkeypatch):
    monkeypatch.setitem(
        sys.modules,
        "webview",
        SimpleNamespace(create_window=lambda *a, **k: None, start=lambda *a, **k: None),
    )
    path = Path(__file__).resolve().parents[2] / "UI" / "main.py"
    spec = importlib.util.spec_from_file_location("escolio_ui_main_test", path)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_desktop_api_send_message_uses_real_corpus_ask(monkeypatch) -> None:
    module = _load_ui_main(monkeypatch)
    citation = Citation(
        note_id="note-ui",
        note_version=1,
        chunk_id="chunk-ui",
        snippet="Trecho usado na resposta.",
        source_path="vault/nota.md",
        char_start=10,
        char_end=37,
    )
    response = AskResponse(
        query="Pergunta?",
        status="answer",
        no_answer=False,
        answer="Resposta gerada pelo corpus.",
        claims=[],
        citations=[citation],
        limitations=[],
        reason_for_no_answer=None,
        used_sources=[
            UsedSource(
                doc_id="note-ui",
                note_version=1,
                source_path="vault/nota.md",
                chunk_ids=["chunk-ui"],
            )
        ],
        latency_ms=42,
    )
    monkeypatch.setattr(
        module, "ask_corpus", lambda question, strategy, runtime: response
    )

    text = module.Api().sendMessage("Pergunta?")

    assert "Resposta gerada pelo corpus." in text
    assert "Fontes:" in text
    assert "vault/nota.md" in text
    assert "latencia_ms: 42" in text


def test_desktop_api_ask_corpus_returns_structured_response(monkeypatch) -> None:
    module = _load_ui_main(monkeypatch)
    citation = Citation(
        note_id="note-ui",
        note_version=1,
        chunk_id="chunk-ui",
        snippet="Trecho usado na resposta.",
        source_path="vault/nota.md",
        char_start=10,
        char_end=37,
    )
    response = AskResponse(
        query="Pergunta?",
        status="answer",
        no_answer=False,
        answer="Resposta gerada pelo corpus.",
        claims=[AnswerClaim(text="Resposta gerada pelo corpus.", citations=[citation], support_level="partial")],
        citations=[citation],
        limitations=["Só uma fonte."],
        latency_ms=42,
    )
    calls = []
    roots = []

    def fake_ask(question, strategy, runtime, source_root=None):
        calls.append(strategy)
        roots.append(source_root)
        return response

    monkeypatch.setattr(module, "ask_corpus", fake_ask)
    api = module.Api()

    payload = api.askCorpus("Pergunta?", "lexical")
    api.askCorpus("Pergunta?", "nao-existe")
    api.askCorpus("Pergunta?", "lexical", "D:\\Notas\\Culinaria")

    assert calls[0] == "lexical"
    assert calls[1] == module.get_settings().default_ask_strategy
    assert roots == [None, None, "D:\\Notas\\Culinaria"]
    assert payload["strategy"] == "lexical"
    assert payload["claims"][0]["support_level"] == "partial"
    assert payload["citations"][0]["char_start"] == 10
    assert payload["limitations"] == ["Só uma fonte."]
    assert payload["latency_ms"] == 42
    assert "debug" not in payload


def test_desktop_api_send_message_abstains_without_answer(monkeypatch) -> None:
    module = _load_ui_main(monkeypatch)
    response = AskResponse(
        query="Pergunta?",
        status="no_answer",
        no_answer=True,
        answer=None,
        claims=[],
        citations=[],
        limitations=["Sem evidência suficiente."],
        reason_for_no_answer="no_retrieval_hits",
        used_sources=[],
        latency_ms=7,
    )
    monkeypatch.setattr(
        module, "ask_corpus", lambda question, strategy, runtime: response
    )

    text = module.Api().sendMessage("Pergunta?")

    assert "Não encontrei resposta no corpus indexado." in text
    assert "no_retrieval_hits" in text
    assert "Sem evidência suficiente." in text


def test_desktop_api_index_vault_returns_batch_summary(
    monkeypatch, tmp_path: Path
) -> None:
    module = _load_ui_main(monkeypatch)
    calls: list[Path] = []

    def fake_index_corpus_folder(path: Path, *, runtime):
        calls.append(path)
        return SimpleNamespace(
            status="success",
            total_found=3,
            indexed_count=2,
            unchanged_count=1,
            failed_count=0,
            skipped_count=0,
        )

    monkeypatch.setattr(module, "index_corpus_folder", fake_index_corpus_folder)

    result = module.Api().indexVault(str(tmp_path))

    assert calls == [tmp_path]
    assert result == {
        "ok": True,
        "status": "success",
        "total_found": 3,
        "indexed_count": 2,
        "unchanged_count": 1,
        "failed_count": 0,
        "skipped_count": 0,
    }


def test_desktop_api_exposes_index_queue_methods(monkeypatch, tmp_path: Path) -> None:
    module = _load_ui_main(monkeypatch)
    started: list[tuple[str, bool]] = []
    cancelled: list[str] = []

    class FakeSnapshot:
        def __init__(self, job_id: str, status: str = "running") -> None:
            self.job_id = job_id
            self.status = status

        def model_dump(self, mode="json"):
            return {
                "job_id": self.job_id,
                "status": self.status,
                "source_path": str(tmp_path),
                "started_at": "2026-05-26T10:00:00+00:00",
                "finished_at": None,
                "progress": None,
                "result": None,
                "error_code": None,
                "message": None,
                "last_errors": [],
                "cancel_requested": False,
                "files_per_second": 0.0,
                "chunks_per_second": 0.0,
                "eta_seconds": None,
            }

    def fake_start_index_job(folder_path, *, rebuild, runtime):
        started.append((str(folder_path), rebuild))
        return FakeSnapshot("job-ui")

    def fake_get_index_job(job_id):
        return FakeSnapshot(job_id, status="running")

    def fake_cancel_index_job(job_id):
        cancelled.append(job_id)
        return FakeSnapshot(job_id, status="cancelled")

    monkeypatch.setattr(module, "start_index_job", fake_start_index_job)
    monkeypatch.setattr(module, "get_index_job", fake_get_index_job)
    monkeypatch.setattr(module, "cancel_index_job", fake_cancel_index_job)

    api = module.Api()

    assert api.startIndexJob(str(tmp_path))["job_id"] == "job-ui"
    assert started == [(str(tmp_path), False)]
    assert api.getIndexJob("job-ui")["status"] == "running"
    assert api.cancelIndexJob("job-ui")["status"] == "cancelled"
    assert cancelled == ["job-ui"]


def test_desktop_api_exposes_watcher_methods(monkeypatch, tmp_path: Path) -> None:
    module = _load_ui_main(monkeypatch)
    calls: list[str] = []

    def fake_start(folder_path, indexer):
        calls.append(f"start:{folder_path}")
        assert indexer is api.dropped_files
        return {"ok": True, "active": True, "directory": str(folder_path)}

    def fake_stop():
        calls.append("stop")
        return {"ok": True, "active": False, "directory": None}

    def fake_status():
        return {"active": True, "directory": str(tmp_path)}

    monkeypatch.setattr(module.watcher_manager, "start", fake_start)
    monkeypatch.setattr(module.watcher_manager, "stop", fake_stop)
    monkeypatch.setattr(module.watcher_manager, "status", fake_status)

    api = module.Api()

    assert api.startWatcher(str(tmp_path))["active"] is True
    assert api.getWatcherStatus()["directory"] == str(tmp_path)
    assert api.stopWatcher()["active"] is False
    assert calls == [f"start:{tmp_path}", "stop"]


def test_desktop_api_exposes_settings_catalog(monkeypatch) -> None:
    module = _load_ui_main(monkeypatch)

    result = module.Api().getBackendSettings()

    keys = {row["key"] for row in result["settings_catalog"]}
    assert {
        "retrieval_top_k",
        "default_chunk_size",
        "default_chunk_overlap",
        "answer_api_key",
    } <= keys


def test_desktop_api_exposes_doctor_report(monkeypatch) -> None:
    module = _load_ui_main(monkeypatch)
    monkeypatch.setattr(
        module,
        "run_doctor",
        lambda: DoctorReport(
            status="warning",
            checks=[
                DoctorCheck(
                    code="corpus",
                    status="warning",
                    message="Corpus vazio.",
                    latency_ms=2,
                )
            ],
            latency_ms=2,
            ok_count=0,
            warning_count=1,
            error_count=0,
        ),
    )

    result = module.Api().getDoctor()

    assert result["status"] == "warning"
    assert result["checks"][0]["code"] == "corpus"
    assert result["checks"][0]["message"] == "Corpus vazio."


def test_desktop_api_exposes_settings_presets(monkeypatch) -> None:
    module = _load_ui_main(monkeypatch)

    result = module.Api().listSettingsPresets()

    keys = {preset["key"] for preset in result}
    assert {"cpu_rapido", "gpu_qualidade", "vault_grande", "tcc_reprodutivel"} <= keys
    assert all("answer_api_key" not in preset["values"] for preset in result)


def test_desktop_api_applies_settings_preset_and_clears_runtime(monkeypatch) -> None:
    module = _load_ui_main(monkeypatch)
    calls: list[str] = []

    class FakeResult:
        preset = SimpleNamespace(
            key="cpu_rapido",
            model_dump=lambda mode="json": {
                "key": "cpu_rapido",
                "label": "CPU rapido",
                "description": "Teste",
                "values": {
                    "embedding_model": "chroma-default",
                    "embedding_device": "cpu",
                },
            },
        )
        settings = SimpleNamespace(
            embedding_model="chroma-default", embedding_device="cpu"
        )
        values = {"embedding_model": "chroma-default", "embedding_device": "cpu"}
        changes = {}

    def fake_apply_settings_preset(name: str):
        calls.append(name)
        return FakeResult()

    monkeypatch.setattr(module, "apply_settings_preset", fake_apply_settings_preset)
    api = module.Api()
    cleared = False

    def clear_runtime() -> None:
        nonlocal cleared
        cleared = True

    api.runtime.clear = clear_runtime

    result = api.applySettingsPreset("cpu_rapido")

    assert calls == ["cpu_rapido"]
    assert cleared is True
    assert result["ok"] is True
    assert result["preset"]["key"] == "cpu_rapido"
    assert result["values"]["embedding_model"] == "chroma-default"


def test_desktop_api_tests_answer_provider(monkeypatch) -> None:
    module = _load_ui_main(monkeypatch)
    monkeypatch.setattr(
        module,
        "test_answer_provider",
        lambda: AnswerProviderTestResult(
            provider="ollama",
            model="llama3.1:8b",
            base_url="http://localhost:11434/v1",
            status="ok",
            latency_ms=7,
            error=None,
        ),
    )

    result = module.Api().testAnswerProvider()

    assert result["status"] == "ok"
    assert result["provider"] == "ollama"
    assert result["latency_ms"] == 7


def test_desktop_api_lists_answer_models(monkeypatch) -> None:
    module = _load_ui_main(monkeypatch)
    monkeypatch.setattr(
        module,
        "list_answer_models",
        lambda: ModelDiscoveryResult(
            provider="ollama",
            base_url="http://localhost:11434",
            status="ok",
            models=[
                ModelInfo(id="llama3.1:8b", label="llama3.1:8b", provider="ollama")
            ],
            latency_ms=9,
        ),
    )

    result = module.Api().listAnswerModels()

    assert result["status"] == "ok"
    assert result["provider"] == "ollama"
    assert result["models"][0]["id"] == "llama3.1:8b"
    assert "api_key" not in result


def test_desktop_api_saves_backend_setting(monkeypatch, tmp_path: Path) -> None:
    module = _load_ui_main(monkeypatch)
    calls: list[tuple[str, object]] = []

    def fake_save_catalog_setting(key: str, value: object):
        calls.append((key, value))

    monkeypatch.setattr(module, "save_catalog_setting", fake_save_catalog_setting)

    result = module.Api().saveBackendSetting("retrieval_top_k", "9")

    assert result == {"ok": True}
    assert calls == [("retrieval_top_k", "9")]


def test_desktop_api_exposes_notes_methods(monkeypatch) -> None:
    module = _load_ui_main(monkeypatch)

    monkeypatch.setattr(
        module,
        "list_notes",
        lambda settings=None: [
            SimpleNamespace(
                model_dump=lambda mode="json": {
                    "note_id": "nota-1",
                    "title": "Nota 1",
                    "source_type": "md",
                    "source_path": "vault/nota-1.md",
                    "created_at": "2026-05-25T10:00:00+00:00",
                    "tags": ["md"],
                    "chunk_count": 2,
                }
            )
        ],
    )
    monkeypatch.setattr(
        module,
        "get_note_detail",
        lambda note_id, settings=None: SimpleNamespace(
            model_dump=lambda mode="json": {
                "note_id": note_id,
                "title": "Nota 1",
                "source_type": "md",
                "source_path": "vault/nota-1.md",
                "created_at": "2026-05-25T10:00:00+00:00",
                "tags": ["md"],
                "chunk_count": 2,
                "structured_markdown": "# Nota 1",
                "chunks": [],
            }
        ),
    )
    monkeypatch.setattr(
        module,
        "delete_note",
        lambda note_id, settings=None, vector_store=None: SimpleNamespace(
            model_dump=lambda mode="json": {
                "ok": True,
                "note_id": note_id,
                "deleted_vectors": 2,
            }
        ),
    )
    monkeypatch.setattr(
        module,
        "reindex_note",
        lambda note_id, runtime=None: SimpleNamespace(
            model_dump=lambda mode="json": {
                "ok": True,
                "note_id": note_id,
                "status": "success",
                "chunks_indexed": 2,
            }
        ),
    )

    api = module.Api()

    assert api.listNotes()[0]["note_id"] == "nota-1"
    assert api.getNoteDetail("nota-1")["structured_markdown"] == "# Nota 1"
    assert api.deleteNote("nota-1", "APAGAR")["ok"] is True
    assert api.deleteNote("nota-1", "")["status"] == "confirmation_required"
    assert api.reindexNote("nota-1")["chunks_indexed"] == 2


def test_desktop_api_runs_benchmark_compare(monkeypatch) -> None:
    module = _load_ui_main(monkeypatch)
    calls: list[str] = []

    monkeypatch.setattr(
        module,
        "run_benchmark_compare",
        lambda suite_path, runtime=None: (
            calls.append(str(suite_path))
            or {
                "ok": True,
                "comparison_id": "cmp-ui",
                "suite_name": "suite-ui",
                "summaries": {
                    "hybrid": {
                        "mrr": 1.0,
                        "recall_at_3": 1.0,
                        "avg_query_latency_ms": 4.0,
                    }
                },
                "json_report_path": "data/results/cmp-ui.json",
                "csv_report_path": "data/results/cmp-ui.csv",
                "settings_snapshot": {
                    "embedding_model": "fake-hash",
                    "embedding_device": "cpu",
                },
            }
        ),
    )

    result = module.Api().runBenchmarkCompare("suite.json")

    assert calls == ["suite.json"]
    assert result["ok"] is True
    assert result["comparison_id"] == "cmp-ui"
    assert result["json_report_path"].endswith("cmp-ui.json")
    assert result["settings_snapshot"]["embedding_device"] == "cpu"


def test_desktop_api_indexes_dropped_files(monkeypatch, tmp_path: Path) -> None:
    module = _load_ui_main(monkeypatch)
    api = module.Api()
    indexed: list[str] = []

    def runner(path: Path):
        from escolio.corpus.models import CorpusIndexBatchResult, CorpusIndexResult

        indexed.append(path.name)
        return CorpusIndexBatchResult(
            source_path=str(path),
            recursive=False,
            status="success",
            total_found=1,
            indexed_count=1,
            failed_count=0,
            skipped_count=0,
            results=[CorpusIndexResult(source_path=str(path), status="success", chunks_indexed=2)],
        )

    api.dropped_files = module.DroppedFileIndexer(runner=runner)
    api._stage_dropped_files(
        {"dataTransfer": {"files": [{"name": "nota.md", "pywebviewFullPath": str(tmp_path / "nota.md")}, {"name": "sem-caminho.md"}]}}
    )

    assert api.indexDroppedFiles(["nota.md", "sem-caminho.md"]) == {"queued": ["nota.md"], "missing": ["sem-caminho.md"]}
    api.dropped_files.join()
    events = api.pollDroppedFiles()
    assert indexed == ["nota.md"]
    assert events[0]["status"] == "indexed" and events[0]["chunks"] == 2


def test_desktop_api_removes_corpus_root_only_with_confirmation_regressao(monkeypatch) -> None:
    module = _load_ui_main(monkeypatch)
    calls: list[str] = []

    def fake_remove(root, *, runtime=None):
        calls.append(root)
        return 3

    monkeypatch.setattr(module, "remove_corpus_root_from_tui", fake_remove)
    api = module.Api()

    assert api.removeCorpusRoot("D:/Notas/Culinaria", "")["status"] == "confirmation_required"
    assert api.removeCorpusRoot("D:/Notas/Culinaria", "APAGAR")["status"] == "confirmation_required"
    assert calls == []
    assert api.removeCorpusRoot("D:/Notas/Culinaria", "REMOVER") == {"ok": True, "removed_notes": 3}
    assert calls == ["D:/Notas/Culinaria"]
