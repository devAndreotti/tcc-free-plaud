import { test, expect, type Page } from '@playwright/test';
import { createPyWebViewMockScript } from './fixtures/pywebview-bridge-mock';

// O app não sanitiza HTML: a proteção vem do escape do React, que mostra a tag como texto.
// Por isso os testes conferem o que o usuário vê (texto literal) e que nada executou.

const PAYLOAD = '<img src="invalid-image" onerror="window.xss=1;alert(1)"> e <script>window.xss=2</script>';

const watchDialogs = (page: Page) => {
  const seen: string[] = [];
  page.on('dialog', async (dialog) => {
    seen.push(dialog.message());
    await dialog.dismiss();
  });
  return seen;
};

const expectNothingExecuted = async (page: Page, dialogs: string[]) => {
  await expect(page.locator('.msg img')).toHaveCount(0);
  await expect(page.locator('[onerror]')).toHaveCount(0);
  // O onerror de uma imagem inserida dispararia logo; esta é a única espera por tempo.
  await page.waitForTimeout(1500);
  expect(await page.evaluate(() => (window as unknown as { xss?: unknown }).xss)).toBeUndefined();
  expect(dialogs).toEqual([]);
};

test.describe('Adversarial & Security E2E Flow', () => {
  test('E2E-SEG-01: resposta com HTML perigoso aparece como texto e nada executa (escape do React, sem sanitizador)', async ({ page }) => {
    const dialogs = watchDialogs(page);

    const maliciousScript = `
      (function() {
        window.pywebview = {
          api: {
            loadVaultPath: async function() { return "/mock/vault"; },
            sendMessage: async function() {
              return "Conteúdo com injeção: <img src=\\"invalid-image\\" onerror=\\"window.xss=1;alert(1)\\"> e <script>window.xss=2</script>";
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
    // As tags aparecem escritas, não interpretadas.
    const answer = page.locator('.msg--ai .msg__answer');
    await expect(answer).toContainText('<img src="invalid-image" onerror="window.xss=1;alert(1)">');
    await expect(answer).toContainText('<script>window.xss=2</script>');
    await expectNothingExecuted(page, dialogs);
  });

  test('E2E-SEG-01: o payload digitado na pergunta também aparece como texto e não executa', async ({ page }) => {
    const dialogs = watchDialogs(page);
    // O mock devolve "Resposta sintetizada para: <pergunta>": o payload volta na resposta.
    await page.addInitScript(createPyWebViewMockScript());
    await page.goto('/');

    const input = page.locator('textarea, input[type="text"]').first();
    await input.fill(PAYLOAD);
    await input.press('Enter');

    await expect(page.locator('.msg--user .msg__bubble')).toHaveText(PAYLOAD);
    await expect(page.locator('.msg--ai .msg__answer').first()).toContainText(PAYLOAD, { timeout: 10000 });
    await expectNothingExecuted(page, dialogs);
  });
});
