# SPEC: Free Plaud (Open Local-First Multimodal PKM & Grounded RAG)

## 1. Overview & Vision
`free-plaud` (TCC Free Plaud) is an open-source, private, local-first multimodal Personal Knowledge Management (PKM) and Retrieval-Augmented Generation (RAG) system. Designed as a sovereign alternative to proprietary hardware and cloud AI recorders (such as Plaud Note/AI), it ingests multimodal inputs (audio recordings, PDF papers, text files, and Obsidian vaults), normalizes and structures them into canonical Markdown notes with rich frontmatter, and delivers grounded question-answering with mandatory character-level citations and strict hallucination prevention in Brazilian Portuguese (`pt-BR`).

---

## 2. Core Architectural Principles
1. **Local-First & Sovereign Privacy:** Data resides locally in SQLite and ChromaDB. Embeddings and Whisper transcription run on local hardware (CUDA 12.8 acceleration with CPU fallback) with optional cloud/local LLM endpoints (Ollama, LM Studio, OpenAI-compatible APIs).
2. **Decoupled Facade Layer:** Domain logic, indexing, and retrieval are decoupled from presentation layers via `free_plaud.tui.actions` and `free_plaud.corpus.runtime.CorpusRuntime`.
3. **Dual Persistence & Hybrid RRF:** Lexical indexing (SQLite FTS5 / BM25) and dense semantic indexing (ChromaDB) are combined using Reciprocal Rank Fusion (RRF) for optimal recall and precision.
4. **Anti-Hallucination & Exact Span Lineage:** Every claim generated in an answer must strictly map to source character offsets and line numbers (`claims` -> `citations`). If evidence is insufficient, the system returns a structured `no_answer` with actionable reasoning.

---

## 3. Detailed Functional Requirements

### 3.1 Multi-Interface Presentation Tier
The system exposes 4 cohesive interfaces sharing the exact same backend runtime:
1. **Typer CLI (`free_plaud.cli`, `free_plaud.config_cli`):**
   - Headless, scriptable automation subcommands (`ingest`, `notes`, `retrieval`, `benchmark`, `corpus`, `doctor`, `config`).
   - Integrated with PowerShell wrapper `fp.ps1`.
2. **Interactive Terminal Menu (`free_plaud.terminal_menu`, `free_plaud.terminal_settings`):**
   - Rich-powered numbered interactive CLI menu for fast terminal navigation, status checks, and preset adjustments.
3. **Textual Reactive TUI (`free_plaud.tui.app`):**
   - Full-screen terminal application using CSS styling (`app.tcss`) featuring reactive panes:
     - `AskPane`: Query execution across lexical, vector, and hybrid strategies with real-time streaming, latency tracking, and expandable citation inspectors.
     - `NotesPane`: Vault browser, note metadata viewer, and inline editor/re-indexer.
     - `BenchmarkPane`: Suite runner and comparative evaluator (MRR, Recall@k, latency).
     - `SettingsPane`: Configuration catalog and preset switcher.
4. **Desktop GUI (`UI/` - PyWebView + React 19 + Tailwind CSS):**
   - Windows native WebView2 container (`UI/main.py`) communicating over a bidirectional Python-JS bridge (`window.pywebview.api`).
   - React 19 frontend with real-time chat, Markdown rendering, force-directed note knowledge graph (`ForceGraph.tsx`, `GraphPanel.tsx`), queue monitors, and settings modals.

