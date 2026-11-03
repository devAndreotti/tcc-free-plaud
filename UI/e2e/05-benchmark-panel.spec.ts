import { test, expect } from '@playwright/test';

// Benchmark no modo navegador do app. A 08 cobre o estado vazio e a 09 a seção "Resposta da IA";
// aqui a tela abre, roda a comparação e mostra o resultado das três estratégias.

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => window.localStorage.clear());
  await page.goto('/');
  await expect(page.getByRole('heading', { level: 1 })).toBeVisible();
});

test('Benchmark: abre a tela, exige a suite e mostra o resultado por estratégia depois de rodar', async ({ page }) => {
  await page.getByRole('button', { name: 'Benchmark', exact: true }).click();

  await expect(page.getByRole('heading', { level: 1, name: 'Benchmark' })).toBeVisible();
  const run = page.getByRole('button', { name: 'Rodar comparação' });
  await page.getByLabel('suite.json').fill('');
  await expect(run).toBeDisabled();

  await page.getByLabel('suite.json').fill('data/datasets/manual_validation/suite.json');
  await expect(run).toBeEnabled();
  await run.click();

  await expect(page.getByRole('heading', { name: 'Resultado por estratégia' })).toBeVisible({ timeout: 8000 });
  await expect(page.getByRole('heading', { name: 'Recall@k' })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Relatórios desta comparação' })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Nenhum benchmark executado nesta sessão.' })).toHaveCount(0);
});
