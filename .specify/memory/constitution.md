# Escólio Constitution

## Core Principles

### I. Local-First & Privacy Non-Negotiable
All ingestion, text cleaning, STT processing (Whisper CUDA/CPU), dual indexing (SQLite FTS5 + ChromaDB), and vector calculations execute on the local machine by default. User notes, transcripts, audio, and embeddings never leave the device unless explicitly routed to an external LLM endpoint requested by the user.

### II. Dual Persistence & Hybrid AutoRAG (BM25 + Vectors)
Every document chunk is indexed deterministically in SQLite FTS5 for exact lexical match and in ChromaDB for semantic embeddings. Retrieval runs Reciprocal Rank Fusion (RRF k=60) combining both candidate sets to guarantee high recall without false positives.

### III. Strict Span Citations & Zero Hallucinations
RAG answers must map claims to exact character/token offset spans in the source notes. Any response failing deterministic span verification must be rejected or clearly flagged with corpus insufficiency instead of generating fabricated information.

### IV. Test & Ratchet Enforcement
Code changes must pass strict preflight quality gates (qg doctor, qg check). Test coverage cannot regress below the established ratchet baseline. Quality Gate scripts and policies govern CI and local validation.

### V. Lean Architecture & Multi-Interface Consistency
The backend exposes a single unified facade (tui.actions / runtime) consumed identically by CLI (Typer), TUI (Textual), and Desktop GUI (PyWebView + React 19). No business logic lives inside UI presentation components.

## Technical Standards & Stack
- Language & Package Manager: Python 3.12+ managed via uv, Node.js + npm for UI.
- Data & Models: Pydantic schemas for domain contracts, SQLite with FTS5 extension, ChromaDB.
- AI & STT: faster-whisper (CUDA 12.8 / PyTorch), SentenceTransformers for embeddings, Ollama / OpenAI-compatible API providers for generation.

## Quality Gates & Verification
1. uv run pytest across backend test suites.
2. ruff check and ruff format enforcement.
3. Node audit, TypeScript build and lint for /UI.
4. Ratchet metrics verification via Quality Gate before merging.

## Governance
This constitution sets the non-negotiable architectural invariants of Escólio. Any evolution requires spec update, rationale in docs/, and quality gate validation.

**Version**: 1.0.0 | **Ratified**: 2026-09-07 | **Last Amended**: 2026-09-07
