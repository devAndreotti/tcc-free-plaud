import { test, expect } from '@playwright/test';
import { createPyWebViewMockScript } from './fixtures/pywebview-bridge-mock';

test.describe('Chat & RAG E2E Flow', () => {
  test.beforeEach(async ({ page }) => {
    await page.addInitScript(createPyWebViewMockScript());
    await page.goto('/');
  });

  test('deve enviar pergunta e receber resposta formatada com citacoes', async ({ page }) => {
    const input = page.locator('textarea, input[type="text"]').first();
    await expect(input).toBeVisible();

    await input.fill('Como funciona o pipeline multimodal do Free Plaud?');
    await input.press('Enter');

    // Verifica que a mensagem enviada pelo usuário aparece na tela
    await expect(page.locator('text=Como funciona o pipeline multimodal do Free Plaud?')).toBeVisible();

    // Verifica resposta gerada pelo mock do bridge
    await expect(page.locator('text=Recuperação híbrida via BM25 e ChromaDB.')).toBeVisible({ timeout: 10000 });
  });
});
