import { test, expect, type Page } from '@playwright/test';
import { createPyWebViewMockScript } from './fixtures/pywebview-bridge-mock';

// Telas do canvas "Telas novas": sem chats (vaults, busca, recentes, Ctrl+T) e o grafo de todas as vaults.

const ask = async (page: Page, question: string) => {
  const input = page.locator('textarea, input[type="text"]').first();
  await input.fill(question);
  await input.press('Enter');
  await expect(page.getByText('Recuperação híbrida via BM25 e ChromaDB.')).toBeVisible({ timeout: 10000 });
};

const closeAllTabs = async (page: Page) => {
  const close = page.getByRole('button', { name: /^Fechar aba / });
  while ((await close.count()) > 0) await close.first().click();
};

test.describe('Tela sem chats', () => {
  test.beforeEach(async ({ page }) => {
    await page.addInitScript(createPyWebViewMockScript());
    await page.goto('/');
  });

  test('fechar todas as abas mostra as vaults, a busca, a conversa recente e o Ctrl+T', async ({ page }) => {
    await ask(page, 'Como funciona o pipeline?');
    await closeAllTabs(page);

    await expect(page.getByRole('heading', { name: 'Você fechou todos os chats' })).toBeVisible();
    // Com poucas vaults não há busca: os cards já cabem na tela.
    await expect(page.getByRole('list', { name: 'Vaults' }).getByRole('button')).toHaveCount(2);
    await expect(page.getByLabel('Buscar vault')).toHaveCount(0);

    // Reabrir a conversa recente traz as mensagens de volta.
    await page.getByRole('region', { name: 'Conversas recentes' }).getByRole('button').first().click();
    await expect(page.getByRole('article', { name: 'Sua pergunta' })).toContainText('Como funciona o pipeline?');

    await closeAllTabs(page);
    await page.keyboard.press('Control+t');
    await expect(page.getByRole('tablist', { name: 'Abas abertas' }).getByRole('tab')).toHaveCount(1);
    await expect(page.getByRole('heading', { name: 'Você fechou todos os chats' })).toBeHidden();
  });

  test('a partir de 7 vaults aparece a busca, que filtra pelo nome', async ({ page }) => {
    await page.addInitScript(() => {
      const api = (window as unknown as { pywebview: { api: Record<string, unknown> } }).pywebview.api;
      const names = ['Obsidian', 'Culinária', 'Trabalho', 'Faculdade', 'Viagens', 'Leituras', 'Finanças', 'Música'];
      api.listVaults = async () => ({
        active: 'v0',
        vaults: names.map((name, i) => ({ id: `v${i}`, name, icon: 'notes', color: 'violet', folders: [], embedding_model: 'chroma-default', created_at: '2026-10-18T12:00:00-03:00', sqlite_path: null, vector_store_dir: null, note_count: i + 1, roots: [] })),
      });
    });
    await page.goto('/');
    await closeAllTabs(page);

    const vaults = page.getByRole('list', { name: 'Vaults' });
    await expect(vaults.getByRole('button')).toHaveCount(8);
    await page.getByLabel('Buscar vault').fill('culin');
    await expect(vaults.getByRole('button')).toHaveCount(1);
    await expect(vaults).toContainText('Culinária');
    await page.getByLabel('Buscar vault').fill('zzz');
    await expect(page.getByText('Nenhuma vault com esse nome.')).toBeVisible();
  });

  test('clicar numa vault abre uma conversa nela', async ({ page }) => {
    await closeAllTabs(page);
    await page.getByRole('list', { name: 'Vaults' }).getByRole('button', { name: /Culinária/ }).click();
    await expect(page.getByRole('tablist', { name: 'Abas abertas' }).getByRole('tab')).toHaveCount(1);
  });
});

