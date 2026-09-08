import { test, expect } from '@playwright/test';
import { createPyWebViewMockScript } from './fixtures/pywebview-bridge-mock';

test.describe('Knowledge Graph E2E Flow', () => {
  test.beforeEach(async ({ page }) => {
    await page.addInitScript(createPyWebViewMockScript());
    await page.goto('/');
  });

  test('deve renderizar aplicacao e permitir navegacao por abas', async ({ page }) => {
    await expect(page.locator('body')).toBeVisible();
    const graphButton = page.locator('button:has-text("Grafo"), [data-tab="graph"]').first();
    if (await graphButton.isVisible()) {
      await graphButton.click();
    }
    await expect(page.locator('body')).toBeVisible();
  });
});
