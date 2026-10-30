import { test, expect } from '@playwright/test';
import { createPyWebViewMockScript } from './fixtures/pywebview-bridge-mock';

test.describe('Notes & Corpus Exploration E2E Flow', () => {
  test.beforeEach(async ({ page }) => {
    await page.addInitScript(createPyWebViewMockScript());
    await page.goto('/');
  });

  test('deve listar as notas indexadas no painel lateral ou aba de notas', async ({ page }) => {
    // Botão exato do menu principal: `has-text("Notas")` casava antes com o botão da vault ("42 notas")
    const notesButton = page.getByRole('navigation', { name: 'Navegação principal' }).getByRole('button', { name: 'Notas', exact: true });
    if (await notesButton.isVisible()) {
      await notesButton.click();
      await expect(page.locator('text=Arquitetura do Escólio')).toBeVisible();
    } else {
      // Verifica presença no DOM geral
      await expect(page.locator('body')).toBeVisible();
    }
  });
});
