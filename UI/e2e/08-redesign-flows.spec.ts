import { test, expect, type Page } from '@playwright/test';

// Fluxos do redesenho no navegador, com o modo de navegador do app (bridge sem desktop).
// Regressão: desbloqueio do Avançado, presets, diagnóstico, Aparência ligada a "Reduzir animações" e a Fila que vira job.

const openSettings = async (page: Page, tab: string) => {
  await page.getByRole('button', { name: 'Configurações' }).first().click();
  await page.getByRole('navigation', { name: 'Categorias de configuração' }).getByRole('button', { name: tab, exact: true }).click();
};

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => window.localStorage.clear());
  await page.goto('/');
  await expect(page.getByRole('heading', { level: 1 })).toBeVisible();
});

test('Avançado: bloqueado explica, libera com confirmação e mostra presets e grupos', async ({ page }) => {
  await openSettings(page, 'Avançado');

  const mostrar = page.getByRole('button', { name: 'Mostrar ajustes avançados' });
  await expect(mostrar).toBeDisabled();
  await page.getByRole('checkbox', { name: /Entendo que estes ajustes/ }).check();
  await mostrar.click();

  await expect(page.getByRole('button', { name: 'Ocultar Avançado' })).toBeVisible({ timeout: 5000 });
  await expect(page.getByRole('heading', { name: /Presets/ })).toBeVisible();
  await expect(page.getByRole('region', { name: 'Busca', exact: true })).toBeVisible();

  await page.getByRole('button', { name: 'Ocultar Avançado' }).click();
  await expect(page.getByRole('button', { name: 'Mostrar ajustes avançados' })).toBeVisible();
});

test('Geral: Verificar de novo roda o diagnóstico e volta com o resultado', async ({ page }) => {
  await openSettings(page, 'Geral');
  const again = page.getByRole('button', { name: 'Verificar de novo' });
  await expect(again).toBeVisible();
  await again.click();
  await expect(page.getByRole('button', { name: 'Verificar de novo' })).toBeEnabled({ timeout: 5000 });
  await expect(page.getByRole('img', { name: /verificações ok/ })).toBeVisible();
});

test('Aparência: Reduzir animações vale no app inteiro e a prévia acompanha', async ({ page }) => {
  await openSettings(page, 'Aparência');

  const motion = page.getByRole('radiogroup', { name: 'Reduzir animações' });
  await motion.getByRole('radio', { name: 'Sempre' }).click();
  await expect(page.locator('html')).toHaveAttribute('data-motion', 'always');
  await expect(page.getByText('Animações desligadas em todo o app.')).toBeVisible();

  await page.getByRole('radiogroup', { name: 'Tamanho do texto' }).getByRole('radio', { name: '110%' }).click();
  await expect(page.locator('html')).toHaveAttribute('data-text-size', '110');
  await expect(page.getByLabel('Prévia da aparência')).toBeVisible();
});

