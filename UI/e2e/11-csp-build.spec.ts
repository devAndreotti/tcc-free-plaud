import { test, expect } from '@playwright/test';
import { existsSync, readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { createPyWebViewMockScript } from './fixtures/pywebview-bridge-mock';

// CSP do build: abre dist/index.html por file:// e exige 0 violações ao navegar.
// O app real é servido pelo PyWebView em http://127.0.0.1:<porta>; essa janela foi conferida à mão em
// 2026-11-03 (WebView2: ponte, fontes, 0 violações e 0 requisições externas). Este teste usa o Chromium do Playwright.
const distHtml = fileURLToPath(new URL('../dist/index.html', import.meta.url));
const hasDist = existsSync(distHtml);

test.skip(!hasDist, 'dist/ não existe: rode "npm run build" na pasta UI antes de executar este teste.');

// Necessário só neste teste, para o Chromium carregar o bundle por file://.
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
  // Local-first: nenhuma requisição http(s) para fora da máquina em toda a navegação.
  const external: string[] = [];
  page.on('request', (req) => {
    const { protocol, hostname } = new URL(req.url());
    if ((protocol === 'http:' || protocol === 'https:') && !['localhost', '127.0.0.1', '[::1]'].includes(hostname)) external.push(req.url());
  });

  await page.addInitScript(createPyWebViewMockScript());
  await page.addInitScript(() => {
    // O mock compartilhado não traz o catálogo de ajustes que a tela de Configurações lê.
    const api = (window as unknown as { pywebview: { api: Record<string, (...args: unknown[]) => Promise<unknown>> } }).pywebview.api;
    const original = api.getBackendSettings;
    api.getBackendSettings = async () => ({ ...(await original()) as object, settings_catalog: [] });
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
  expect(external).toEqual([]);

  // As fontes embutidas carregam de verdade por file:// (faces com status "loaded", sem cair no sistema).
  const fonts = await page.evaluate(async () => {
    await document.fonts.ready;
    const families = ['IBM Plex Sans', 'IBM Plex Mono', 'Source Serif 4'];
    return Object.fromEntries(
      families.map((family) => [family, [...document.fonts].filter((f) => f.family.replaceAll('"', '') === family && f.status === 'loaded').length]),
    );
  });
  for (const [family, loaded] of Object.entries(fonts)) expect(loaded, `faces carregadas de ${family}`).toBeGreaterThan(0);
  expect(consoleErrors).toEqual([]);
});
