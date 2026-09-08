# Tasks: AutoRAG Rerank Calibration & Evaluation

**Input**: Design documents from `specs/001-featurename-autorag-rerank/`

## Phase 1: Setup
- [ ] T001 Verify benchmark test fixtures and datasets in `pipeline/tests/fixtures/`
- [ ] T002 [P] Create benchmark output directory in `pipeline/data/benchmarks/`

## Phase 2: Foundational
- [ ] T003 [P] Implement `RerankConfig` in `pipeline/src/free_plaud/rag/fusion.py`
- [ ] T004 Implement `RetrievalBenchmarkResult` schema in `pipeline/src/free_plaud/benchmark/metrics.py`

## Phase 3: User Story 1 - RRF Fusion Dynamic Parameters (Priority: P1) 🎯 MVP
**Goal**: Allow flexible adjustment of RRF smoothing factor `k` and hybrid weights during retrieval.
**Independent Test**: `uv run pytest pipeline/tests/test_rag.py`

- [ ] T005 [P] [US1] Add unit tests for dynamic `k` in `pipeline/tests/test_rag.py`
- [ ] T006 [US1] Implement configurable `k` in RRF fusion function `pipeline/src/free_plaud/rag/fusion.py`
- [ ] T007 [US1] Expose `k_rrf` parameter in `CorpusService.ask` and `tui.actions` in `pipeline/src/free_plaud/services/corpus.py`

## Phase 4: User Story 2 - Automated Retrieval Evaluation & Metrics (Priority: P2)
**Goal**: Compute MRR, Recall@3, Recall@5 and latency across lexical, vector and hybrid strategies.
**Independent Test**: `uv run pytest pipeline/tests/test_benchmark.py`

- [ ] T008 [P] [US2] Implement MRR and Recall calculation in `pipeline/src/free_plaud/benchmark/metrics.py`
- [ ] T009 [US2] Implement runner execution logic in `pipeline/src/free_plaud/benchmark/runner.py`
- [ ] T010 [US2] Add CLI command `fp benchmark run` in `pipeline/src/free_plaud/cli.py`

## Phase 5: Polish & Validation
- [ ] T011 [P] Document calibration findings and results in `docs/experimentos/15_calibracao_rrf_tcc.md`
- [ ] T012 Run end-to-end quickstart validation per `specs/001-featurename-autorag-rerank/quickstart.md`
- [ ] T013 Verify Quality Gate ratchet with `& (Get-ScriplyQualityGateScript) -Check`
