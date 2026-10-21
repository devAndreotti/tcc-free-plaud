import importlib.util
import json
import sys
import tempfile
import threading
import time
from pathlib import Path
from types import SimpleNamespace

from escolio.app.config import Settings, user_settings_path_for
from escolio.app.doctor_models import DoctorCheck, DoctorReport
from escolio.providers.answer import AnswerProviderTestResult
from escolio.providers.model_discovery import ModelDiscoveryResult, ModelInfo
from escolio.retrieval.models import AnswerClaim, AskResponse, Citation, UsedSource
from escolio.storage.sqlite import init_sqlite


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
    # Api() le o registro de vaults: isola em diretorio temporario, nunca no data/ real.
    isolated = Path(tempfile.mkdtemp(prefix="escolio-ui-bridge-"))
    module.base_settings = lambda: Settings(
        data_dir=isolated / "data",
        results_dir=isolated / "data" / "results",
        sqlite_path=isolated / "data" / "results" / "escolio.sqlite3",
        vector_store_dir=isolated / "data" / "results" / "vector_store",
        notes_dir=isolated / "notes",
    )
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
    # getBackendSettings roda o doctor, que consultaria o provider configurado no user_settings real.
    monkeypatch.setattr(
        "escolio.app.doctor.list_answer_models",
        lambda settings, **_: SimpleNamespace(status="not_applicable", models=[], message=None),
    )

    result = module.Api().getBackendSettings()

    keys = {row["key"] for row in result["settings_catalog"]}
    assert {
        "retrieval_top_k",
        "default_chunk_size",
        "default_chunk_overlap",
        "answer_api_key",
    } <= keys


def test_desktop_api_get_backend_settings_sem_doctor_nao_roda_o_doctor(monkeypatch, tmp_path: Path) -> None:
    module = _load_ui_main(monkeypatch)
    api = module.Api()
    monkeypatch.setattr(module, "get_settings", lambda: _settings_do_provider(tmp_path, "extractive"))
    chamadas: list[str] = []
    monkeypatch.setattr(module, "run_doctor", lambda **_: chamadas.append("doctor"))

    result = api.getBackendSettings(doctor=False)

    assert chamadas == []
    assert result["doctor"] is None


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

    def fake_apply_settings_preset(name: str, **kwargs):
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


def test_desktop_api_aplicar_preset_nao_grava_embedding_model(monkeypatch, tmp_path: Path) -> None:
    module = _load_ui_main(monkeypatch)
    settings = _settings_do_provider(tmp_path, "extractive")
    aplicar = module.apply_settings_preset
    monkeypatch.setattr(
        module, "apply_settings_preset", lambda name, **kwargs: aplicar(name, settings=settings, **kwargs)
    )

    result = module.Api().applySettingsPreset("cpu_rapido")

    payload = json.loads(user_settings_path_for(settings).read_text(encoding="utf-8"))
    assert "embedding_model" not in payload
    assert "embedding_model" not in result["values"]
    assert payload["retrieval_top_k"] == 4


def test_desktop_api_tests_answer_provider(monkeypatch) -> None:
    module = _load_ui_main(monkeypatch)
    monkeypatch.setattr(
        module,
        "test_answer_provider",
        lambda settings: AnswerProviderTestResult(
            provider=settings.answer_provider,
            model=settings.answer_model,
            base_url="http://localhost:11434/v1",
            status="ok",
            latency_ms=7,
            error=None,
        ),
    )

    result = module.Api().testAnswerProvider()

    assert result["status"] == "ok"
    assert result["latency_ms"] == 7


def test_desktop_api_lists_answer_models(monkeypatch) -> None:
    module = _load_ui_main(monkeypatch)
    monkeypatch.setattr(
        module,
        "list_answer_models",
        lambda settings: ModelDiscoveryResult(
            provider="ollama",
            base_url="http://localhost:11434",
            status="ok",
            models=[
                ModelInfo(id="qchat:latest", label="qchat:latest", provider="ollama")
            ],
            latency_ms=9,
        ),
    )

    result = module.Api().listAnswerModels()

    assert result["status"] == "ok"
    assert result["provider"] == "ollama"
    assert result["models"][0]["id"] == "qchat:latest"
    assert "api_key" not in result


