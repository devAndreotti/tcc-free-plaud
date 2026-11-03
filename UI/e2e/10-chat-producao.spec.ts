import { test, expect, type Page } from '@playwright/test';
import { createPyWebViewMockScript } from './fixtures/pywebview-bridge-mock';

// Caminho de produção do chat: dentro do desktop o App chama bridge.askCorpus, ou bridge.startAsk + pollAsk
// quando o backend responde em streaming. Aqui a ponte simulada devolve o AskResult no formato real
// (claims, citations, limitations), em vez do texto puro do sendMessage dos outros mocks.

type Mode = 'askCorpus' | 'startAsk';
const MODES: Mode[] = ['askCorpus', 'startAsk'];

const SNIPPET_1 = 'O id de um trecho junta o id da nota, a versão e o deslocamento no texto.';
const SNIPPET_2 = 'Se o hash não mudou desde a última indexação, a nota entra como inalterada.';
const XSS = (n: number) => `<img src=x onerror="window.xss=${n};alert(${n})">`;

interface Scenario {
  kind: 'answer' | 'no_answer' | 'xss';
  mode: Mode;
}

// Roda dentro da página: monta a ponte por cima do mock base e anota as chamadas em window.__calls.
const installBridge = ({ kind, mode }: Scenario) => {
  const cite = (chunk_id: string, snippet: string, char_start: number, char_end: number) => ({
    note_id: 'arquitetura--3f9a1c',
    note_version: 1,
    chunk_id,
    snippet,
    source_path: '/mock/vault/Projetos/Arquitetura do índice.md',
    char_start,
    char_end,
  });
  const xss = (n: number) => `<img src=x onerror="window.xss=${n};alert(${n})">`;
  const direct = cite('arquitetura--3f9a1c::v1::ofs-000680-001480::9a41', kind === 'xss' ? xss(2) : 'O id de um trecho junta o id da nota, a versão e o deslocamento no texto.', 680, 1480);
  const partial = cite('arquitetura--3f9a1c::v1::ofs-001360-002160::77c0', 'Se o hash não mudou desde a última indexação, a nota entra como inalterada.', 1360, 2160);

  const noAnswer = {
    query: '',
    status: 'no_answer',
    no_answer: true,
    answer: null,
    claims: [],
    citations: [],
    limitations: ['Nenhum trecho recuperado responde à pergunta com segurança.'],
    reason_for_no_answer: 'no_retrieval_hits',
    latency_ms: 12,
    strategy: 'hybrid',
    top_k: 5,
  };
  const answered = {
    query: '',
    status: 'answer',
    no_answer: false,
    answer: null,
    claims: [
      { text: kind === 'xss' ? `O id do trecho. ${xss(1)} <script>window.xss=9</script>` : 'O id de um trecho junta nota, versão e deslocamento.', citations: [direct], support_level: 'direct' },
      { text: 'A nota sem mudança de hash fica inalterada.', citations: [partial], support_level: 'partial' },
    ],
    citations: [direct, partial],
    limitations: [kind === 'xss' ? `Só um trecho apoia. ${xss(3)}` : 'Só dois trechos apoiam esta resposta.'],
    reason_for_no_answer: null,
    latency_ms: 42,
    strategy: 'hybrid',
    top_k: 5,
    answer_provider: 'extractive',
    generated: false,
  };
  const result = (query: string) => ({ ...(kind === 'no_answer' ? noAnswer : answered), query });

  const w = window as unknown as {
    __calls: string[];
    __release: boolean;
    pywebview: { api: Record<string, (...args: never[]) => Promise<unknown>> };
  };
  w.__calls = [];
  w.__release = false;
  const api = w.pywebview.api;

  const noteSummary = {
    note_id: 'arquitetura--3f9a1c',
    title: 'Arquitetura do índice',
    source_type: 'md',
    source_path: '/mock/vault/Projetos/Arquitetura do índice.md',
    created_at: '2026-09-08T00:00:00Z',
    tags: [],
    chunk_count: 2,
  };
  api.listNotes = async () => [noteSummary];
  api.getNoteDetail = async () => ({
    ...noteSummary,
    structured_markdown: '# Arquitetura do índice\n\nTexto da nota.',
    chunks: [
      { chunk_id: direct.chunk_id, chunk_index: 1, char_start: 680, char_end: 1480, token_count: 120, snippet: direct.snippet },
      { chunk_id: partial.chunk_id, chunk_index: 2, char_start: 1360, char_end: 2160, token_count: 118, snippet: partial.snippet },
    ],
  });

  if (mode === 'askCorpus') {
    // Sem startAsk na ponte, o App cai em askCorpus (bridge.supportsAskStreaming = false).
    delete (api as Record<string, unknown>).startAsk;
    api.askCorpus = (async (query: string) => {
      w.__calls.push('askCorpus');
      return result(query);
    }) as never;
    return;
  }

  const queries = new Map<string, { query: string; polls: number }>();
  api.startAsk = (async (query: string) => {
    w.__calls.push('startAsk');
    const id = `ask-${queries.size + 1}`;
    queries.set(id, { query, polls: 0 });
    return { ask_id: id };
  }) as never;
  api.askCorpus = (async () => {
    w.__calls.push('askCorpus');
    throw new Error('askCorpus não deveria ser chamado com streaming');
  }) as never;
  // 1º poll: buscando; depois escrevendo, até o teste liberar; então a resposta final.
  api.pollAsk = (async (askId: string) => {
    w.__calls.push('pollAsk');
    const ask = queries.get(askId);
    if (!ask) return { ask_id: askId, stage: 'error', partial: '', result: null, error: 'Pergunta não encontrada.' };
    ask.polls += 1;
    if (ask.polls === 1) return { ask_id: askId, stage: 'retrieving', partial: '', result: null, error: null };
    if (!w.__release) return { ask_id: askId, stage: 'writing', partial: 'Rascunho parcial da resposta', result: null, error: null };
    return { ask_id: askId, stage: 'done', partial: '', result: result(ask.query), error: null };
  }) as never;
};