test.describe('Grafo de todas as vaults', () => {
  test.beforeEach(async ({ page }) => {
    await page.addInitScript(createPyWebViewMockScript());
    await page.goto('/');
    await page.getByRole('button', { name: 'Abrir painel de grafos' }).click();
    await page.getByRole('group', { name: 'Quais vaults o grafo mostra' }).getByRole('button', { name: 'Todas as vaults' }).click();
  });

  // Distância entre a ponta da linha no SVG e o centro do botão da vault por cima dele.
  const nodeOffset = (page: Page) => page.evaluate(() => {
    const line = document.querySelector('.overview__spoke') as SVGLineElement;
    const point = new DOMPoint(line.x2.baseVal.value, line.y2.baseVal.value).matrixTransform(line.getScreenCTM()!);
    const box = document.querySelector('.overview__node')!.getBoundingClientRect();
    return Math.hypot(point.x - (box.left + box.width / 2), point.y - (box.top + box.height / 2));
  });

  test('no painel estreito o botão da vault fica em cima do desenho, e a escolha fica lembrada', async ({ page }) => {
    await expect(page.getByRole('button', { name: /^Vault de exemplo: 3 notas/ })).toBeVisible();
    expect(await nodeOffset(page)).toBeLessThan(3);

    await page.reload();
    await page.getByRole('button', { name: 'Abrir painel de grafos' }).click();
    await expect(page.getByRole('button', { name: 'Todas as vaults' })).toHaveAttribute('aria-pressed', 'true');
  });

  test('tela cheia cobre a janela, busca em todas as vaults e sai com Esc', async ({ page }) => {
    await page.getByRole('button', { name: 'Abrir em tela cheia' }).click();
    const dialog = page.getByRole('dialog', { name: 'Grafo de todas as vaults' });
    await expect(dialog).toBeVisible();
    const box = await dialog.boundingBox();
    const viewport = page.viewportSize()!;
    expect(box).toMatchObject({ x: 0, y: 0, width: viewport.width, height: viewport.height });
    expect(await nodeOffset(page)).toBeLessThan(3);

    await dialog.getByRole('button', { name: /^Vault de exemplo/ }).click();
    await expect(dialog.getByRole('complementary', { name: 'Detalhes' })).toContainText('Estudos');

    await dialog.getByLabel('Buscar em todas as vaults').fill('vlan');
    await expect(dialog.getByRole('complementary', { name: 'Detalhes' })).toContainText('1 resultado');
    await expect(dialog.getByRole('button', { name: /VLAN/ })).toBeVisible();

    await page.keyboard.press('Escape');
    await expect(dialog).toBeHidden();
  });

  test('tela cheia: scroll aproxima no mouse, arrastar move e duplo clique volta ao desenho inteiro', async ({ page }) => {
    await page.getByRole('button', { name: 'Abrir em tela cheia' }).click();
    const dialog = page.getByRole('dialog', { name: 'Grafo de todas as vaults' });
    const body = dialog.locator('.overview__body');
    const stage = dialog.locator('.overview__stage');
    const box = (await body.boundingBox())!;
    await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
    await page.mouse.wheel(0, -400);
    await expect(body).toHaveClass(/is-zoomed/);
    const zoomed = await stage.evaluate((el) => el.style.transform);
    expect(zoomed).toMatch(/scale\(/);
    expect(await nodeOffset(page)).toBeLessThan(3); // desenho e botões aproximam juntos

    // Arrastar no vazio move o desenho; soltar não abre nada embaixo do mouse.
    await page.mouse.move(box.x + 30, box.y + 30);
    await page.mouse.down();
    await page.mouse.move(box.x + 130, box.y + 80, { steps: 5 });
    await page.mouse.up();
    expect(await stage.evaluate((el) => el.style.transform)).not.toBe(zoomed);
    await expect(dialog).toBeVisible();

    await body.dblclick({ position: { x: 30, y: 30 } });
    await expect(body).not.toHaveClass(/is-zoomed/);
  });
});

test.describe('Grafo da vault: arrastar um nó', () => {
  test('o nó segue o mouse com o cursor de agarrar, e a câmera fica parada', async ({ page }) => {
    const graph = {
      notes: [
        { note_id: 'n1', title: 'Cisco', source_type: 'md', source_path: '/mock/vault/Estudos/cisco.md', created_at: '2026-09-01', tags: [], chunk_count: 1 },
        { note_id: 'n2', title: 'RRF', source_type: 'md', source_path: '/mock/vault/Estudos/rrf.md', created_at: '2026-09-01', tags: [], chunk_count: 1 },
        { note_id: 'n3', title: 'Plano', source_type: 'md', source_path: '/mock/vault/Projetos/plano.md', created_at: '2026-09-01', tags: [], chunk_count: 1 },
      ],
      roots: [{ root: '/mock/vault', notes_count: 3 }],
    };
    await page.addInitScript(createPyWebViewMockScript());
    await page.addInitScript((g) => {
      const api = (window as unknown as { pywebview: { api: Record<string, () => Promise<unknown>> } }).pywebview.api;
      api.listNotes = async () => g.notes;
      api.listCorpusRoots = async () => g.roots;
      api.listNoteLinks = async () => [];
    }, graph);
    await page.goto('/');
    await page.locator('#btn-grafos').click();
    const canvas = page.locator('.force-graph__canvas');
    await expect(canvas).toBeVisible();
    await page.waitForTimeout(800); // a simulação assenta (são 300 passos)

    // Acha um nó varrendo o canvas: em cima de um nó o cursor vira a mãozinha.
    const box = (await canvas.boundingBox())!;
    const cursor = () => canvas.evaluate((el) => (el as HTMLCanvasElement).style.cursor);
    let hit: { x: number; y: number } | null = null;
    for (let y = box.y + 10; y < box.y + box.height - 10 && !hit; y += 7) {
      for (let x = box.x + 10; x < box.x + box.width - 10 && !hit; x += 7) {
        await page.mouse.move(x, y);
        if ((await cursor()) === 'pointer') hit = { x, y };
      }
    }
    expect(hit).not.toBeNull();
    const from = hit!;
    const to = { x: Math.min(box.x + box.width - 20, from.x + 70), y: Math.min(box.y + box.height - 20, from.y + 60) };

    await page.mouse.down();
    await page.mouse.move(to.x, to.y, { steps: 8 });
    expect(await cursor()).toBe('grabbing');
    await page.mouse.up();
    // Soltou: sai do modo de arrastar e o grafo continua na tela (soltar não é clique, não abre a nota).
    expect(await cursor()).not.toBe('grabbing');
    await expect(canvas).toBeVisible();
  });
});