def test_desktop_api_testar_e_listar_usam_o_que_esta_na_tela_sem_salvar(monkeypatch, tmp_path: Path) -> None:
    module = _load_ui_main(monkeypatch)
    api = module.Api()
    monkeypatch.setattr(module, "get_settings", lambda: Settings(results_dir=tmp_path))  # salvo: extractive
    seen: list[Settings] = []

    def capture(settings: Settings):
        seen.append(settings)
        return SimpleNamespace(model_dump=lambda mode: {})

    monkeypatch.setattr(module, "test_answer_provider", capture)
    monkeypatch.setattr(module, "list_answer_models", capture)

    api.testAnswerProvider("ollama", " qchat:latest ", "")
    api.listAnswerModels("lmstudio", "http://127.0.0.1:1234/v1")
    api.testAnswerProvider("nao-existe", None, None)

    assert (seen[0].answer_provider, seen[0].answer_model, seen[0].answer_base_url) == ("ollama", "qchat:latest", None)
    assert (seen[1].answer_provider, seen[1].answer_base_url) == ("lmstudio", "http://127.0.0.1:1234/v1")
    assert seen[2].answer_provider == "extractive"  # provedor desconhecido não passa


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


def test_desktop_api_lists_note_links_from_active_vault(monkeypatch, tmp_path: Path) -> None:
    module = _load_ui_main(monkeypatch)
    api = module.Api()  # o construtor limpa o cache de get_settings: patcha depois
    db_path = tmp_path / "escolio.sqlite3"
    monkeypatch.setattr(module, "get_settings", lambda: Settings(results_dir=tmp_path, sqlite_path=db_path))
    connection = init_sqlite(db_path)
    connection.executemany(
        "INSERT INTO notes (note_id, note_version, source_type, source_path, source_name, title, summary, "
        "raw_text, normalized_text, structured_markdown, content_hash, provider, model, created_at) "
        "VALUES (?, 1, 'md', ?, ?, ?, '', ?, '', '', '', '', '', '2026-10-18T12:00:00')",
        [
            ("switch", "V/Redes/Switch.md", "Switch.md", "Switch", ""),
            ("ospf", "V/Redes/OSPF.md", "OSPF.md", "OSPF", "- [[switch|o switch]]"),
        ],
    )
    connection.commit()
    connection.close()

    assert api.listNoteLinks() == [{"source": "ospf", "target": "switch"}]


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


def test_regressao_scan_vault_usa_caminho_como_id_e_ignora_pastas_ocultas(monkeypatch, tmp_path: Path) -> None:
    module = _load_ui_main(monkeypatch)
    (tmp_path / "Pessoas").mkdir()
    (tmp_path / "Pessoas" / "ana.md").write_text("# Ana\n", encoding="utf-8")
    (tmp_path / "raiz.md").write_text("# Raiz\n", encoding="utf-8")
    for hidden in (".obsidian", ".trash"):
        (tmp_path / hidden).mkdir()
        (tmp_path / hidden / "lixo.md").write_text("# Lixo\n", encoding="utf-8")

    first = module.Api().scanVault(str(tmp_path))
    second = module.Api().scanVault(str(tmp_path))

    assert sorted(node["path"] for node in first) == ["Pessoas/ana.md", "raiz.md"]
    assert all(node["id"] == node["path"] for node in first)  # grafo não se redesenha a cada rescan
    assert sorted(node["id"] for node in second) == sorted(node["id"] for node in first)


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


def test_desktop_api_save_conversations_devolve_erro_de_validacao(monkeypatch) -> None:
    module = _load_ui_main(monkeypatch)

    def fake_save(payload: dict) -> None:
        if "tabs" not in payload:
            raise ValueError('Conversas: "tabs" precisa ser uma lista.')

    monkeypatch.setattr(module, "save_conversations", fake_save)
    api = module.Api()

    assert api.saveConversations({}) == {"ok": False, "message": 'Conversas: "tabs" precisa ser uma lista.'}
    assert api.saveConversations({"tabs": []}) == {"ok": True}


