import { test, expect, type Page } from '@playwright/test';

// Fluxos do redesenho no navegador, com o modo de navegador do app (bridge sem desktop).
// Regressão: desbloqueio do Avançado, presets, diagnóstico, Aparência ligada a "Reduzir animações" e a Fila que vira job.

const openSettings = async (page: Page, tab: string) => {
  await page.getByRole('button', { name: 'Configurações' }).first().click();
  await page.getByRole('navigation', { name: 'Categorias de configuração' }).getByRole('button', { name: tab, exact: true }).click();
};

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => window.localStorage.clear());
  await page.goto('/');
  await expect(page.getByRole('heading', { level: 1 })).toBeVisible();
});

test('Avançado: bloqueado explica, libera com confirmação e mostra presets e grupos', async ({ page }) => {
  await openSettings(page, 'Avançado');

  const mostrar = page.getByRole('button', { name: 'Mostrar ajustes avançados' });
  await expect(mostrar).toBeDisabled();
  await page.getByRole('checkbox', { name: /Entendo que estes ajustes/ }).check();
  await mostrar.click();

  await expect(page.getByRole('button', { name: 'Ocultar Avançado' })).toBeVisible({ timeout: 5000 });
  await expect(page.getByRole('heading', { name: /Presets/ })).toBeVisible();
  await expect(page.getByRole('region', { name: 'Busca', exact: true })).toBeVisible();

  await page.getByRole('button', { name: 'Ocultar Avançado' }).click();
  await expect(page.getByRole('button', { name: 'Mostrar ajustes avançados' })).toBeVisible();
});

test('Geral: Verificar de novo roda o diagnóstico e volta com o resultado', async ({ page }) => {
  await openSettings(page, 'Geral');
  const again = page.getByRole('button', { name: 'Verificar de novo' });
  await expect(again).toBeVisible();
  await again.click();
  await expect(page.getByRole('button', { name: 'Verificar de novo' })).toBeEnabled({ timeout: 5000 });
  await expect(page.getByRole('img', { name: /verificações ok/ })).toBeVisible();
});

test('Aparência: Reduzir animações vale no app inteiro e a prévia acompanha', async ({ page }) => {
  await openSettings(page, 'Aparência');

  const motion = page.getByRole('radiogroup', { name: 'Reduzir animações' });
  await motion.getByRole('radio', { name: 'Sempre' }).click();
  await expect(page.locator('html')).toHaveAttribute('data-motion', 'always');
  await expect(page.getByText('Animações desligadas em todo o app.')).toBeVisible();

  await page.getByRole('radiogroup', { name: 'Tamanho do texto' }).getByRole('radio', { name: '110%' }).click();
  await expect(page.locator('html')).toHaveAttribute('data-text-size', '110');
  await expect(page.getByLabel('Prévia da aparência')).toBeVisible();
});

test('Fila: sem job mostra a arte; Indexar vira o job com a lista Agora e Fechar volta', async ({ page }) => {
  await page.getByRole('button', { name: 'Fila', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Nada indexando agora' })).toBeVisible();

  await page.getByRole('textbox').filter({ hasText: '' }).first().fill('C:\\Users\\usuario\\Documents\\Vault (mock)');
  await page.getByRole('button', { name: 'Indexar', exact: true }).click();

  const job = page.getByRole('article', { name: 'Job atual' });
  await expect(job).toBeVisible({ timeout: 5000 });
  const feed = job.getByRole('region', { name: 'Arquivos processados agora' });
  await expect(feed.getByText('Redes\\OSPF.md')).toBeVisible();
  await expect(feed.getByText('6 trechos')).toBeVisible();

  // Regressão: o cartão encolhia na coluna da página (overflow hidden num item flex) e cortava a última fileira.
  await page.waitForTimeout(800);
  const card = await page.getByRole('region', { name: 'Indexação' }).boundingBox();
  const lastKpi = await job.getByText('Modo de commit').boundingBox();
  expect(card && lastKpi && lastKpi.y + lastKpi.height <= card.y + card.height).toBeTruthy();

  await expect(job.getByRole('button', { name: 'Fechar' })).toBeVisible({ timeout: 15000 });
  await job.getByRole('button', { name: 'Fechar' }).click();
  await expect(page.getByRole('heading', { name: 'Nada indexando agora' })).toBeVisible();
});
