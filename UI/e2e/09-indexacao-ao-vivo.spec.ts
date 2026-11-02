import { test, expect, type Page } from '@playwright/test';

// Indexação ao vivo, no modo navegador do app: o job de exemplo lê 2 arquivos por consulta (1 por segundo)
// e grava o lote anterior, como os micro-lotes do backend. São 6 arquivos, em 4 consultas.

const startIndexing = async (page: Page) => {
  await page.getByRole('button', { name: 'Fila', exact: true }).click();
  await page.getByRole('textbox').filter({ hasText: '' }).first().fill('C:\\Users\\usuario\\Documents\\Vault (mock)');
  await page.getByRole('button', { name: 'Indexar', exact: true }).click();
};

const chooseAi = async (page: Page) => {
  await page.getByRole('button', { name: /^Como responder/ }).click();
  await page.getByRole('button', { name: /qwen2\.5:3b/ }).click();
};

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => window.localStorage.clear());
  await page.goto('/');
  await expect(page.getByRole('heading', { level: 1 })).toBeVisible();
});

test('Grafo: cresce durante o job, mostra o arquivo atual e o que espera gravação, e termina com tudo gravado', async ({ page }) => {
  await page.getByRole('button', { name: 'Abrir painel de grafos' }).click();
  const count = page.locator('.graph-panel__count');
  await expect(count).toBeVisible();
  const before = Number(await count.textContent());

  await startIndexing(page);

  const live = page.locator('.graph-panel__live');
  await expect(live).toContainText('Ao vivo', { timeout: 5000 });
  await expect(live).toContainText(/\.md · 2 aguardando gravação/);
  // Regressão: o grafo só mudava no fim do job. Aqui ele cresce com o job ainda rodando.
  await expect.poll(async () => Number(await count.textContent()), { timeout: 5000 }).toBeGreaterThan(before + 2);
  await expect(live).toBeVisible();

  await expect(live).toBeHidden({ timeout: 10000 });
  await expect(count).toHaveText(String(before + 6));
});

test('Barra lateral: notas e trechos sobem durante o job, sem esperar ele terminar', async ({ page }) => {
  await startIndexing(page);
  const job = page.getByRole('article', { name: 'Job atual' });
  await expect(job).toBeVisible({ timeout: 5000 });

  // Antes de o job acabar (o botão Fechar só aparece no fim) a contagem já saiu do zero.
  await expect(page.getByText(/[2-4] notas · \d+ trechos/)).toBeVisible({ timeout: 6000 });
  await expect(job.getByRole('button', { name: 'Fechar' })).toBeHidden();

  await expect(page.getByText('6 notas · 18 trechos')).toBeVisible({ timeout: 10000 });
});

test('Seletor de vault e pastas da Fila: as contagens sobem durante o job', async ({ page }) => {
  const vault = page.getByText(/4\d notas · \d+ pasta/).first();
  await expect(vault).toHaveText(/42 notas/);
  await startIndexing(page);
  const roots = page.getByRole('region', { name: 'Pastas no corpus' });
  await expect(roots.getByText('42 notas')).toBeVisible();

  // 2 ou 4: o job ainda não terminou (ao final são 48).
  await expect(vault).toHaveText(/4[46] notas/, { timeout: 6000 });
  await expect(roots.getByText(/4[46] notas/)).toBeVisible({ timeout: 3000 });

  await expect(vault).toHaveText(/48 notas/, { timeout: 10000 });
  await expect(roots.getByText('48 notas')).toBeVisible();
});

test('Chat: resposta no meio da indexação diz quanto já estava no corpus e, no fim, oferece perguntar de novo', async ({ page }) => {
  await startIndexing(page);
  await expect(page.getByRole('article', { name: 'Job atual' })).toBeVisible({ timeout: 5000 });

  await page.getByRole('button', { name: 'Perguntar', exact: true }).click();
  const input = page.locator('textarea').first();
  await input.fill('Como a reindexação decide se uma nota mudou?');
  await input.press('Enter');

  const during = page.getByRole('region', { name: 'Indexação em andamento' });
  await expect(during).toContainText(/\d de 6 arquivos desta pasta já estavam no corpus/, { timeout: 8000 });
  await expect(during.getByRole('button', { name: 'Perguntar de novo' })).toHaveCount(0);

  const done = page.getByRole('region', { name: 'Indexação terminada' });
  await expect(done).toContainText('A indexação terminou', { timeout: 10000 });
  await expect(page.locator('article.msg--ai')).toHaveCount(1);
  await done.getByRole('button', { name: 'Perguntar de novo' }).click();

  // A pergunta repetida já vê o corpus completo: resposta nova, sem aviso.
  await expect(page.locator('article.msg--ai')).toHaveCount(2, { timeout: 8000 });
  await expect(page.locator('article.msg--ai').last().locator('.msg__during')).toHaveCount(0);
});

test('Rascunho: os [n] da IA aparecem como chips enquanto ela escreve', async ({ page }) => {
  await chooseAi(page);
  const input = page.locator('textarea').first();
  await input.fill('Como a reindexação decide se uma nota mudou?');
  await input.press('Enter');

  await expect(page.locator('.msg__ref--draft').first()).toHaveText('1', { timeout: 8000 });
  await expect(page.locator('.msg__draft')).not.toContainText('[1]');
});

test('Benchmark: com a opção ligada, mostra aceitas e motivos de descarte por estratégia', async ({ page }) => {
  await chooseAi(page);
  await page.getByRole('button', { name: 'Benchmark', exact: true }).click();

  await page.getByRole('checkbox', { name: /Medir também a resposta da IA/ }).check({ force: true });
  await page.getByLabel('suite.json').fill('data/datasets/manual_validation/suite.json');
  await page.getByRole('button', { name: 'Rodar comparação' }).click();

  const section = page.getByRole('region', { name: 'Resposta da IA' });
  await expect(section).toContainText('37 de 38', { timeout: 8000 });
  await expect(section).toContainText('generated_no_answer_sentinel');
  await expect(section).toContainText('A IA disse que os trechos não respondem');

  await section.getByRole('radio', { name: 'Lexical' }).click();
  await expect(section).toContainText('36 de 39');
  await expect(section).toContainText('echoed_context_metadata');
});
