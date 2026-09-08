# Implementation Plan: AutoRAG Rerank Calibration & Multi-Agent Execution

**Branch**: `feat/spec-kit-tooling-and-diagrams` | **Date**: 2026-09-08 | **Spec**: `specs/001-featurename-autorag-rerank/spec.md`

## Multi-Agent Work Breakdown (5 Subagents)

### Subagent 1: Data Contracts & Config Engine
- **Responsibility**: Schemas Pydantic, parametrização dinâmica de RRF e persistência de settings.
- **Artifacts**:
  - `pipeline/src/free_plaud/rag/fusion.py` (ou `retrieval/fusion.py` / `retrieval/search.py`)
  - `pipeline/src/free_plaud/app/settings_catalog.py`
  - `pipeline/src/free_plaud/benchmark/metrics.py` (schemas de resultados)

### Subagent 2: Hybrid Retrieval & RRF Core
- **Responsibility**: Algoritmo de Reciprocal Rank Fusion com fator $k$ dinâmico e pesos de fusão.
- **Artifacts**:
  - `pipeline/src/free_plaud/retrieval/search.py` (`hybrid_search`, constante $k$)
  - `pipeline/src/free_plaud/retrieval/rag.py` (encaminhamento de parâmetros)
  - `pipeline/tests/test_rag.py` (testes de calibração de $k$)

### Subagent 3: Benchmark Harness & Evaluation Suite
- **Responsibility**: Runner comparativo (lexical vs vector vs hybrid) e cálculo de métricas (MRR, Recall@3, Recall@5, latência).
- **Artifacts**:
  - `pipeline/src/free_plaud/benchmark/runners.py`
  - `pipeline/src/free_plaud/benchmark/metrics.py`
  - `pipeline/tests/test_benchmark.py`

### Subagent 4: CLI, TUI & Facade Integration
- **Responsibility**: Comandos CLI Typer (`fp benchmark run`), menus interativos e facade `tui.actions`.
- **Artifacts**:
  - `pipeline/src/free_plaud/cli.py`
  - `pipeline/src/free_plaud/benchmark/cli.py`
  - `pipeline/src/free_plaud/services/corpus.py`

### Subagent 5: Validation, Experiment Docs & Quality Gate Ratchet
- **Responsibility**: Execução da suíte completa de testes, geração de relatório em `docs/experimentos/` e validação do ratchet.
- **Artifacts**:
  - `docs/experimentos/15_calibracao_rrf_tcc.md`
  - Quality Gate audit (`doctor.cjs`, `policy.json`, baseline ratchet)
