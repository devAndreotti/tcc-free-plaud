# Plano Mestre de Execução e Conclusão do TCC (Multi-Agente)

## Subagentes & Divisão de Trabalho

### Subagente 1: Consolidação da Monografia do TCC
- **Objetivo**: Integrar arquitetura, metodologia e resultados empíricos do Experimento 15 no texto de `docs/tcc/texto/TCC.md`.
- **Entregáveis**: `docs/tcc/texto/TCC.md` atualizado com tabela de resultados, análise de RRF ($k=60$) e respostas às perguntas de pesquisa (P1, P2, P3a).

### Subagente 2: Expansão da Suíte E2E Playwright
- **Objetivo**: Completar os cenários de teste E2E do frontend cobrindo Settings, Benchmark, Grafo e Zero-State.
- **Entregáveis**:
  - `UI/e2e/04-settings-presets.spec.ts`
  - `UI/e2e/05-benchmark-panel.spec.ts`
  - `UI/e2e/06-graph-view.spec.ts`
  - `UI/e2e/07-zero-state.spec.ts`

### Subagente 3: Execução e Validação Completa de Testes
- **Objetivo**: Rodar 100% dos testes unitários, E2E e backend sem falhas.
- **Comandos**:
  - Vitest: `npm run test:coverage`
  - Playwright: `npx playwright test`
  - Pytest: `uv run pytest`
  - Quality Gate: `doctor` e `check`

### Subagente 4: Abertura e Gestão de PR
- **Objetivo**: Criar PR da branch `feat/tcc-monograph-and-e2e-expansion` para a `main`.

### Subagente 5: Babysit CI & Merge Final
- **Objetivo**: Monitorar GitHub Actions e SonarCloud, corrigir eventuais desvios e realizar squash merge para a `main`.