const openChat = async (page: Page, scenario: Scenario) => {
  const dialogs: string[] = [];
  page.on('dialog', async (dialog) => {
    dialogs.push(dialog.message());
    await dialog.dismiss();
  });
  await page.addInitScript(createPyWebViewMockScript());
  await page.addInitScript(installBridge, scenario);
  await page.goto('/');
  return dialogs;
};

const ask = async (page: Page, question: string) => {
  const input = page.locator('textarea').first();
  await input.fill(question);
  await input.press('Enter');
};

const calls = (page: Page) => page.evaluate(() => (window as unknown as { __calls: string[] }).__calls);

for (const mode of MODES) {
  test.describe(`Chat de produção via ${mode}`, () => {
    test('resposta com claims e citações: marcador, fonte visível e clique abre a nota no trecho citado', async ({ page }) => {
      await openChat(page, { kind: 'answer', mode });
      await ask(page, 'Como o id de um trecho é montado?');

      const answer = page.getByRole('article', { name: 'Resposta' });
      if (mode === 'startAsk') {
        // Enquanto o backend escreve, a tela mostra o rascunho e depois troca pela resposta validada.
        await expect(page.getByRole('status', { name: /Escrevendo/ })).toBeVisible({ timeout: 8000 });
        await expect(page.getByText('Rascunho parcial da resposta')).toBeVisible();
        await page.evaluate(() => { (window as unknown as { __release: boolean }).__release = true; });
      }

      await expect(answer.getByText('O id de um trecho junta nota, versão e deslocamento.')).toBeVisible({ timeout: 8000 });
      await expect(answer.getByText('A nota sem mudança de hash fica inalterada.')).toBeVisible();
      // Marcadores: um por afirmação, o segundo de apoio parcial.
      await expect(answer.getByRole('button', { name: 'Fonte 1', exact: true })).toBeVisible();
      await expect(answer.getByRole('button', { name: 'Fonte 2, apoio parcial' })).toBeVisible();
      // Fontes com a citação, o intervalo e o tipo de apoio.
      const sources = answer.getByRole('list', { name: 'Fontes' }).getByRole('listitem');
      await expect(sources).toHaveCount(2);
      await expect(sources.nth(0)).toContainText(SNIPPET_1);
      await expect(sources.nth(0)).toContainText('680–1480');
      await expect(sources.nth(0)).toContainText('apoio direto');
      await expect(sources.nth(1)).toContainText(SNIPPET_2);
      await expect(sources.nth(1)).toContainText('apoio parcial');
      await expect(answer.getByRole('region', { name: 'Limitação' })).toContainText('Só dois trechos apoiam esta resposta.');
      await expect(answer.getByText('Só trechos · sem IA')).toBeVisible();

      expect(await calls(page)).toContain(mode);
      if (mode === 'askCorpus') expect(await calls(page)).not.toContain('startAsk');
      else expect(await calls(page)).not.toContain('askCorpus');

      // Clique na fonte: abre a nota, em Trechos, com o trecho citado destacado e o outro não.
      await answer.getByRole('button', { name: 'Abrir Arquitetura do índice no trecho citado' }).first().click();
      await expect(page.locator('.reader__title')).toHaveText('Arquitetura do índice');
      const cited = page.locator('.reader__chunk--cited');
      await expect(cited).toHaveCount(1);
      await expect(cited).toContainText(SNIPPET_1);
      await expect(cited).toContainText('trecho citado');
      await expect(page.locator('.reader__chunk').filter({ hasText: SNIPPET_2 })).not.toHaveClass(/reader__chunk--cited/);
    });

    test('no_answer: mostra "Sem resposta" com o motivo e sem fontes', async ({ page }) => {
      await openChat(page, { kind: 'no_answer', mode });
      await ask(page, 'Pergunta que o vault não responde');
      if (mode === 'startAsk') {
        await expect(page.getByRole('status', { name: /Escrevendo/ })).toBeVisible({ timeout: 8000 });
        await page.evaluate(() => { (window as unknown as { __release: boolean }).__release = true; });
      }

      const answer = page.getByRole('article', { name: 'Resposta' });
      await expect(answer.getByText('Sem resposta', { exact: true })).toBeVisible({ timeout: 8000 });
      await expect(answer.getByRole('heading', { name: 'Não encontrei isso no vault.' })).toBeVisible();
      await expect(answer.getByText('Nenhum trecho recuperado responde à pergunta com segurança.')).toBeVisible();
      await answer.getByText('Detalhes técnicos').click();
      await expect(answer.getByText('motivo: no_retrieval_hits')).toBeVisible();
      await expect(answer.getByRole('list', { name: 'Fontes' })).toHaveCount(0);
      expect(await calls(page)).toContain(mode);
    });

    test('XSS em claims, trecho citado e limitações: aparece como texto e nada executa', async ({ page }) => {
      const dialogs = await openChat(page, { kind: 'xss', mode });
      await ask(page, 'Pergunta com resposta maliciosa');
      if (mode === 'startAsk') {
        await expect(page.getByRole('status', { name: /Escrevendo/ })).toBeVisible({ timeout: 8000 });
        await page.evaluate(() => { (window as unknown as { __release: boolean }).__release = true; });
      }

      const answer = page.getByRole('article', { name: 'Resposta' });
      await expect(answer.getByRole('list', { name: 'Fontes' })).toBeVisible({ timeout: 8000 });
      // Cada campo mostra a tag escrita, literalmente.
      await expect(answer.locator('.msg__claim').first()).toContainText(XSS(1));
      await expect(answer.locator('.msg__claim').first()).toContainText('<script>window.xss=9</script>');
      await expect(answer.locator('.msg__source-quote').first()).toHaveText(XSS(2));
      await expect(answer.getByRole('region', { name: 'Limitação' })).toContainText(XSS(3));

      await expect(page.locator('.msg img')).toHaveCount(0);
      await expect(page.locator('[onerror]')).toHaveCount(0);
      // Um onerror de imagem inserida dispararia em instantes; esta é a única espera por tempo.
      await page.waitForTimeout(1500);
      expect(await page.evaluate(() => (window as unknown as { xss?: unknown }).xss)).toBeUndefined();
      expect(dialogs).toEqual([]);
    });
  });
}
