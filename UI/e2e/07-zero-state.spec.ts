import { test, expect } from '@playwright/test';

test.describe('Zero State E2E Flow', () => {
  test('corpus vazio: a pergunta volta como "Sem resposta" e as notas e o grafo mostram o estado vazio', async ({ page }) => {
    // Ponte no formato real do backend com o corpus vazio (askCorpus devolve AskResult com empty_corpus).
    await page.addInitScript(() => {
      window.localStorage.clear();
      const w = window as unknown as { pywebview: unknown };
      w.pywebview = {
        api: {
          loadVaultPath: async () => null,
          listNotes: async () => [],
          getBackendSettings: async () => ({}),
          getDoctor: async () => ({ status: 'ok', checks: [] }),
          listSettingsPresets: async () => [],
          askCorpus: async (query: string) => ({
            query,
            status: 'no_answer',
            no_answer: true,
            answer: null,
            claims: [],
            citations: [],
            limitations: [],
            reason_for_no_answer: 'empty_corpus',
            latency_ms: 3,
          }),
        },
      };
    });
    await page.goto('/');

    const input = page.locator('textarea').first();
    await input.fill('Pergunta sem corpus');
    await input.press('Enter');

    const answer = page.getByRole('article', { name: 'Resposta' });
    await expect(answer.getByText('Sem resposta', { exact: true })).toBeVisible({ timeout: 10000 });
    await expect(answer.getByRole('heading', { name: 'O corpus ainda está vazio.' })).toBeVisible();
    await expect(answer.getByText('Indexe a pasta do vault na Fila')).toBeVisible();
    // Sem nada indexado, buscar só por palavra-chave não ajudaria: o botão não é oferecido.
    await expect(answer.getByRole('button', { name: 'Buscar só por palavra-chave' })).toHaveCount(0);

    await page.getByRole('button', { name: 'Notas', exact: true }).click();
    await expect(page.getByText('Nenhuma nota indexada ainda. Indexe uma pasta na Fila.')).toBeVisible();

    await page.getByRole('button', { name: 'Abrir painel de grafos' }).click();
    await expect(page.getByText('Nenhuma nota indexada nesta vault. Indexe uma pasta na Fila.')).toBeVisible();
  });
});
