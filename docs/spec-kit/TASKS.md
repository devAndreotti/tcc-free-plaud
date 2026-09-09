# TASKS: Free Plaud Implementation & Verification Tasks

## Phase 1: Core Domain, Storage & Retrieval (Complete - Sprints 00-07)
- [x] Implement document loaders (PDF, TXT, MD) and Obsidian vault cleaner (`ingest/obsidian_cleaner.py`).
- [x] Implement Note structuring, metadata extraction, and pt-BR normalizer (`notes/normalizer.py`).
- [x] Implement dual persistence (SQLite FTS5 + ChromaDB) with exact chunk character offsets.
- [x] Implement Reciprocal Rank Fusion (RRF) hybrid search with configurable $k=60$ constant and weights.
- [x] Implement strict claim extraction, character-level span citations, and `no_answer` anti-hallucination guardrails.
- [x] Implement Typer CLI (`free_plaud.cli`, `free_plaud.config_cli`) and `fp.ps1` launcher.
- [x] Implement Rich interactive terminal menu (`terminal_menu.py`, `terminal_settings.py`).
- [x] Implement Textual TUI (`tui/app.py`, `app.tcss`) with `AskPane`, `NotesPane`, `BenchmarkPane`, and `SettingsPane`.
- [x] Implement automated benchmark harness (`benchmark/`) computing MRR, Recall@k, and latency.

## Phase 2: Multimodal Audio, Transcription & Providers (In Progress)
- [x] Define `Transcriber` protocol interface in `providers/transcribe.py`.
- [x] Implement concrete Whisper integration (`torchaudio` CUDA 12.8 / `faster-whisper`) and audio chunking.
- [x] Implement model discovery and runtime provider diagnostics (`providers/model_discovery.py`, `app/doctor.py`).
- [ ] Add live audio recording capture directly from microphone into the ingestion queue.
- [ ] Expand automated transcription fixture tests and evaluation datasets.

## Phase 3: Desktop Shell & Knowledge Graph (Active & Next)
- [x] Implement PyWebView native container (`UI/main.py`) with bidirectional Python-JS bridge.
- [x] Implement React 19 + Tailwind CSS frontend with Chat, Note Browser, Settings Modal, and Benchmark Viewer.
- [x] Implement 3D/2D force-directed interactive knowledge graph (`UI/src/components/ForceGraph.tsx`, `GraphPanel.tsx`).
- [ ] Implement automated filesystem watcher daemon (`ingest/watcher.py`) for live folder sync.
- [ ] Implement batch audio dropzone in Desktop UI with real-time transcription progress.

## [CODEX] Worktree 1: Multimodal Audio, VAD & STT Pipeline

Sprint 09 — `wt-audio`, branch `feat/audio-vad-stt-pipeline`.

- [x] Implementar captura de áudio ao vivo do microfone com resample 16 kHz e Silero VAD em `pipeline/src/free_plaud/ingest/audio_capture.py`.
- [x] Criar catálogo offline `models_catalog.json` com metadados ONNX/GGUF, SHA-256 e download Hugging Face verificado.
- [x] Implementar runtime ONNX leve para SenseVoice e Moonshine convivendo com Faster-Whisper.
- [x] Implementar limpeza conservadora de áudio/transcrição, preservando original e timestamps.
- [x] Expandir testes automatizados de áudio/VAD e fixtures de avaliação reproduzíveis em `pipeline/tests/test_audio_vad.py` e arquivos auxiliares.
- [ ] Concluir atualização das tarefas da Worktree 1 com Quality Gate final e evidências de entrega.

Evidência parcial: 406 testes Python, 17 testes VAD após correção de cortes,
6 testes adicionais de integração e 64 testes de scripts passaram. Inferência
real validada em SenseVoice/Moonshine CPU e Whisper small CPU/CUDA. Captura real
de 3 segundos produziu 47.398 amostras mono/16 kHz, sem fala detectada. Avaliação
FLEURS: 54 execuções nos três modos. Resultados e limitações em
`docs/spec-kit/AUDIO_VALIDATION.md`. Gate final, PR/CI e merge ainda pendentes.
