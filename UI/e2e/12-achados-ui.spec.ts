import { test, expect, type Page } from '@playwright/test';
import { createPyWebViewMockScript } from './fixtures/pywebview-bridge-mock';

// Coisas que só o navegador real prova: CSS aplicado (esqueleto com menos animação, seleção de texto),
// a ponte em segundo plano do Benchmark e as setas e o copiar no chat.

const summary = (strategy: string, mrr: number) => ({
  strategy,
  case_count: 2,
  query_count: 3,
  mrr,
  recall_at_3: 1,
  recall_at_5: 1,
  recall_at_10: 1,
  duration_ms: 100,
  avg_query_latency_ms: 10,
});
const compareResult = (id: string) => ({
  ok: true,
  comparison_id: id,
  suite_name: 'lote-cego-suite',
  embedding_model: 'chroma-default',
  top_k: 4,
  chunk_size: 800,
  overlap: 120,
  summaries: { lexical: summary('lexical', 0.7), vector: summary('vector', 0.8), hybrid: summary('hybrid', 0.9) },
  corpus: {
    note_count: 2,
    positive_count: 1,
    negative_count: 1,
    retrieval_depth: 10,
    summaries: { lexical: summary('lexical', 0.7), vector: summary('vector', 0.8), hybrid: summary('hybrid', 0.9) },
    queries: {
      hybrid: [
        { sample_id: 'p1', question: 'Qual é a sigla?', retrieved: [{ rank: 1, note_id: 'nota' }], relevant_rank: 1, answered: true, answer: 'A sigla é ACME.', expected_note_id: 'nota', expected_ref: 'Seção 1' },
        { sample_id: 'n1', question: 'Quando é a festa?', retrieved: [], answered: true, category: 'negativa' },
      ],
    },
  },
  cases: [],
  json_report_path: 'data/results/x.json',
  csv_report_path: 'data/results/x.csv',
});

// Roda dentro da página: a comparação avança um passo a cada consulta e termina no quarto.
const installBenchmark = ({ first, second }: { first: unknown; second: unknown }) => {
  const api = (window as unknown as { pywebview: { api: Record<string, unknown> } }).pywebview.api;
  const calls = { started: 0, polls: 0, cancelled: 0 };
  (window as unknown as { __bench: typeof calls }).__bench = calls;
  const job = (patch: object) => ({
    status: 'running',
    suite_name: 'lote-cego-suite',
    answer: false,
    phase: 'corpus',
    strategy: 'hybrid',
    question: 'Qual é a sigla?',
    done: calls.polls,
    total: 4,
    elapsed_ms: 1000,
    error: null,
    result: null,
    recent: [],
    ...patch,
  });
  api.previewBenchmarkSuite = async () => ({
    suite_name: 'lote-cego-suite',
    note_count: 2,
    positive_count: 1,
    negative_count: 1,
    questions: [{ question: 'Qual é a sigla?', note: 'nota', expected_ref: 'Seção 1', negative: false }],
  });
  api.listBenchmarkRuns = async () => [{
    comparison_id: 'cmp-antiga',
    suite_name: 'calibrada',
    started_at: '2026-11-04T01:00:00Z',
    duration_ms: 23000,
    answer_provider: 'extractive',
    answer_model: null,
    positive_count: 39,
    negative_count: 34,
    mrr: 0.944,
    recall_at_3: 1,
    answered_positive_rate: 0.97,
    abstention_recall: 0.62,
    accuracy: 0.81,
  }];
  api.loadBenchmarkRun = async () => first;
  api.startBenchmarkCompare = async () => {
    calls.started += 1;
    calls.polls = 0;
    return job({ done: 0 });
  };
  api.getBenchmarkJob = async () => {
    calls.polls += 1;
    if (calls.cancelled) return job({ status: 'cancelled' });
    if (calls.polls >= 4) return job({ status: 'done', done: 4, result: second });
    return job({});
  };
  api.cancelBenchmarkJob = async () => {
    calls.cancelled += 1;
    return job({});
  };
};

