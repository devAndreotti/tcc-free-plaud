# TASKS: Free Plaud Implementation & Multi-Agent Execution Plan

> **Protocolo Obrigatório de Conclusão para Todos os Agentes:**
> 1. **Desenvolvimento Isolado**: Trabalhar exclusivamente na worktree e branch designadas.
> 2. **Abertura de PR**: Ao terminar tasks, fazer push e abrir PR contra a branch `main` (`gh pr create`).
> 3. **Quality Gate & Babysit**: Rodar a suite completa de validação:
>    - Backend: `uv run pytest` e `ruff check .`
>    - Frontend: `npm run test:coverage` (Vitest)
>    - E2E: `npx playwright test`
>    - Diagnóstico: `python -m free_plaud.cli doctor`
> 4. **Monitoramento de CI**: Acompanhar checks do GitHub Actions e SonarCloud (skill `babysit`).
> 5. **Merge**: Realizar `gh pr merge --squash --delete-branch` somente após 100% dos checks verdes.
> 6. **Sync**: Worktrees subsequentes devem atualizar com `git pull origin main --rebase`.

---

## [CODEX] Worktree 1: Multimodal Audio, VAD & STT Pipeline (Inspirado no Handy - Mais Complexa)
- **Worktree**: `../wt-audio`
- **Branch**: `feat/audio-vad-stt-pipeline`
- **Responsável / Perfil**: Codex / Astra (Alta complexidade, DSP, CUDA e ONNX)
- **Referência Arquitetural**: Handy (arquitetura de streaming de áudio, pipeline VAD desacoplado, fallback de STT local-first e catalogação offline de modelos)
- [x] Define Transcriber protocol interface in `providers/transcribe.py`.
- [x] Implement concrete Whisper integration (`torchaudio` CUDA 12.8 / `faster-whisper`) and audio chunking.
- [x] Implement model discovery and runtime provider diagnostics (`providers/model_discovery.py`, `app/doctor.py`).
- [x] Implementar captura de áudio ao vivo do microfone com resample 16 kHz e Silero VAD em `pipeline/src/free_plaud/ingest/audio_capture.py`.
- [x] Criar catálogo offline `models_catalog.json` com metadados ONNX/GGUF, SHA-256 e download Hugging Face verificado.
- [x] Implementar runtime ONNX leve para SenseVoice e Moonshine convivendo com Faster-Whisper.
- [x] Implementar limpeza conservadora de áudio/transcrição, preservando original e timestamps.
- [x] Expandir testes automatizados de áudio/VAD e fixtures de avaliação reproduzíveis em `pipeline/tests/test_audio_vad.py` e arquivos auxiliares.
- [x] Atualizar as tarefas da Worktree 1 com evidências de implementação e Quality Gate local.

