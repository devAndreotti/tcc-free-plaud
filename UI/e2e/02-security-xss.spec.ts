import { test, expect } from '@playwright/test';

test.describe('Adversarial & Security E2E Flow', () => {
  test('deve sanitizar tags html perigosas em respostas markdown sem executar scripts', async ({ page }) => {
    let alertTriggered = false;
    page.on('dialog', async dialog => {
      alertTriggered = true;
      await dialog.dismiss();
    });

    const maliciousScript = `
      (function() {
        window.pywebview = {
          api: {
            loadVaultPath: async function() { return "/mock/vault"; },
            sendMessage: async function() {
              return "Conteúdo com injeção: <img src=\\"invalid-image\\" onerror=\\"alert(1)\\"> e <script>window.xss=true</script>";
            },
            listNotes: async function() { return []; },
            getBackendSettings: async function() { return {}; },
            getDoctor: async function() { return { status: "ok", checks: [] }; },
            listSettingsPresets: async function() { return []; }
          }
        };
      })();
    `;

    await page.addInitScript(maliciousScript);
    await page.goto('/');

    const input = page.locator('textarea, input[type="text"]').first();
    await input.fill('Teste de injeção XSS');
    await input.press('Enter');

    await expect(page.locator('text=Conteúdo com injeção:')).toBeVisible({ timeout: 10000 });
    expect(alertTriggered).toBe(false);
  });
});
