# Plano de Implementação: Suíte E2E com Playwright para o Free Plaud

## 1. Visão Geral
Estruturar e configurar uma suíte completa de testes End-to-End (E2E) com Playwright no frontend React/Vite (`UI/`), simulando o ciclo de vida do usuário na interface desktop: envio de perguntas ao corpus, navegação por notas, disparo de benchmarks, alteração de configurações e inspeção do grafo de conhecimento.

---

## 2. Arquitetura da Suíte E2E

### 2.1 Camada de Mock do Bridge PyWebView
- O frontend consome `window.pywebview.api`.
- Em modo E2E no navegador (Chromium/Playwright), o Playwright injeta um mock determinístico do objeto `window.pywebview.api` antes do carregamento da página (`page.addInitScript`).

### 2.2 Cenários de Teste E2E
1. **Chat & RAG Ask Flow (`chat-rag.spec.ts`)**:
   - Digitação de pergunta no `ChatInput`.
   - Exibição de indicador de digitação.
   - Renderização da resposta com formatação Markdown e citações de fontes.
2. **Notes & Corpus Exploration (`notes-corpus.spec.ts`)**:
   - Abertura do painel de notas (`NotesPanel`).
   - Listagem de notas, busca textual e visualização de detalhes.
3. **Benchmark Panel & Runs (`benchmark.spec.ts`)**:
   - Acesso ao `BenchmarkPanel`.
   - Seleção de estratégia de busca (lexical, vector, hybrid).
   - Execução e renderização da tabela comparativa com métricas de MRR e Recall.
4. **Settings & Presets Modal (`settings.spec.ts`)**:
   - Abertura do `SettingsModal`.
   - Alteração de parâmetros de embedding e provider generativo.
   - Aplicação de presets (ex: `cpu_rapido`).
5. **Knowledge Graph Navigation (`graph-view.spec.ts`)**:
   - Troca de aba para o `GraphPanel` / `GraphView`.
   - Renderização dos nós do grafo e interatividade de zoom/pan.

---

## 3. Estrutura de Arquivos Proposta

```text
UI/
├── e2e/
│   ├── fixtures/
│   │   ├── pywebview-mock.ts     # Mock do bridge window.pywebview.api
│   │   └── mock-data.ts          # Dados sintéticos de notas, benchmark e configurações
│   ├── pages/
│   │   ├── ChatPage.ts           # Page Object Model para o Chat
│   │   ├── NotesPage.ts          # POM para o Painel de Notas
│   │   ├── BenchmarkPage.ts      # POM para o Painel de Benchmark
│   │   └── SettingsModalPage.ts  # POM para o Modal de Configurações
│   ├── chat-rag.spec.ts
│   ├── notes-corpus.spec.ts
│   ├── benchmark.spec.ts
│   ├── settings.spec.ts
│   └── graph-view.spec.ts
├── playwright.config.ts
└── package.json                  # Adição de scripts: "test:e2e", "test:e2e:ui"
```

---

## 4. Integração no Quality Gate e CI
1. Adicionar job `e2e` no GitHub Actions (`.github/workflows/quality-gate.yml`) rodando `npx playwright test`.
2. Incluir `playwright.config.ts` com `webServer` apontando para `npm run dev` na porta `5173`.
3. Adicionar checagem no `doctor.cjs` para validar a presença da suíte Playwright.

---

## 5. Passos de Execução
- [ ] **Passo 1**: Instalar dependências do Playwright (`@playwright/test`) em `UI/package.json`.
- [ ] **Passo 2**: Criar `UI/playwright.config.ts` com suporte a execução headless local e CI.
- [ ] **Passo 3**: Implementar o mock de `window.pywebview.api` em `UI/e2e/fixtures/pywebview-mock.ts`.
- [ ] **Passo 4**: Desenvolver Page Objects e testes E2E para Chat, Notes, Benchmark e Settings.
- [ ] **Passo 5**: Rodar e validar a suíte localmente (`npx playwright test`).
- [ ] **Passo 6**: Integrar na pipeline do Quality Gate.