def _ask_response(answer: str) -> AskResponse:
    return AskResponse(
        query="Pergunta?",
        status="answer",
        no_answer=False,
        answer=answer,
        claims=[],
        citations=[],
        limitations=[],
        reason_for_no_answer=None,
        used_sources=[],
        latency_ms=7,
    )


def _consulta_ate_fim(api, ask_id: str, pronto=lambda snapshot: False) -> dict:
    """Consulta o job até terminar (ou até `pronto` valer). done/error já saem do registro."""
    fim = time.monotonic() + 5.0
    while True:
        snapshot = api.pollAsk(ask_id)
        if snapshot["stage"] in ("done", "error") or pronto(snapshot) or time.monotonic() > fim:
            return snapshot
        time.sleep(0.01)


def _espera(pronto, limite: float = 5.0) -> None:
    fim = time.monotonic() + limite
    while not pronto() and time.monotonic() < fim:
        time.sleep(0.01)


def _settings_do_provider(tmp_path: Path, provider: str) -> Settings:
    return Settings(
        workspace_dir=tmp_path,
        data_dir=tmp_path / "data",
        notes_dir=tmp_path / "data" / "corpus" / "notes",
        results_dir=tmp_path / "data" / "results",
        sqlite_path=tmp_path / "data" / "results" / "escolio.sqlite3",
        vector_store_dir=tmp_path / "data" / "results" / "vector_store",
        answer_provider=provider,
    )


def test_desktop_api_start_ask_mostra_etapas_e_texto_parcial_ate_done(monkeypatch) -> None:
    module = _load_ui_main(monkeypatch)
    liberar_busca = threading.Event()
    liberar_escrita = threading.Event()

    def fake_ask(question, strategy, runtime, source_root=None, on_answer_delta=None):
        liberar_busca.wait(5)
        on_answer_delta("Resposta ")
        liberar_escrita.wait(5)
        on_answer_delta("curta.")
        return _ask_response("Resposta curta.")

    monkeypatch.setattr(module, "ask_corpus", fake_ask)
    api = module.Api()

    ask_id = api.startAsk("Pergunta?", "lexical")["ask_id"]
    assert api.pollAsk(ask_id)["stage"] == "retrieving"

    liberar_busca.set()
    parcial = _consulta_ate_fim(api, ask_id, pronto=lambda s: s["partial"] == "Resposta ")
    assert parcial["stage"] == "writing"

    liberar_escrita.set()
    final = _consulta_ate_fim(api, ask_id)
    assert final["stage"] == "done"
    assert final["partial"] == "Resposta curta."
    assert final["error"] is None
    assert final["result"]["answer"] == "Resposta curta."
    assert final["result"]["strategy"] == "lexical"
    assert final["result"]["answer_model"] == module.get_settings().answer_model
    assert api.pollAsk(ask_id)["error"] == "Pergunta não encontrada."


def test_desktop_api_start_ask_sem_streaming_vai_direto_para_done(monkeypatch) -> None:
    module = _load_ui_main(monkeypatch)
    monkeypatch.setattr(
        module,
        "ask_corpus",
        lambda question, strategy, runtime, source_root=None, on_answer_delta=None: _ask_response("Trecho direto."),
    )
    api = module.Api()

    final = _consulta_ate_fim(api, api.startAsk("Pergunta?", "lexical")["ask_id"])

    assert final["stage"] == "done"
    assert final["partial"] == ""
    assert final["result"]["answer"] == "Trecho direto."


def test_desktop_api_poll_ask_id_desconhecido_devolve_erro(monkeypatch) -> None:
    module = _load_ui_main(monkeypatch)

    assert module.Api().pollAsk("nao-existe") == {
        "ask_id": "nao-existe",
        "stage": "error",
        "partial": "",
        "result": None,
        "error": "Pergunta não encontrada.",
    }