const abrirBenchmark = async (page: Page) => {
  await page.addInitScript(createPyWebViewMockScript());
  await page.addInitScript(installBenchmark, { first: compareResult('cmp-antiga'), second: compareResult('cmp-nova') });
  await page.goto('/');
  await page.getByRole('button', { name: 'Benchmark', exact: true }).click();
  await expect(page.getByRole('heading', { level: 1, name: 'Benchmark' })).toBeVisible();
};

test.describe('Benchmark', () => {
  test('prévia da suite, rodada anterior, progresso sem dados velhos e perguntas no fim', async ({ page }) => {
    await abrirBenchmark(page);

    await page.getByLabel('suite.json').fill('data/datasets/lote_cego/suite.json');
    await expect(page.getByText('2 notas · 1 com resposta · 1 sem resposta')).toBeVisible();

    await page.getByRole('button', { name: /^Abrir calibrada/ }).click();
    await expect(page.getByText('Rodada cmp-antiga aberta.')).toBeVisible();
    await expect(page.getByRole('heading', { name: 'Resultado por estratégia' })).toBeVisible();

    // Nova comparação: o resultado anterior sai na hora e a barra aparece.
    await page.getByRole('button', { name: 'Rodar comparação' }).click();
    await expect(page.getByRole('progressbar')).toBeVisible();
    await expect(page.getByText('Rodada cmp-antiga aberta.')).toHaveCount(0);
    await expect(page.locator('.bench__thesis')).toHaveCount(0);
    await expect(page.getByLabel('Rodando a comparação')).toBeVisible();

    await expect(page.getByText('Comparação cmp-nova concluída.')).toBeVisible();
    await expect(page.getByRole('progressbar')).toHaveCount(0);

    const perguntas = page.getByRole('region', { name: 'Perguntas e respostas' });
    await expect(perguntas.getByText('Qual é a sigla?')).toBeVisible();
    await perguntas.getByRole('button', { name: /Decisão errada/ }).click();
    await expect(perguntas.getByText('Quando é a festa?')).toBeVisible();
    await expect(perguntas.getByText('Qual é a sigla?')).toHaveCount(0);
  });

  test('trocar de tela não perde a comparação', async ({ page }) => {
    await abrirBenchmark(page);
    await page.getByLabel('suite.json').fill('data/datasets/lote_cego/suite.json');
    await page.getByRole('button', { name: 'Rodar comparação' }).click();
    await page.getByRole('button', { name: 'Fila', exact: true }).click();
    await page.getByRole('button', { name: 'Benchmark', exact: true }).click();
    await expect(page.getByText('Comparação cmp-nova concluída.')).toBeVisible();
    await expect(page.getByLabel('suite.json')).toHaveValue('data/datasets/lote_cego/suite.json');
    expect(await page.evaluate(() => (window as unknown as { __bench: { started: number } }).__bench.started)).toBe(1);
  });

  test('cancelar volta para a tela sem resultado', async ({ page }) => {
    await abrirBenchmark(page);
    await page.getByLabel('suite.json').fill('data/datasets/lote_cego/suite.json');
    await page.getByRole('button', { name: 'Rodar comparação' }).click();
    await page.getByRole('button', { name: 'Cancelar' }).click();
    await expect(page.getByText('Comparação cancelada.')).toBeVisible();
    await expect(page.getByRole('progressbar')).toHaveCount(0);
    await expect(page.getByRole('heading', { name: 'Resultado por estratégia' })).toHaveCount(0);
  });
});

