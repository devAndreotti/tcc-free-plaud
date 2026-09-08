# Implementation Plan: AutoRAG Rerank Calibration & Evaluation

**Branch**: `feat/spec-kit-tooling-and-diagrams` | **Date**: 2026-09-07 | **Spec**: `specs/001-featurename-autorag-rerank/spec.md`

## Summary
Calibrar os parâmetros de fusão híbrida (Reciprocal Rank Fusion k=60 vs pesos ponderados BM25/vetorial) e padronizar métricas de avaliação de recuperação (MRR, Recall@k e latência) para validação empírica dos experimentos do TCC.

## Technical Context
- **Language/Version**: Python 3.12+
- **Primary Dependencies**: faster-whisper, sentence-transformers, chromadb, sqlite3 (FTS5), typer, rich, pydantic
- **Storage**: SQLite (FTS5) + ChromaDB local
- **Testing**: pytest (369 tests, 100% passing)
- **Target Platform**: Windows 11 Desktop / Linux local-first
- **Project Type**: CLI + Desktop TUI/PyWebView PKM System
- **Performance Goals**: Benchmarks executando 50 queries em < 10s
- **Constraints**: 100% offline/local-first, sem dependência de nuvem para recuperação

## Constitution Check
- [x] Local-first: zero dados enviados a servidores externos durante a recuperação e indexação.
- [x] Dual persistence: FTS5 e ChromaDB mantidos sincronizados no benchmark.
- [x] Strict Span Citations: preservação de chunk_ids e offsets para checagem determinística.
- [x] Quality Gates & Ratchet: testes e lint sem regressão.

## Project Structure
```text
specs/001-featurename-autorag-rerank/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
└── contracts/
    └── benchmark-cli.md
```

## Source Code Structure
```text
pipeline/
├── src/free_plaud/
│   ├── benchmark/
│   │   ├── runner.py
│   │   └── metrics.py
│   ├── rag/
│   │   ├── fusion.py
│   │   └── retrieval.py
│   └── cli/
└── tests/
    └── test_benchmark.py
```
