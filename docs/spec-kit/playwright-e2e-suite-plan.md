# Plano Revisado: Suíte E2E Playwright (Senior Second Pass & Adversarial Delivery Audit)

## 1. Veredito & Diagnóstico Crítico
- **Veredito Inicial**: `Approved with adjustments` / `Risky`
- **Gaps Identificados na Versão Anterior**:
  - `[P1] Timing & Race Condition do Bridge`: O React lê `window.pywebview` no carregamento de módulo (`const isDesktopApp = typeof window !== 'undefined' && 'pywebview' in window`). Se o mock for injetado após o bundle inicial, o app chaveia para o fallback estático de dev em vez de testar os handlers de IPC reais.
  - `[P1] Poluição de Portas & CI Hang`: Usar `webServer` no Vite sem gerenciar timeout, porta ocupada (`5173`) e isolamento de builds pode travar o runner no GitHub Actions.
  - `[P2] Ausência de Testes Adversariais de UI`: O plano focava apenas no "caminho feliz". Faltavam testes de payload malformado (XSS via Markdown renderizado, timeout de LLM, erro de conexão com Ollama e cancelamento de jobs de indexação no meio do processamento).
  - `[P2] Falso Positivo de Cobertura SonarCloud`: O Playwright roda contra o bundle Vite no browser e não gera coverage direto de backend Python ou unitário React sem instrumentação explícita.

---

## 2. Arquitetura Corrigida da Suíte E2E

### 2.1 Injeção Determinística de Bridge (`beforeEach` / `addInitScript`)
A injeção do mock deve ocorrer a nível de contexto do browser antes de qualquer avaliação de script:
```typescript
await context.addInitScript(() => {
  (window as any).pywebview = {
    api: {
      askCorpus: async (payload: any) => mockAskResponse(payload),
      listNotes: async () => mockNotesList(),
      getCorpusStatus: async () => mockStatus(),
      startIndexJob: async () => ({ job_id: 'mock-job-123' }),
      getSettingsCatalog: async () => mockSettings(),
      // ... contratos completos
    }
  };
});
```

### 2.2 Matriz de Cenários: Caminho Feliz + Cenários Adversariais

| ID | Cenário | Tipo | Comportamento Esperado / Asserção |
|---|---|---|---|
| **E2E-01** | Ask RAG Happy Path | Funcional | Pergunta enviada, typing indicator exibido, markdown renderizado e chips de citação clicáveis. |
| **E2E-02** | XSS & Sanitização em Spans | **Adversarial (Segurança)** | Citação com `<img src=x onerror=alert(1)>` ou `<script>` deve ser sanitizada sem execução de script no DOM. |
| **E2E-03** | Timeout & Queda de Provedor LLM | **Adversarial (Resiliência)** | Mock rejeita com timeout (504); UI exibe banner de erro amigável sem quebrar o layout do chat. |
| **E2E-04** | Indexação Concorrente & Cancelamento | Funcional/Stress | Usuário inicia indexação de pasta grande, clica em "Cancelar"; status transiciona para `cancelled` sem travamento. |
| **E2E-05** | Benchmark Suite & Renderização | Funcional | Disparo de comparação de 3 estratégias; tabela exibe MRR, Recall@3 e latência sem valores `NaN` ou `undefined`. |
| **E2E-06** | Troca de Preset de Configuração | Integridade | Aplica preset `cpu_rapido`; inputs de formulário são atualizados e refletidos no estado global. |
| **E2E-07** | Corpus Vazio (Zero State) | Edge Case | Busca com zero notas no banco; exibe recomendação de indexação ao invés de tela em branco. |

---

## 3. Estrutura de Arquivos da Suíte

```text
UI/
├── e2e/
│   ├── fixtures/
│   │   ├── pywebview-bridge-mock.ts   # Mock completo e tipado de window.pywebview.api
│   │   ├── adversarial-payloads.ts    # Payloads de XSS, strings longas, respostas corrompidas
│   │   └── base-test.ts               # Test fixture customizada do Playwright pré-configurada
│   ├── pages/
│   │   ├── ChatPage.ts                # Page Object: Chat & Mensagens
│   │   ├── NotesPage.ts               # Page Object: Painel de Notas & Preview
│   │   ├── BenchmarkPage.ts           # Page Object: Painel de Avaliação
│   │   └── SettingsPage.ts            # Page Object: Modal de Configurações
│   ├── 01-chat-rag.spec.ts
│   ├── 02-security-xss.spec.ts        # Suite adversarial
│   ├── 03-notes-corpus.spec.ts
│   ├── 04-benchmark-eval.spec.ts
│   └── 05-settings-presets.spec.ts
├── playwright.config.ts
└── package.json                       # Scripts: "test:e2e", "test:e2e:ci"
```

---

## 4. Configuração do Runner Playwright (`playwright.config.ts`)
- **Porta Dedicada para Teste**: `5174` (evita colisão com `5173` do dev regular).
- **WebServer Determinístico**:
  ```typescript
  webServer: {
    command: 'npm run dev -- --port 5174 --strictPort',
    port: 5174,
    reuseExistingServer: !process.env.CI,
    timeout: 30000,
  }
  ```
- **Retries & Tracing**: `retries: process.env.CI ? 2 : 0`, `trace: 'on-first-retry'`.

---

## 5. Plano de Implementação em Fases

### Fase 1: Setup de Infraestrutura & Mock do Bridge
- [x] Instalar `@playwright/test` como devDependency em `UI/`.
- [x] Criar `UI/playwright.config.ts` com isolamento de portas e timeout estrito.
- [x] Implementar `UI/e2e/fixtures/pywebview-bridge-mock.ts` garantindo 100% de paridade com `Api` de `main.py`.

### Fase 2: Page Objects & Suíte Funcional
- [x] Implementar `base-test.ts` e Page Objects (`ChatPage`, `NotesPage`, `BenchmarkPage`, `SettingsPage`).
- [x] Implementar testes de fluxo principal (`01-chat-rag.spec.ts`, `03-notes-corpus.spec.ts`, `04-benchmark-eval.spec.ts`).

### Fase 3: Suíte Adversarial & Resiliência
- [x] Implementar testes de sanitização contra XSS e injeção de tags em spans (`02-security-xss.spec.ts`).
- [x] Implementar testes de timeout do LLM e interrupção de indexação.

### Fase 4: Integração no CI & Quality Gate
- [x] Adicionar script `npm run test:e2e` e `npm run test:e2e:ci`.
- [x] Atualizar `.github/workflows/quality-gate.yml` com job de execução Playwright.
- [x] Validar compatibilidade do ratchet e `qg -Check`.
