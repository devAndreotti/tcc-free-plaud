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
    // Com movimento reduzido o grafo já aparece assentado: o nó achado na varredura continua no lugar quando o mouse desce.
    await page.emulateMedia({ reducedMotion: 'reduce' });
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
    await page.waitForTimeout(300);

    // Acha um nó varrendo o canvas dentro da página (uma chamada por ponto estoura o tempo em máquina lenta):
    // em cima de um nó o cursor vira a mãozinha.
    const box = (await canvas.boundingBox())!;
    const cursor = () => canvas.evaluate((el) => (el as HTMLCanvasElement).style.cursor);
    const scan = () => canvas.evaluate((el) => {
      const c = el as HTMLCanvasElement;
      const r = c.getBoundingClientRect();
      for (let y = r.top + 10; y < r.bottom - 10; y += 5) {
        for (let x = r.left + 10; x < r.right - 10; x += 5) {
          c.dispatchEvent(new MouseEvent('mousemove', { clientX: x, clientY: y, bubbles: true }));
          if (c.style.cursor === 'pointer') return { x, y };
        }
      }
      return null;
    });
    // Repete até o mouse de verdade confirmar o nó: os lotes da simulação ainda podem estar assentando.
    let from = { x: 0, y: 0 };
    await expect(async () => {
      const hit = await scan();
      expect(hit).not.toBeNull();
      from = hit!;
      await page.mouse.move(from.x, from.y);
      await page.waitForTimeout(200);
      await page.mouse.move(from.x, from.y + 0.5);
      expect(await cursor()).toBe('pointer');
    }).toPass({ timeout: 15000 });
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

// Clique de verdade: o Playwright só clica se o item for o que está por cima naquele ponto.
// Com o cabeçalho cortando o que passa dos 40 px, o menu ficava invisível e o clique caía no chat.
test.describe('Exportar conversa', () => {
  test.beforeEach(async ({ page }) => {
    await page.addInitScript(createPyWebViewMockScript());
    await page.goto('/');
    await ask(page, 'Como funciona o pipeline?');
  });

  test('o menu aparece por cima do chat e o PDF abre a impressão só com a conversa', async ({ page }) => {
    await page.evaluate(() => {
      const state = { title: '', text: '' };
      (window as unknown as { __print: typeof state }).__print = state;
      window.print = () => {
        state.title = document.title;
        state.text = document.querySelector('.print-root')?.textContent ?? '';
      };
    });
    await page.getByRole('button', { name: 'Exportar conversa' }).click();
    const menu = page.getByRole('group', { name: 'Formato da exportação' });
    await expect(menu).toBeVisible();
    await menu.getByRole('button', { name: /^PDF/ }).click();
    const printed = await page.evaluate(() => (window as unknown as { __print: { title: string; text: string } }).__print);
    expect(printed.title).toBe('Como funciona o pipeline-');
    expect(printed.text).toContain('Como funciona o pipeline?');
  });

  test('com muitas abas o cabeçalho não estoura a janela e o menu segue clicável', async ({ page }) => {
    for (let i = 0; i < 14; i += 1) await page.locator('#btn-new-tab').click();
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
    expect(overflow).toBeLessThanOrEqual(0);
    await page.getByRole('tablist', { name: 'Abas abertas' }).getByRole('tab').first().click();
    await page.getByRole('button', { name: 'Exportar conversa' }).click();
    await expect(page.getByRole('group', { name: 'Formato da exportação' }).getByRole('button', { name: /^JSON/ })).toBeVisible();
  });
});

test('Benchmark: o campo da suíte tem largura de verdade com o interruptor da IA na tela', async ({ page }) => {
  await page.addInitScript(createPyWebViewMockScript());
  await page.goto('/');
  await page.getByRole('button', { name: 'Benchmark', exact: true }).click();
  await expect(page.getByRole('checkbox', { name: /Medir também a resposta da IA/ })).toHaveCount(1);
  const field = page.locator('#benchmark-suite-path');
  await expect(field).toBeVisible();
  expect((await field.boundingBox())!.width).toBeGreaterThan(200);
});
