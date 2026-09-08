import { test, expect } from '@playwright/test';

test.describe('Zero State E2E Flow', () => {
  test('deve tratar corpus vazio sem quebrar a interface', async ({ page }) => {
    const emptyCorpusScript = `
      (function() {
        window.pywebview = {
          api: {
            loadVaultPath: async function() { return null; },
            listNotes: async function() { return []; },
            getBackendSettings: async function() { return {}; },
            getDoctor: async function() { return { status: "ok", checks: [] }; },
            listSettingsPresets: async function() { return []; },
            sendMessage: async function() { return "Nenhum documento encontrado no corpus."; }
          }
        };
      })();
    `;

    await page.addInitScript(emptyCorpusScript);
    await page.goto('/');

    const input = page.locator('textarea, input[type="text"]').first();
    await input.fill('Pergunta sem corpus');
    await input.press('Enter');

    await expect(page.locator('text=Nenhum documento encontrado no corpus.')).toBeVisible({ timeout: 10000 });
  });
});
