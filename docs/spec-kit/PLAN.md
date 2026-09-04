# PLAN: Free Plaud Architectural Execution Plan

## 1. Modular Monolith Layout

```
tcc-free-plaud/
├── pipeline/src/free_plaud/
│   ├── app/              # Settings catalog, paths, doctor diagnostics, logging
│   ├── ingest/           # Loaders (PDF, TXT, MD), Obsidian cleaner, audio loader, watcher
│   ├── notes/            # Structurer, Pydantic Note schema, pt-BR normalizer, repository
│   ├── retrieval/        # Chunking with lineage, BM25 FTS5, Vector, Hybrid RRF, Grounded RAG
│   ├── providers/        # Adapters for LLMs, embeddings, Whisper transcription, model discovery
│   ├── storage/          # SQLite (FTS5) & ChromaDB vector stores
│   ├── corpus/           # CorpusRuntime, background jobs, Ask engine, discovery
│   ├── benchmark/        # Automated evaluation harness (MRR, Recall@k, latency comparisons)
│   ├── tui/              # Textual reactive app (`app.py`, `actions.py`, `app.tcss`, panes)
│   ├── cli.py            # Typer CLI subcommands
│   ├── config_cli.py     # Configuration CLI interface
│   ├── terminal_menu.py  # Rich interactive terminal menu
│   └── terminal_settings.py # Interactive settings terminal interface
├── UI/                   # PyWebView entrypoint (`main.py`) & React 19 / Tailwind / Vite frontend
├── docs/                 # Documentation, spec-kit, benchmarks, experiments, and TCC monograph
├── Sprints/              # Historical sprint deliverables (Sprint 00 - 08.2)
└── fp.ps1                # Canonical PowerShell launcher
```

---

## 2. End-to-End Execution Pipeline

1. **Multimodal Ingest & Normalization:**
   - Raw audio (`.mp3`, `.wav`, `.m4a`) processed via `Transcriber` (Whisper CUDA / API) -> raw transcription text.
   - Textual and PDF documents parsed and sanitized (Obsidian frontmatter & wikilinks cleaned).
   - Text normalized for pt-BR diacritics and OCR noise -> structured into canonical `Note` Markdown with metadata.

2. **Dual Indexing & Offset Lineage:**
   - Note text split into sliding chunks with exact character offsets (`start_char`, `end_char`) and line references.
   - Lexical indexing: SQLite FTS5 table with BM25 scoring and content hash deduplication.
   - Dense vector indexing: ChromaDB collection populated with normalized embeddings (`multilingual-e5-large` / `all-MiniLM-L6-v2`).

3. **Query & Grounded Retrieval:**
   - User submits query via any of the 4 interfaces.
   - Retrieval strategy (`lexical`, `vector`, `hybrid`) executes search.
   - In `hybrid` mode, RRF fuses ranked hits ($k=60$) with lexical weight 1.5 and vector weight 1.0.
   - Grounded context compiled and fed to LLM provider (Ollama / LM Studio / Cloud API).
   - Claims extracted, verified against source spans, and output with character-level citations or structured `no_answer`.

---

## 3. Interfaces & Unified Facade Decoupling

The facade layer (`free_plaud.tui.actions` and `free_plaud.corpus.runtime.CorpusRuntime`) ensures strict separation of concerns:
- **CLI (`free_plaud.cli` / `fp.ps1`)**: Invokes actions directly for pipeline automation and scripting.
- **Terminal Menu (`free_plaud.terminal_menu`)**: Interactive CLI wrapper over the runtime facade.
- **Textual TUI (`free_plaud.tui.app`)**: Reactive event-driven UI connecting worker threads to the runtime.
- **Desktop App (`UI/main.py` + React 19)**: PyWebView JS bridge bindings mapping frontend actions to `CorpusRuntime` and `actions.py`.