Evidência local: 432 testes Python, 17 testes VAD pela raiz, 64 testes de
scripts, 12 testes UI e 7 E2E passaram. Cobertura 89,5%; ratchet e Ruff passaram;
doctor do Quality Gate 9/9. Inferência real em SenseVoice/Moonshine CPU e
Whisper small CPU/CUDA. Microfone: 47.398 amostras mono/16 kHz, sem fala detectada.
Avaliação FLEURS: 54 execuções. Detalhes e limitações em
`docs/spec-kit/AUDIO_VALIDATION.md`. Entrega e checks finais: [PR #69](https://github.com/devAndreotti/tcc-free-plaud/pull/69).

---

## [CLAUDE] Worktree 2: Vector Optimization & TurboQuant Compression (Média-Alta)
- **Worktree**: `../wt-turboquant`
- **Branch**: `feat/turboquant-compression`
- **Responsável / Perfil**: Claude (Opus) (Álgebra linear, quantização e RAG)
- [x] Avaliar e implementar compressao vetorial extrema estilo TurboQuant para embeddings locais SentenceTransformers antes de persistir em SQLite / ChromaDB.
- [x] Criar o modulo de quantizacao vetorial em runtime `pipeline/src/free_plaud/providers/embed_compressor.py` para reduzir footprint de RAM e disco.
- [x] Adaptar o salvamento e leitura de vetores comprimidos mantendo compatibilidade total com a busca hibrida RRF (k=60).
- [x] Criar suite de benchmark comparativa em `pipeline/src/free_plaud/benchmark/` avaliando tradeoffs de MRR, Recall@k e latencia (float32 vs embeddings quantizados).
- [x] Adicionar testes unitarios rigorosos em `pipeline/tests/test_embed_compressor.py`.
- [x] Atualizar `docs/spec-kit/TASKS.md` marcando as caixas da Worktree 2 com `[x]`.

---

## [CLAUDE] Worktree 3: TCC Academic Monograph & Research Synthesis (Média)
- **Worktree**: `../wt-tcc-mono`
- **Branch**: `docs/tcc-monograph-final`
- **Responsável / Perfil**: Claude (Opus) (Síntese científica, análise de dados e texto do TCC)
- [x] Consolidate empirical results and evaluation metrics (Experiment 15, RRF $k=60$, MRR, Recall@k) into final academic monograph (`docs/tcc/texto/TCC.md`).
- [x] Answer core research questions (P1: hybrid vs single retrieval, P2: chunking strategy impact, P3: local model viability) with quantitative tables and citations.
- [x] Review references and bibliography against `docs/referencias_ia/`.

---

## [CLAUDE] Worktree 4: Playwright E2E Suite & Settings Parity Audit (Média)
- **Worktree**: `../wt-e2e`
- **Branch**: `test/playwright-e2e-parity`
- **Responsável / Perfil**: Claude (Opus) (Testes E2E, contratos frontend-backend e segurança)
- [x] Run and validate Playwright E2E test suite (`UI/e2e/01-chat-rag.spec.ts` to `07-zero-state.spec.ts`) against Vite test server with mock IPC bridge.
- [x] Verify full parity and bidirectional persistence of settings across CLI (`terminal_settings.py`), TUI (`tui/app.py - SettingsPane`) and GUI (`SettingsModal.tsx` / `user_settings.json`).
- [x] Verify hot-reloading of embedding and LLM provider configurations across all three interfaces without application restart.
- [x] Execute adversarial Playwright UI test suite (XSS payload sanitization in Markdown/spans and 504 provider timeout handling).

---

## [AGY] Worktree 5: Filesystem Watcher & UI Dropzone (Simples)
- **Worktree**: `../wt-watcher`
- **Branch**: `feat/watcher-and-dropzone`
- **Responsável / Perfil**: Agy (Automação e UI React)
- [x] Implement automated filesystem watcher daemon (`ingest/watcher.py`) for live folder sync.
- [x] Implement batch audio/document dropzone in Desktop UI with real-time transcription/indexing progress.
- [x] Add visual notifications/toasts when new notes are auto-ingested.

---

## [AGY] Worktree 6: Desktop Packaging, Release & Defense Slides (Simples)
- **Worktree**: `../wt-release`
- **Branch**: `chore/release-and-slides`
- **Responsável / Perfil**: Agy (Build, scripts e apresentação)
- [x] Build and verify release distribution bundle (`pywebview` desktop app executable and portable CLI package `fp.ps1`).
- [x] Prepare final presentation slides and demo walkthrough script based on dataset (`data/corpus/notes`).
- [x] Run full unified health check script (`fp doctor` e `npm run test:coverage`).

---

## Histórico Concluído: Phase 1 Core Domain & Retrieval (Sprints 00-07)
- [x] Document loaders (PDF, TXT, MD) e limpador Obsidian (`ingest/obsidian_cleaner.py`).
- [x] Estruturador de Notas, extração de metadados e normalizador pt-BR (`notes/normalizer.py`).
- [x] Persistência dupla (SQLite FTS5 + ChromaDB) com offsets exatos por caractere.
- [x] Busca híbrida Reciprocal Rank Fusion (RRF) com $k=60$.
- [x] Extração rígida de claims, citações de span e guardrails anti-alucinação `no_answer`.
- [x] Typer CLI (`free_plaud.cli`, `free_plaud.config_cli`) e launcher `fp.ps1`.
- [x] Menu interativo Rich no terminal (`terminal_menu.py`, `terminal_settings.py`).
- [x] Textual TUI (`tui/app.py`, `app.tcss`) com painéis Ask, Notes, Benchmark e Settings.
- [x] Suite de benchmark automatizado (`benchmark/`) computando MRR, Recall@k e latência.
- [x] Container PyWebView nativo (`UI/main.py`) com ponte bidirecional Python-JS.
- [x] Frontend React 19 + Tailwind CSS (Chat, Note Browser, Settings Modal, Benchmark Viewer).
- [x] Grafo de conhecimento interativo 2D/3D (`UI/src/components/ForceGraph.tsx`, `GraphPanel.tsx`).
