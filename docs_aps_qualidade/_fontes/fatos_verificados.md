# Fatos verificados em 2026-10-14

Verificados pelo agente principal. Cite como "verificado em 2026-10-14", indicando a fonte entre parênteses.

## Projeto
- Nome atual: **Escólio**, antes "free-plaud" / "Evil Plaud".
  - Renomeado no PR #119, merge `dbb82fe` em 2026-10-14.
  - Repo: GitHub `devAndreotti/tcc-free-plaud` (privado).
  - Pacote Python `pipeline/src/escolio`. CLI `escolio`. Wrappers `es` / `es.ps1`.
- Fallbacks de compatibilidade em `pipeline/src/escolio/app/legacy.py`:
  - variáveis `FREE_PLAUD_*`;
  - `free_plaud.sqlite3`;
  - coleção Chroma `free_plaud_chunks`;
  - chaves de localStorage `free-plaud:*`.
- Corpus real do autor, no PC Windows (comando `escolio corpus status`):
  - 668 notas, 4.195 chunks em SQLite, 4.195 em FTS5 e 4.195 vetores;
  - 0 vetores obsoletos e 0 faltantes;
  - status `inconsistent` por `embedding_model_mismatch_count = 4195`. O índice foi gerado com `chroma-default`, mas a configuração atual usa `paraphrase-multilingual-MiniLM-L12-v2` em CUDA.
