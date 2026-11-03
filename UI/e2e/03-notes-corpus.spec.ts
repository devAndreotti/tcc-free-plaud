import { test, expect } from '@playwright/test';
import { createPyWebViewMockScript } from './fixtures/pywebview-bridge-mock';

test.describe('Notes & Corpus Exploration E2E Flow', () => {
  test.beforeEach(async ({ page }) => {
    await page.addInitScript(createPyWebViewMockScript());
    // O getNoteDetail do mock compartilhado não tem o formato de NoteDetail (sem note_id nem trechos): aqui a nota abre inteira.
    await page.addInitScript(() => {
      const api = (window as unknown as { pywebview: { api: Record<string, (...args: never[]) => Promise<unknown>> } }).pywebview.api;
      api.getNoteDetail = async (noteId: unknown) => {
        const notes = (await api.listNotes()) as Array<{ note_id: string; title: string }>;
        const note = notes.find((item) => item.note_id === noteId) ?? notes[0];
        return {
          ...note,
          source_type: 'md',
          source_path: `/mock/vault/${note.title}.md`,
          created_at: '2026-09-08T00:00:00Z',
          tags: [],
          chunk_count: 1,
          structured_markdown: `# ${note.title}\n\nCorpo da nota ${note.title}.`,
          chunks: [{ chunk_id: `${note.note_id}::v1::ofs-0-40`, chunk_index: 1, char_start: 0, char_end: 40, token_count: 9, snippet: `Corpo da nota ${note.title}.` }],
        };
      };
    });
    await page.goto('/');
  });

  test('lista as notas indexadas, abre a escolhida e o filtro esconde as outras', async ({ page }) => {
    // Botão exato do menu principal: `has-text("Notas")` casava antes com o botão da vault ("42 notas")
    await page.getByRole('navigation', { name: 'Navegação principal' }).getByRole('button', { name: 'Notas', exact: true }).click();

    const arquitetura = page.getByRole('button', { name: /Arquitetura do Escólio/ });
    const rrf = page.getByRole('button', { name: /Decisões de RRF/ });
    await expect(arquitetura).toBeVisible();
    await expect(rrf).toBeVisible();
    await expect(page.getByText('2 no corpus')).toBeVisible();

    await rrf.click();
    await expect(page.locator('.reader__title')).toHaveText('Decisões de RRF');

    await page.getByRole('textbox', { name: 'Filtrar notas' }).fill('rrf');
    await expect(page.getByText('1 encontrada')).toBeVisible();
    await expect(arquitetura).toHaveCount(0);
    await expect(rrf).toBeVisible();

    await page.getByRole('textbox', { name: 'Filtrar notas' }).fill('nada-disso-existe');
    await expect(page.getByText('Nenhuma nota com esse filtro.')).toBeVisible();
  });
});
