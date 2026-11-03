import { test, expect, type Page } from '@playwright/test';

// Configurações no modo navegador do app (ponte sem desktop). A 08 cobre Avançado, Diagnóstico, Aparência,
// Fontes de IA e Voz em detalhe; aqui ficam a navegação completa e o preset aplicado até o fim.

const TABS = ['Diagnóstico', 'Vaults', 'Fontes de IA', 'Voz', 'Avançado', 'Aparência'];

const openSettings = async (page: Page) => {
  await page.getByRole('button', { name: 'Configurações' }).first().click();
  const nav = page.getByRole('navigation', { name: 'Categorias de configuração' });
  await expect(nav).toBeVisible();
  return nav;
};

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => window.localStorage.clear());
  await page.goto('/');
  await expect(page.getByRole('heading', { level: 1 })).toBeVisible();
});

test('Configurações: a navegação lista as seis abas e cada uma mostra o próprio conteúdo', async ({ page }) => {
  const nav = await openSettings(page);
  await expect(nav.getByRole('button')).toHaveText(TABS);

  const headings: Array<[string, string | RegExp]> = [
    ['Diagnóstico', /^Diagnóstico/],
    ['Vaults', 'Vaults'],
    ['Fontes de IA', 'Fontes de IA'],
    ['Voz', 'Voz'],
    ['Avançado', 'Avançado'],
    ['Aparência', 'Aparência'],
  ];
  for (const [tab, heading] of headings) {
    await nav.getByRole('button', { name: tab, exact: true }).click();
    await expect(nav.getByRole('button', { name: tab, exact: true })).toHaveAttribute('aria-current', 'page');
    await expect(page.getByRole('heading', { level: 3, name: heading, exact: typeof heading === 'string' })).toBeVisible();
  }
});

test('Preset: a prévia mostra o que muda e Aplicar grava e avisa', async ({ page }) => {
  const nav = await openSettings(page);
  await nav.getByRole('button', { name: 'Avançado', exact: true }).click();
  await page.getByRole('checkbox', { name: /Entendo que estes ajustes/ }).check();
  await page.getByRole('button', { name: 'Mostrar ajustes avançados' }).click();

  await page.getByRole('button', { name: 'Aplicar preset GPU qualidade' }).click();
  const preview = page.getByLabel('Prévia do preset GPU qualidade');
  await expect(preview).toBeVisible({ timeout: 5000 });
  await expect(preview.getByRole('list', { name: 'O que muda' })).toBeVisible();

  await preview.getByRole('button', { name: 'Aplicar', exact: true }).click();
  await expect(page.getByRole('status').filter({ hasText: /Preset .+ aplicado\./ })).toBeVisible({ timeout: 5000 });
  await expect(preview).toHaveCount(0);
});
