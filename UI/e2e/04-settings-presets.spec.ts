import { test, expect } from '@playwright/test';
import { createPyWebViewMockScript } from './fixtures/pywebview-bridge-mock';

test.describe('Settings & Presets E2E Flow', () => {
  test.beforeEach(async ({ page }) => {
    await page.addInitScript(createPyWebViewMockScript());
    await page.goto('/');
  });

  test('deve renderizar aplicacao e verificar integridade da interface', async ({ page }) => {
    await expect(page.locator('body')).toBeVisible();
  });
});