def test_desktop_api_cancel_ask_descarta_a_pergunta(monkeypatch) -> None:
    module = _load_ui_main(monkeypatch)
    liberar = threading.Event()

    def fake_ask(question, strategy, runtime, source_root=None, on_answer_delta=None):
        liberar.wait(5)
        return _ask_response("Tarde demais.")

    monkeypatch.setattr(module, "ask_corpus", fake_ask)
    api = module.Api()
    ask_id = api.startAsk("Pergunta?", "lexical")["ask_id"]

    assert api.cancelAsk(ask_id) == {"ok": True}
    assert api.pollAsk(ask_id)["error"] == "Pergunta não encontrada."
    liberar.set()


def test_desktop_api_cancel_ask_id_desconhecido_nao_falha(monkeypatch) -> None:
    module = _load_ui_main(monkeypatch)

    assert module.Api().cancelAsk("nao-existe") == {"ok": True}


def test_desktop_api_start_ask_falha_vira_stage_error(monkeypatch) -> None:
    module = _load_ui_main(monkeypatch)

    def fake_ask(question, strategy, runtime, source_root=None, on_answer_delta=None):
        raise ValueError("Pergunta vazia.")

    monkeypatch.setattr(module, "ask_corpus", fake_ask)
    api = module.Api()
    ask_id = api.startAsk("   ", "lexical")["ask_id"]

    final = _consulta_ate_fim(api, ask_id)

    assert final == {"ask_id": ask_id, "stage": "error", "partial": "", "result": None, "error": "Pergunta vazia."}


def test_desktop_api_start_ask_descarta_resposta_antiga_que_ninguem_consultou(monkeypatch) -> None:
    module = _load_ui_main(monkeypatch)
    monkeypatch.setattr(module, "ask_corpus", lambda *args, **kwargs: _ask_response("ok"))
    api = module.Api()
    agora = time.monotonic()
    api._ask_jobs["antiga"] = {
        "ask_id": "antiga", "stage": "done", "partial": "", "result": {}, "error": None, "finished_at": agora - 601,
    }
    api._ask_jobs["recente"] = {
        "ask_id": "recente", "stage": "done", "partial": "", "result": {}, "error": None, "finished_at": agora - 60,
    }

    api.startAsk("Pergunta?", "lexical")

    assert "antiga" not in api._ask_jobs
    assert "recente" in api._ask_jobs


def test_desktop_api_warm_answer_model_so_dispara_para_ollama_e_nao_empilha(monkeypatch, tmp_path: Path) -> None:
    module = _load_ui_main(monkeypatch)
    liberar = threading.Event()
    aquecidos: list[str] = []

    def fake_warm(settings) -> bool:
        aquecidos.append(settings.answer_provider)
        liberar.wait(5)
        return True

    monkeypatch.setattr(module, "warm_up_answer_model", fake_warm)
    api = module.Api()

    monkeypatch.setattr(module, "get_settings", lambda: _settings_do_provider(tmp_path, "lmstudio"))
    assert api.warmAnswerModel() == {"ok": True, "started": False}

    monkeypatch.setattr(module, "get_settings", lambda: _settings_do_provider(tmp_path, "ollama"))
    assert api.warmAnswerModel() == {"ok": True, "started": True}
    assert api.warmAnswerModel() == {"ok": True, "started": False}  # ainda aquecendo

    liberar.set()
    _espera(lambda: not api._warming)
    assert aquecidos == ["ollama"]
    assert api.warmAnswerModel() == {"ok": True, "started": True}  # terminou: pode aquecer de novo


def test_desktop_api_warm_answer_model_nunca_levanta_excecao(monkeypatch) -> None:
    module = _load_ui_main(monkeypatch)
    api = module.Api()

    def settings_quebrado():
        raise RuntimeError("settings corrompido")

    monkeypatch.setattr(module, "get_settings", settings_quebrado)

    assert api.warmAnswerModel() == {"ok": False, "started": False}