- Mensageria / filas externas: não existe. A "fila" do app é interna (Dropzone, PR #101).

## CI/CD (`.github/workflows/quality-gate.yml`)
- Jobs, todos com `runs-on: [self-hosted, linux, ostg02, tcc]`:
  - Security audit;
  - Lint;
  - Tests & ratchet;
  - Build & smoke;
  - SonarCloud (`needs: test`);
  - Docker image gate;
  - PR report (`needs` todos, só em pull_request).
- `desktop-release.yml` roda em `windows-latest` (hosted), Node 20.
- **O Playwright NÃO roda em nenhum workflow** (grep sem resultado em `.github/workflows`). Ele roda manual/local:
  - em 2026-10-14, na VPS ARM: 7/7 specs passaram em 36,7 s com 2 workers, Chromium headless, via `npx playwright test`;
  - no PR #118 (bump do Playwright 1.64.0), também 7/7.
- Proteção do branch `main` (API do GitHub):
  - checks obrigatórios: Security audit, Lint, Tests & ratchet, Docker image gate, Build & smoke, SonarCloud;
  - strict = true (branch precisa estar atualizado com a main);
  - 0 revisões obrigatórias;
  - enforce_admins = false.
- Runner:
  - `hermes-ostg02-tcc-runner`, versão 2.337.0, serviço systemd `actions.runner.devAndreotti-tcc-free-plaud.hermes-ostg02-tcc-runner.service`;
  - diretório `/mnt/volume-50gb/ci-runners/tcc-free-plaud-runner` (3,9 GB; `_work` 3,5 GB);
  - **1 slot**: os jobs entram em fila; Security audit chegou a levar 16m38s esperando cache.
  - Host: VM Oracle Cloud (OCI) `hermes-agent-01` / OSTG02, shape VM.Standard.A1.Flex (**ARM aarch64**), região eu-amsterdam-1, Ubuntu (kernel 6.17 oracle), cerca de 11 GiB de RAM, swap extra de 4 GB;
  - disco raiz de 96 GB (94% usado em 2026-10-14) e volume de 50 GB (83%).
  - A tenancy OCI está no limite Always Free (200 GB de block storage).
  - Adotado no PR #93 (2026-09-21): "ci: self-hosted runner OSTG 0.2". No mesmo PR, o node-version subiu para 22 por causa de uma regressão do undici no Node 20.20 (commit 97b1ece).
  - PR #103 (2026-10-01): torch de CPU no CI e no release.
- Incidente em 2026-10-13: o volume do runner lotou e os jobs falhavam com "No space left on device" ou travavam cerca de 10 min sem executar passos.
  - Limpeza: venv de 6,6 GB movida, versão antiga do runner (2.322.0, 1,25 GB) removida, logs `_diag` com mais de 3 dias apagados, runner duplicado removido.
  - Resultado: volume de 100% para 65%.
- PRs do Dependabot não recebem secrets (`SONAR_TOKEN`), por isso o job SonarCloud sempre falha neles. A prática é consolidar num PR único (precedentes #113 e #118).
- `UI/package-lock.json` é versionado com CRLF. npm e Dependabot regravam em LF e o diff vira o arquivo inteiro, então é preciso restaurar o CRLF.

## Tempos e resultados observados em 2026-10-14
- PR #118 (run 38563746866):
  - Docker gate 25 s, Lint 4m46s, Security audit 16m38s, Build & smoke 4m52s;
  - Tests & ratchet 23m33s, **falhou por teste instável da TUI** (`test_tui_ask_button_ignores_double_click_while_running`, `assert ['hybrid','hybrid'] == ['hybrid']`). Na re-execução passou (14m47s).
- PR #119 (run 38576721730):
  - Tests & ratchet 13m23s; os demais passaram;
  - SonarCloud falhou por Security Rating C on New Code. Causa: a renomeação fez o código antigo contar como "novo", e a issue antiga `python:S2245` (PRNG em `benchmark/metrics.py:157`, bootstrap de intervalo de confiança com seed fixa) entrou no cálculo.
  - A issue foi marcada como falso positivo pelo dono, com justificativa; a re-execução passou.
- CONTAGEM ATUAL (main dbb82fe, depois do #119): **498 testes pytest, 498 passaram em 594,56 s (9m54s) na CI**, run 38576721730; Vitest com 86 testes. O #119 acrescentou 14 testes pytest e 2 Vitest de fallback/migração.
- Pytest completo na VPS (2026-10-14, main ANTERIOR 6c442ee): 484 coletados, **483 passaram e 1 falhou** em 22m37s. A falha foi `tests/test_tui_app.py::test_tui_notes_cancel_button_cancels_running_index`, que passou 3/3 isolado (flaky por timing de `pilot.pause` e thread).
- UI (antes do #119): Vitest com 84/84 testes em 16 arquivos (86 depois do #119); ESLint limpo; `vite build` ok (bundle principal de 347,84 kB, 103,39 kB em gzip).
- Smoke do backend real (VPS, corpus temporário de 10 docs, 78 chunks):
  - 14/15 perguntas positivas respondidas com citação;
  - 5/6 negativas abstidas;
  - 2 defeitos achados e ainda abertos:
    - (a) "Qual versão do Kubernetes roda no cluster de produção?" foi respondida com uma frase irrelevante do doc de Docker, em vez de se abster;
    - (b) "Quando o componente MAJOR deve ser incrementado?" teve abstenção falsa (`missing_named_anchor`) no modo híbrido.
  - Transcrição do fixture de áudio pt-BR em CPU idêntica à referência.
  - A CLI leva cerca de 90 s por invocação nessa VPS ARM.

## SonarCloud
Coletado via API em 2026-10-14; arquivo bruto em `docs_aps_qualidade/_fontes/sonar_raw.txt`.
- Organização `devandreotti`, projeto `devAndreotti_tcc-free-plaud`.
- Quality gate "Sonar way" (padrão). Condições sobre CÓDIGO NOVO:
  - new_security_rating, new_reliability_rating e new_maintainability_rating ≤ A;
  - new_coverage ≥ 80%;
  - new_duplicated_lines_density ≤ 3%;
  - new_security_hotspots_reviewed = 100%.
- Perfil de regras: "Sonar way comprehensive".
- Métricas do código atual (análise do PR #119 = main atual):
  - ncloc 14.839;
  - cobertura 84,9% (linhas 87,7%, branches 68,6%);
  - duplicação 0,8% (13 blocos);
  - débito técnico (sqale_index) 338 min, debt ratio 0,1%, manutenibilidade A;
  - 53 code smells, 0 bugs (confiabilidade A), 0 vulnerabilidades (segurança A), 0 hotspots;
  - complexidade ciclomática 2.729, cognitiva 2.380.
- Última análise bem-sucedida da main: 2026-07-21. As análises da main falham desde 2026-10-08 com "CE Task finished abnormally" (lado do servidor).
  - Métricas daquela análise: ncloc 16.686; cobertura 80,3% (linhas 81,2%, branches 54,7%); duplicação 0,8%; débito 1.129 min; 116 code smells; 2 bugs; 1 vulnerabilidade (segurança E); 4 hotspots.
  - Issues abertas nela (119): 116 code smells, 2 bugs, 1 vulnerabilidade. Severidades: 57 MAJOR, 38 CRITICAL, 22 MINOR, 1 BLOCKER, 1 INFO.
  - Regras mais frequentes:
    - python:S3776 (complexidade cognitiva), 21;
    - typescript:S6819 (roles ARIA), 17;
    - python:S1192 (literal duplicado), 15;
    - python:S8786, 9;
    - typescript:S7780, 8.

## Evidência de desempenho existente
Cite os arquivos:
- `docs/spec-kit/AUDIO_VALIDATION.md` (6 clips FLEURS):
  - Whisper small em CPU: WER 0,0790, CER 0,0673, RTF 0,78;
  - Whisper em CUDA: RTF 0,30;
  - Whisper com VAD: WER 0,0895.
- Experimentos de recuperação 01/07/08 (suíte de 4 documentos e 16 consultas):
  - léxico: MRR 0,96875, 86–130 ms;
  - vetorial: MRR 0,79, 600–1.180 ms;
  - híbrido: MRR 0,96875 com peso léxico 1,5, 690–817 ms.
- Exp. 13: corpus Obsidian de 294 chunks, cerca de 2–12 s por pergunta.
- PR #102: a pergunta "aquecida" caiu de cerca de 3 s para cerca de 0,5 s.
- **O exp. 15 (MRR 0,884, ~42 ms) não tem n, comando nem artefato, e contradiz os exp. 01/07/08. Não use como métrica confiável;** se citar, marque como "não reproduzível".
- Artefatos locais não versionados no PC Windows (`D:\Dev\Repos\Own\tcc-free-plaud\data\results\`): `benchmark_compare/`, `experiments/02_calibracao/*`, `experiments/03_embeddings/*`, `vector_store_*`.
