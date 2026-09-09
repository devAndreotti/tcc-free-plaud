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

## [CLAUDE] Worktree 2: Vector Optimization & TurboQuant Compression
- [x] Avaliar e implementar compressao vetorial extrema estilo TurboQuant para embeddings locais SentenceTransformers antes de persistir em SQLite / ChromaDB.
- [x] Criar o modulo de quantizacao vetorial em runtime `pipeline/src/free_plaud/providers/embed_compressor.py` para reduzir footprint de RAM e disco.
- [x] Adaptar o salvamento e leitura de vetores comprimidos mantendo compatibilidade total com a busca hibrida RRF (k=60).
- [x] Criar suite de benchmark comparativa em `pipeline/src/free_plaud/benchmark/` avaliando tradeoffs de MRR, Recall@k e latencia (float32 vs embeddings quantizados).
- [x] Adicionar testes unitarios rigorosos em `pipeline/tests/test_embed_compressor.py`.
- [x] Atualizar `docs/spec-kit/TASKS.md` marcando as caixas da Worktree 2 com `[x]`.