### 3.2 Multimodal Ingestion & Note Structuring
- **Audio Transcription Pipeline:**
  - `Transcriber.transcribe(source_path) -> str` remains compatible. The local audio runtime also returns raw/cleaned text, absolute segments, native word timestamps when available, model revision, effective device and cleaning decisions.
  - Whisper small defaults to Portuguese (`pt`), automatic CUDA (`int8_float16`) with one CPU (`int8`) retry for GPU availability/memory errors. SenseVoice supports zh/en/ja/ko/yue and Moonshine tiny supports English, both through sherpa-onnx on CPU. Explicit unsupported languages/devices fail before recording. GGUF is catalog/download only.
  - Microphone capture uses a bounded callback queue, streaming mono 16 kHz resampling and stateful Silero ONNX CPU VAD. Stop flushes trailing audio; cancel closes capture and prevents publication of transcription. Overflow/device/write failures are explicit.
  - Downloads are explicit, revision-pinned and SHA-256 verified before atomic publication. Offline listing/inference performs no model download. Original recordings and JSON provenance remain under the ignored worktree results directory.
  - Cleaning preserves ambiguous phrases, raw text and all timestamps. ONNX without alignment uses VAD segment bounds and no invented word times. Cleaned text feeds note normalization while raw transcription remains available.
  - Audio chunking and format normalization for `.mp3`, `.wav`, `.m4a`, and `.ogg`.
- **Document Loaders & Sanitizers:**
  - PDF document loader (`pypdf`) with layout awareness.
  - Obsidian Vault sanitizer (`ingest/obsidian_cleaner.py`): removes/transforms wikilinks (`[[link]]`), frontmatter metadata, embeds, and callout blocks without losing semantic content.
  - Plaintext and raw Markdown loaders (`.txt`, `.md`).
- **Canonical Note Generation (`notes/`):**
  - Pydantic canonical schema (`Note`, `NoteMetadata`, `ActionItem`, `Topic`).
  - Brazilian Portuguese normalizer (`notes/normalizer.py`): fixes OCR artifacts, diacritic irregularities, and whitespace corruption.
  - Automatic synthesis of executive summaries, key decisions, action items, and topic tags.

### 3.3 Dual Persistence & Hybrid Retrieval Engine
- **Lexical & Relational Store (`storage/sqlite.py`):**
  - SQLite with `FTS5` virtual table.
  - Granular chunk storage preserving exact document character offsets (`start_char`, `end_char`), line numbers, and content SHA-256 hashes.
- **Dense Vector Store (`storage/vector.py`):**
  - ChromaDB local persistence collections.
  - Multilingual sentence transformers (`multilingual-e5-large`, `all-MiniLM-L6-v2`, `paraphrase-multilingual-MiniLM-L12-v2`).
- **Reciprocal Rank Fusion (RRF) Hybrid Search (`retrieval/search.py`):**
  - Standardized formula:
    $$RRF\_Score(d) = \sum_{m \in \{lexical, vector\}} \frac{w_m}{k + \text{rank}_m(d)}$$
  - Default rank constant $k = 60$, lexical weight $w_{lex} = 1.5$, vector weight $w_{vec} = 1.0$.
  - Named anchor boosting and low-signal term pruning for high-precision query grounding.

### 3.4 Grounded RAG & Strict Span Citations (`retrieval/rag.py`)
- Extraction of verifiable factual claims from retrieved chunks.
- Mandatory citation generation linking claim sentences to chunk IDs, note IDs, source file paths, and exact text snippets.
- Hallucination guardrail: claims failing span verification are pruned or rejected.
- Deterministic fallback: when evidence is missing or below threshold, `no_answer=True` is returned with explicit `reason_for_no_answer` and diagnostic limitations.

### 3.5 Benchmarking, Diagnostics & Environment
- **Evaluation Harness (`benchmark/`):**
  - Standard evaluation suites measuring Mean Reciprocal Rank (MRR), Recall@1, Recall@3, Recall@5, and P95 latency.
  - Side-by-side strategy comparison (`lexical` vs `vector` vs `hybrid`).
  - Structured export to JSON and CSV.
- **System Doctor Diagnostics (`app/doctor.py`):**
  - Environment verification: CUDA GPU availability, PyTorch backend, Ollama server health, SQLite FTS5 capability, embedding model weights, and file system permissions.