test.describe('Esqueleto com menos animação', () => {
  const medir = (page: Page) =>
    page.evaluate(() => {
      const sk = document.createElement('span');
      sk.className = 'skeleton-box';
      const outro = document.createElement('span');
      outro.className = 'rise';
      document.body.append(sk, outro);
      const a = getComputedStyle(sk);
      const b = getComputedStyle(outro);
      return { nome: a.animationName, duracao: a.animationDuration, vezes: a.animationIterationCount, outro: b.animationDuration };
    });

  test('sem pedido do sistema, o brilho continua', async ({ page }) => {
    await page.emulateMedia({ reducedMotion: 'no-preference' });
    await page.goto('/');
    expect((await medir(page)).nome).toBe('shimmer');
  });

  test('com o sistema pedindo menos animação, só o esqueleto segue pulsando', async ({ page }) => {
    await page.emulateMedia({ reducedMotion: 'reduce' });
    await page.goto('/');
    const medida = await medir(page);
    expect(medida).toMatchObject({ nome: 'sk-pulse', duracao: '1.6s', vezes: 'infinite' });
    expect(Number.parseFloat(medida.outro)).toBeLessThan(0.001); // zerada pela regra global
  });

  test('"Nunca" reduz: tudo anima mesmo com o sistema pedindo menos', async ({ page }) => {
    await page.emulateMedia({ reducedMotion: 'reduce' });
    await page.addInitScript(() => window.localStorage.setItem('escolio:appearance', JSON.stringify({ motion: 'never' })));
    await page.goto('/');
    const medida = await medir(page);
    expect(medida.nome).toBe('shimmer');
    expect(medida.outro).toBe('0.5s');
  });

  test('"Sempre" reduz: o esqueleto pulsa mesmo sem pedido do sistema', async ({ page }) => {
    await page.emulateMedia({ reducedMotion: 'no-preference' });
    await page.addInitScript(() => window.localStorage.setItem('escolio:appearance', JSON.stringify({ motion: 'always' })));
    await page.goto('/');
    expect((await medir(page)).nome).toBe('sk-pulse');
  });
});

test.describe('Chat', () => {
  test('setas puxam os prompts, copiar pega o texto, e o texto pode ser selecionado', async ({ page, context }) => {
    await context.grantPermissions(['clipboard-read', 'clipboard-write']);
    await page.goto('/');
    const campo = page.getByRole('textbox').first();
    for (const pergunta of ['primeira pergunta', 'segunda pergunta']) {
      await campo.fill(pergunta);
      await campo.press('Enter');
      await expect(page.locator('.msg--user', { hasText: pergunta })).toBeVisible();
      await expect(campo).toBeEnabled({ timeout: 15000 });
    }

    await campo.fill('rascunho');
    await campo.press('Home');
    await campo.press('ArrowUp');
    await expect(campo).toHaveValue('segunda pergunta');
    await campo.press('ArrowUp');
    await expect(campo).toHaveValue('primeira pergunta');
    await campo.press('ArrowDown');
    await campo.press('ArrowDown');
    await expect(campo).toHaveValue('rascunho');

    const balao = page.locator('.msg--user', { hasText: 'primeira pergunta' });
    const copiar = balao.getByRole('button', { name: 'Copiar pergunta' });
    await expect(copiar).toHaveCSS('opacity', '0');
    await balao.hover();
    await expect(copiar).toHaveCSS('opacity', '1');
    await copiar.click();
    expect(await page.evaluate(() => navigator.clipboard.readText())).toBe('primeira pergunta');

    await expect(balao.locator('.msg__bubble')).toHaveCSS('user-select', 'text');
  });

  test('exportar oferece os formatos', async ({ page }) => {
    await page.goto('/');
    const campo = page.getByRole('textbox').first();
    await campo.fill('uma pergunta');
    await campo.press('Enter');
    await page.getByRole('button', { name: 'Exportar conversa' }).click();
    for (const formato of ['Markdown', 'Texto simples', 'Página HTML', 'JSON', 'PDF']) {
      await expect(page.getByRole('button', { name: new RegExp(formato) })).toBeVisible();
    }
    await expect(page.getByRole('checkbox', { name: 'Incluir as fontes de cada resposta' })).toBeChecked();
  });
});
