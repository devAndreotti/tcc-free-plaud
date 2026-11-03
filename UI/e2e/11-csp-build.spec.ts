import { test, expect } from '@playwright/test';
import { existsSync, readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { createPyWebViewMockScript } from './fixtures/pywebview-bridge-mock';

// CSP do build: abre dist/index.html por file:// (como o PyWebView) e exige 0 violações ao navegar.
// Não prova a janela real do PyWebView (WebView2/WebKit); só o Chromium do Playwright.
const distHtml = fileURLToPath(new URL('../dist/index.html', import.meta.url));
const hasDist = existsSync(distHtml);

test.skip(!hasDist, 'dist/ não existe: rode "npm run build" na pasta UI antes de executar este teste.');

// O app real também libera isso no WebView2 para carregar o bundle por file://.
test.use({ launchOptions: { args: ['--allow-file-access-from-files'] } });

test('build: CSP presente e sem violações ao navegar pelas telas principais', async ({ page }) => {
  // O Vite escapa as aspas simples da política como &#39;.
  const html = readFileSync(distHtml, 'utf-8').replaceAll('&#39;', "'");
  expect(html).toMatch(/<meta http-equiv="Content-Security-Policy" content="[^"]*script-src 'self'/);

  const consoleErrors: string[] = [];
  page.on('console', (msg) => {
    if (msg.type() === 'error' && /Content Security Policy|Refused to/i.test(msg.text())) consoleErrors.push(msg.text());
  });
  page.on('pageerror', (err) => consoleErrors.push(`pageerror: ${err.message}`));

  await page.addInitScript(createPyWebViewMockScript());
  await page.addInitScript(() => {
    const w = window as unknown as { __csp: string[] };
    w.__csp = [];
    document.addEventListener('securitypolicyviolation', (e) => {
      w.__csp.push(`${e.violatedDirective} -> ${e.blockedURI}`);
    });
  });

  await page.goto(`file:///${distHtml.replace(/\\/g, '/').replace(/^\//, '')}`);
  const nav = page.getByRole('navigation', { name: 'Navegação principal' });
  await expect(nav).toBeVisible();

  for (const name of ['Notas', 'Fila', 'Benchmark', 'Perguntar']) {
    await nav.getByRole('button', { name, exact: true }).click();
    await page.waitForTimeout(300);
  }
  await page.getByRole('button', { name: 'Configurações' }).first().click();
  await expect(page.getByRole('navigation', { name: 'Categorias de configuração' })).toBeVisible();
  await page.keyboard.press('Escape');
  await page.locator('#btn-grafos').click();
  await expect(page.locator('.force-graph__canvas')).toBeVisible();
  await page.waitForTimeout(500);

  const violations = await page.evaluate(() => (window as unknown as { __csp: string[] }).__csp);
  expect(violations).toEqual([]);
  expect(consoleErrors).toEqual([]);
});
