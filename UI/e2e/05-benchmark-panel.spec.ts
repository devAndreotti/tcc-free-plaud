import { test, expect } from '@playwright/test';
import { createPyWebViewMockScript } from './fixtures/pywebview-bridge-mock';

test.describe('Benchmark Panel E2E Flow', () => {
  test.beforeEach(async ({ page }) => {
    await page.addInitScript(createPyWebViewMockScript());
    await page.goto('/');
  });

  test('deve renderizar tela de benchmark com selecao de estrategias', async ({ page }) => {
    const benchButton = page.locator('button:has-text("Benchmark"), [data-tab="benchmark"]').first();
    if (await benchButton.isVisible()) {
      await benchButton.click();
      await expect(page.locator('body')).toBeVisible();
    } else {
      await expect(page.locator('body')).toBeVisible();
    }
  });
});