test('Fila: sem job mostra a arte; Indexar vira o job com a lista Agora e Fechar volta', async ({ page }) => {
  await page.getByRole('button', { name: 'Fila', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Nada indexando agora' })).toBeVisible();

  await page.getByRole('textbox').filter({ hasText: '' }).first().fill('C:\\Users\\usuario\\Documents\\Vault (mock)');
  await page.getByRole('button', { name: 'Indexar', exact: true }).click();

  const job = page.getByRole('article', { name: 'Job atual' });
  await expect(job).toBeVisible({ timeout: 5000 });
  const feed = job.getByRole('region', { name: 'Arquivos processados agora' });
  await expect(feed.getByText('Redes\\OSPF.md')).toBeVisible();
  await expect(feed.getByText('6 trechos')).toBeVisible();

  // Regressão: o cartão encolhia na coluna da página (overflow hidden num item flex) e cortava a última fileira.
  await page.waitForTimeout(800);
  const card = await page.getByRole('region', { name: 'Indexação' }).boundingBox();
  const lastKpi = await job.getByText('Modo de commit').boundingBox();
  expect(card && lastKpi && lastKpi.y + lastKpi.height <= card.y + card.height).toBeTruthy();

  await expect(job.getByRole('button', { name: 'Fechar' })).toBeVisible({ timeout: 15000 });
  await job.getByRole('button', { name: 'Fechar' }).click();
  await expect(page.getByRole('heading', { name: 'Nada indexando agora' })).toBeVisible();
});

test('Benchmark vazio tem a arte e a explicação', async ({ page }) => {
  await page.getByRole('button', { name: 'Benchmark', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Nenhum benchmark executado nesta sessão.' })).toBeVisible();
  await expect(page.locator('.bench-art')).toBeVisible();
});

test('Fila: a área de soltar mostra os tipos aceitos (MP3, PDF, MD)', async ({ page }) => {
  await page.getByRole('button', { name: 'Fila', exact: true }).click();
  const drop = page.getByRole('region', { name: 'Área de arrastar e soltar arquivos' });
  for (const type of ['MP3', 'PDF', 'MD']) await expect(drop.getByText(type, { exact: true })).toBeVisible();
});

test('Fontes de IA: configuração manual com o provedor em cartões', async ({ page }) => {
  await openSettings(page, 'Fontes de IA');
  const providers = page.getByRole('radiogroup', { name: 'Provedor de resposta' });
  await expect(providers).toBeVisible();
  await providers.getByRole('radio').nth(1).click();
  await expect(providers.getByRole('radio').nth(1)).toHaveAttribute('aria-checked', 'true');
});

test('Notas: com o menu lateral aberto, os dados de cada trecho ficam dentro do painel', async ({ page }) => {
  // Regressão: o rótulo do trecho ficava fora da coluna de leitura e cortava com o menu aberto.
  await page.getByRole('button', { name: 'Expandir menu' }).click();
  await page.getByRole('button', { name: 'Notas', exact: true }).click();
  await page.getByRole('radio', { name: 'Trechos' }).click();

  const head = page.locator('.reader__chunk-head').first();
  await expect(head).toBeVisible();
  const box = await head.boundingBox();
  const pane = await page.locator('.nd__scroll').boundingBox();
  expect(box && pane && box.x >= pane.x && box.x + box.width <= pane.x + pane.width).toBeTruthy();
  await expect(page.getByRole('region', { name: 'Mapa dos trechos' })).toBeVisible();
});

test('Notas: recolher pasta esconde as notas, e a busca as traz de volta', async ({ page }) => {
  await page.getByRole('button', { name: 'Notas', exact: true }).click();
  const folder = page.getByRole('button', { name: /Estudos \/ Redes/ });
  await expect(page.getByRole('button', { name: /VLAN/ })).toBeVisible();

  await folder.click();
  await expect(folder).toHaveAttribute('aria-expanded', 'false');
  await expect(page.getByRole('button', { name: /VLAN/ })).toHaveCount(0);

  await page.getByRole('textbox', { name: 'Filtrar notas' }).fill('vlan');
  await expect(page.getByRole('button', { name: /VLAN/ })).toBeVisible();
});

test('Aparência: o emoji do título vira ícone do app, some ou volta ao original', async ({ page }) => {
  await page.getByRole('button', { name: 'Notas', exact: true }).click();
  await page.getByRole('textbox', { name: 'Filtrar notas' }).fill('saúde');
  const title = page.locator('.notes__item-title').first();
  await expect(title.locator('svg.note-icon')).toBeVisible();
  await expect(page.locator('.notes__group-name').first().locator('svg.note-icon')).toBeVisible();

  await openSettings(page, 'Aparência');
  const icons = page.getByRole('radiogroup', { name: 'Ícones nos títulos' });
  await expect(icons.getByRole('radio', { name: /Ícone do app/ })).toHaveAttribute('aria-checked', 'true');
  await icons.getByRole('radio', { name: /Sem ícone/ }).click();
  await expect(page.locator('html')).toHaveAttribute('data-note-icons', 'none');
  await expect(title).toHaveText('Saúde');
  await expect(title.locator('svg')).toHaveCount(0);

  await icons.getByRole('radio', { name: /Emoji original/ }).click();
  await expect(title).toHaveText('❤️ Saúde');
});

test('Avançado: a arte da Busca mostra lexical, vetorial e híbrida, com a estratégia escolhida em destaque', async ({ page }) => {
  await openSettings(page, 'Avançado');
  await page.getByRole('checkbox', { name: /Entendo que estes ajustes/ }).check();
  await page.getByRole('button', { name: 'Mostrar ajustes avançados' }).click();

  const kinds = page.locator('.adv-search__kind');
  await expect(kinds).toHaveText(['Lexical', 'Vetorial', 'Híbrida'], { timeout: 5000 });
  await expect(page.locator('.adv-search__kind.is-on')).toHaveText('Híbrida');
});

test('Tema: a arte da Fila e o grafo seguem a cor de destaque, não a da vault', async ({ page }) => {
  await page.getByRole('button', { name: 'Abrir painel de grafos' }).click();
  await page.getByRole('button', { name: 'Fila', exact: true }).click();
  const art = page.locator('.queue-empty__art');
  await expect(art).toBeVisible();
  // O canvas só monta depois que a lista de notas carrega.
  await expect(page.locator('.graph-panel canvas')).toBeVisible();

  const colors = await page.evaluate(() => {
    const accent = getComputedStyle(document.documentElement).getPropertyValue('--accent-blue-light').trim();
    // O grafo lê a paleta do próprio canvas (readPalette).
    const panel = document.querySelector('.graph-panel canvas') as Element;
    const probe = document.createElement('span');
    probe.style.color = accent;
    document.body.append(probe);
    const expected = getComputedStyle(probe).color;
    probe.remove();
    return {
      expected,
      art: getComputedStyle(document.querySelector('.queue-empty__art') as Element).color,
      graphAccent: getComputedStyle(panel).getPropertyValue('--ag-accent').trim(),
      accent,
    };
  });
  expect(colors.art).toBe(colors.expected);
  expect(colors.graphAccent).toBe(colors.accent);
});

test('Voz: Testar microfone ouve e responde', async ({ page }) => {
  await openSettings(page, 'Voz');
  await page.getByRole('button', { name: 'Testar', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Ouvindo…' })).toBeVisible();
  await expect(page.locator('.mic-test__msg')).toBeVisible({ timeout: 8000 });
});

test('Chat com IA: a espera mostra as etapas reais e a resposta descartada mostra motivo, detalhes e Copiar', async ({ page }) => {
  await page.context().grantPermissions(['clipboard-read', 'clipboard-write']);
  await page.getByRole('button', { name: /^Como responder/ }).click();
  await page.getByRole('button', { name: /qwen2\.5:3b/ }).click();
  const input = page.locator('textarea').first();

  // Modo navegador: pergunta com "descart" volta com a IA descartada (unsupported_anchor).
  await input.fill('Por que a IA foi descartada aqui?');
  await input.press('Enter');
  const waiting = page.getByRole('status', { name: 'Buscando no vault' });
  await expect(waiting).toBeVisible();
  await expect(waiting.getByText('Escrever com qwen2.5:3b')).toBeVisible();

  const notice = page.getByRole('region', { name: 'Por que a IA foi descartada' });
  await expect(notice).toContainText('A IA citou algo que não está nos trechos', { timeout: 8000 });
  await expect(page.getByText('IA descartada · mostramos o trecho')).toBeVisible();
  await notice.getByText('Detalhes técnicos').click();
  await expect(notice.getByText('unsupported_anchor')).toBeVisible();
  await expect(page.getByRole('region', { name: 'Limitação' })).toContainText('único trecho');
  await page.getByRole('button', { name: 'Copiar resposta com as fontes' }).last().click();
  await expect(page.getByText('Copiado')).toBeVisible();

  // Sem "descart": a IA escreve o rascunho e a resposta sai assinada por ela.
  await input.fill('Como a reindexação decide se uma nota mudou?');
  await input.press('Enter');
  await expect(page.getByText('Escrevendo com qwen2.5:3b…')).toBeVisible({ timeout: 8000 });
  await expect(page.getByText('rascunho, ainda sendo validado')).toBeVisible();
  await expect(page.getByText('Escrita pela IA · qwen2.5:3b')).toBeVisible({ timeout: 8000 });
});

test('Grafo: enquanto carrega nunca diz que a vault está vazia', async ({ page }) => {
  // Regressão: o painel mostrava "Nenhuma nota indexada" até a lista de notas chegar.
  await page.evaluate(() => {
    const w = window as unknown as { sawEmpty: boolean };
    w.sawEmpty = false;
    new MutationObserver(() => {
      if (document.body.textContent?.includes('Nenhuma nota indexada nesta vault')) w.sawEmpty = true;
    }).observe(document.body, { childList: true, subtree: true });
  });
  await page.getByRole('button', { name: 'Abrir painel de grafos' }).click();
  await expect(page.locator('.graph-panel canvas')).toBeVisible();
  expect(await page.evaluate(() => (window as unknown as { sawEmpty: boolean }).sawEmpty)).toBe(false);
});

test('Notas: o primeiro carregamento mostra o esqueleto na lista e na leitura, e o dado troca no lugar', async ({ page }) => {
  await page.getByRole('button', { name: 'Notas', exact: true }).click();
  await expect(page.locator('.notes__items .skeleton-box').first()).toBeAttached();
  await expect(page.getByRole('status', { name: 'Abrindo nota' })).toBeAttached();
  await expect(page.locator('.reader__title')).toBeVisible();
  await expect(page.locator('.notes .skeleton-box')).toHaveCount(0);
});

test('Configurações: o Diagnóstico abre com o esqueleto e depois mostra as verificações', async ({ page }) => {
  await openSettings(page, 'Geral');
  await expect(page.locator('.doctor__summary')).toBeVisible({ timeout: 8000 });
  await expect(page.getByRole('status', { name: 'Carregando diagnóstico' })).toHaveCount(0);
});
