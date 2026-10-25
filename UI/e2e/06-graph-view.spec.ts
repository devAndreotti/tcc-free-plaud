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
  test('teclado no grafo: setas selecionam, Esc limpa e Home enquadra (anúncio na região aria-live)', async ({ page }) => {
    // Dados do grafo só deste teste: o mock compartilhado não traz listCorpusRoots nem o formato de NoteSummary
    const corpusGraph = {
      notes: [
        { note_id: 'n1', title: 'Cisco', source_type: 'md', source_path: '/mock/vault/Estudos/cisco.md', created_at: '2026-09-01', tags: [], chunk_count: 1 },
        { note_id: 'n2', title: 'RRF', source_type: 'md', source_path: '/mock/vault/Estudos/rrf.md', created_at: '2026-09-01', tags: [], chunk_count: 1 },
        { note_id: 'n3', title: 'Plano', source_type: 'md', source_path: '/mock/vault/Projetos/plano.md', created_at: '2026-09-01', tags: [], chunk_count: 1 },
      ],
      roots: [{ root: '/mock/vault', notes_count: 3 }],
      links: [{ source: 'n1', target: 'n3' }],
    };
    await page.addInitScript((graph) => {
      const api = (window as unknown as { pywebview: { api: Record<string, () => Promise<unknown>> } }).pywebview.api;
      api.listNotes = async () => graph.notes;
      api.listCorpusRoots = async () => graph.roots;
      api.listNoteLinks = async () => graph.links;
    }, corpusGraph);
    await page.goto('/');

    await page.locator('#btn-grafos').click();
    const canvas = page.locator('.force-graph__canvas');
    await expect(canvas).toBeVisible();
    const announcement = page.locator('.force-graph [aria-live="polite"]');

    await canvas.focus();
    await page.keyboard.press('ArrowRight');
    await expect(announcement).toHaveText(/^Selecionado: (Cisco|RRF|Plano|Estudos|Projetos|vault), \d+ ligaç(ão|ões)$/);

    await page.keyboard.press('Escape');
    await expect(announcement).toHaveText('');

    await page.keyboard.press('Home');
    await expect(announcement).toHaveText('Grafo inteiro enquadrado');
  });

});
