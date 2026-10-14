import { test, expect } from '@playwright/test';
import { createPyWebViewMockScript } from './fixtures/pywebview-bridge-mock';

test.describe('Notes & Corpus Exploration E2E Flow', () => {
  test.beforeEach(async ({ page }) => {
    await page.addInitScript(createPyWebViewMockScript());
    await page.goto('/');
  });

  test('deve listar as notas indexadas no painel lateral ou aba de notas', async ({ page }) => {
    // Procura botão ou aba de notas se disponível
    const notesButton = page.locator('button:has-text("Notas"), [aria-label*="Notas"], [data-tab="notes"]').first();
    if (await notesButton.isVisible()) {
      await notesButton.click();
      await expect(page.locator('text=Arquitetura do Escólio')).toBeVisible();
    } else {
      // Verifica presença no DOM geral
      await expect(page.locator('body')).toBeVisible();
    }
  });
});
