import { cleanup, render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';
import type { NoteDetail } from '../services/bridge';
import { NoteDetailView } from './NoteDetailView';

// Formato que o backend grava: frontmatter interno, Summary, Normalized Text (a nota) e Raw Text.
const markdown = [
  '---',
  'note_id: ata--abc',
  '---',
  '## Summary',
  'Resumo que não aparece na leitura.',
  '## Normalized Text',
  '---',
  'title: Ata do comitê',
  'tags: [kafka, adr]',
  'vazio:',
  '---',
  '# Ata do comitê',
  'Decisão sobre o **message broker** da `plataforma`.',
  'Continua no mesmo parágrafo.',
  '',
  '## Decisões',
  '- Adotar Kafka',
  '- Registrar ADR',
  '1. Runbook até abril',
  '2. Dead-letter queue',
  '### Detalhe',
  '> Citação da RFC',
  '```',
  'kafka-topics --create',
  '```',
  'Fim.',
  '## Raw Text',
  'Texto cru repetido.',
].join('\n');

const detail = (overrides: Partial<NoteDetail> = {}): NoteDetail =>
  ({
    note_id: 'ata--abc',
    title: 'Ata do comitê',
    source_path: 'C:\\vault\\reunioes\\ata.md',
    source_type: 'markdown',
    created_at: '2025-03-25T14:00:00Z',
    tags: ['kafka'],
    structured_markdown: markdown,
    chunk_count: 2,
    chunks: [
      { chunk_id: 'c1', chunk_index: 0, token_count: 120, char_start: 0, char_end: 800, snippet: 'Primeiro trecho' },
      { chunk_id: 'c2', chunk_index: 1, token_count: 80, char_start: 680, char_end: 1200, snippet: 'Segundo trecho' },
    ],
    ...overrides,
  }) as NoteDetail;

const renderView = (props: Partial<Parameters<typeof NoteDetailView>[0]> = {}) => {
  const handlers = { onReindex: vi.fn(), onDelete: vi.fn() };
  render(
    <NoteDetailView
      detail={detail()}
      crumbs={['reunioes', '2025', 'ata.md']}
      isMutating={false}
      isLoadingDetail={false}
      {...handlers}
      {...props}
    />
  );
  return handlers;
};

describe('NoteDetailView', () => {
  afterEach(() => {
    cleanup();
  });

  it('lê o Markdown: frontmatter, títulos, listas, citação, código e destaques', () => {
    renderView();
    const body = document.querySelector('.reader__body') as HTMLElement;

    expect(within(body).getByText('tags').nextSibling?.textContent).toBe('kafka, adr');
    expect(within(body).queryByText('Resumo que não aparece na leitura.')).toBeNull();
    expect(within(body).queryByText('Texto cru repetido.')).toBeNull();
    expect(within(body).getByText('vazio').nextSibling?.textContent).toBe('—');
    // O H1 igual ao título não se repete no corpo.
    expect(within(body).queryByRole('heading', { name: 'Ata do comitê' })).toBeNull();
    expect(within(body).getByRole('heading', { level: 2, name: 'Decisões' })).toBeTruthy();
    expect(within(body).getByRole('heading', { level: 3, name: 'Detalhe' })).toBeTruthy();
    expect(within(body).getByText('message broker').tagName).toBe('STRONG');
    expect(within(body).getByText('plataforma').tagName).toBe('CODE');
    expect(body.querySelectorAll('ul > li')).toHaveLength(2);
    expect(body.querySelectorAll('ol > li')).toHaveLength(2);
    expect(within(body).getByText('Citação da RFC').tagName).toBe('BLOCKQUOTE');
    expect(within(body).getByText('kafka-topics --create').tagName).toBe('CODE');
    expect(screen.getByRole('navigation', { name: 'Local no vault' }).textContent).toContain('reunioes2025ata.md');
  });

  it('lê tabela e link do Markdown, sem comentário HTML e sem link que não seja http', () => {
    const texto = [
      '<!-- ai-memory:start -->',
      'Veja o [site](https://exemplo.com) e o [local](file:///c/segredo).',
      '',
      '| Situação | Ferramenta |',
      '|---|---|',
      '| salvar `nota` | write |',
      '| a \\| b | query |',
      '',
      '| só uma linha com barra |',
    ].join('\n');
    renderView({ detail: detail({ structured_markdown: texto }) });
    const body = document.querySelector('.reader__body') as HTMLElement;

    expect(body.textContent).not.toContain('ai-memory:start');
    const site = within(body).getByRole('link', { name: 'site' });
    expect(site.getAttribute('href')).toBe('https://exemplo.com');
    expect(site.getAttribute('target')).toBe('_blank');
    expect(within(body).queryByRole('link', { name: 'local' })).toBeNull();
    expect(body.textContent).toContain('local');

    const table = within(body).getByRole('table');
    expect(within(table).getAllByRole('columnheader').map((cell) => cell.textContent)).toEqual(['Situação', 'Ferramenta']);
    expect(within(table).getAllByRole('row')).toHaveLength(3);
    expect(within(table).getByText('nota').tagName).toBe('CODE');
    expect(within(table).getByText('a | b')).toBeTruthy();
    // Linha com | sem a régua abaixo não é tabela.
    expect(within(body).getByText('| só uma linha com barra |').tagName).toBe('P');
  });

  it('Ler e Trechos: os trechos ficam em cartões com tokens, faixa e sobreposição', async () => {
    const user = userEvent.setup();
    renderView();

    expect(screen.getByRole('radio', { name: 'Ler' }).getAttribute('aria-checked')).toBe('true');
    await user.click(screen.getByRole('radio', { name: 'Trechos' }));

    const list = screen.getByRole('list', { name: 'Trechos indexados' });
    const cards = within(list).getAllByRole('listitem');
    expect(cards).toHaveLength(2);
    expect(within(cards[1]).getByText('#1')).toBeTruthy();
    expect(within(cards[1]).getByText('80 tok')).toBeTruthy();
    expect(within(cards[1]).getByText('680–1.200')).toBeTruthy();
    expect(within(cards[1]).getByText(/120 sobrepostos/)).toBeTruthy();
    expect(within(cards[0]).queryByText(/sobrepostos/)).toBeNull();

    await user.click(screen.getByRole('radio', { name: 'Ler' }));
    expect(screen.queryByRole('list', { name: 'Trechos indexados' })).toBeNull();
  });

  it('o mapa mostra onde cada trecho cai na nota e leva até o cartão', async () => {
    const user = userEvent.setup();
    const scrollIntoView = vi.fn();
    Element.prototype.scrollIntoView = scrollIntoView;
    renderView();
    await user.click(screen.getByRole('radio', { name: 'Trechos' }));

    const map = screen.getByRole('region', { name: 'Mapa dos trechos' });
    expect(within(map).getByText('1.200 caracteres')).toBeTruthy();
    const segundo = within(map).getByRole('button', { name: 'Ir para o trecho 1' });
    // 680..1200 de 1200 caracteres
    expect(segundo.style.left).toBe('56.67%');
    expect(segundo.style.width).toBe('43.33%');

    await user.click(segundo);
    const card = screen.getByText('Segundo trecho').closest('li') as HTMLElement;
    expect(card.classList.contains('is-active')).toBe(true);
    expect(scrollIntoView.mock.contexts).toContain(card);
  });

  it('nota sem trechos: avisa, sem mapa', async () => {
    const user = userEvent.setup();
    renderView({ detail: detail({ chunks: [], chunk_count: 0 }) });
    await user.click(screen.getByRole('radio', { name: 'Trechos' }));

    expect(screen.getByText('Esta nota ainda não tem trechos indexados.')).toBeTruthy();
    expect(screen.queryByRole('region', { name: 'Mapa dos trechos' })).toBeNull();
  });

  it('Reindexar mostra o andamento', () => {
    renderView({ isReindexing: true, isMutating: true });
    const button = screen.getByRole('button', { name: 'Reindexando…' }) as HTMLButtonElement;
    expect(button.disabled).toBe(true);
    expect(button.querySelector('.ui-spin')).toBeTruthy();
  });

  it('copia o caminho e apaga só depois de confirmar', async () => {
    const user = userEvent.setup();
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, 'clipboard', { value: { writeText }, configurable: true });
    const { onDelete } = renderView();

    await user.click(screen.getByRole('button', { name: 'Mais ações' }));
    expect(document.querySelector('[role="menu"], [role="menuitem"]')).toBeNull();
    await user.click(screen.getByRole('button', { name: 'Copiar caminho' }));
    expect(writeText).toHaveBeenCalledWith('C:\\vault\\reunioes\\ata.md');
    expect(await screen.findByText('caminho copiado')).toBeTruthy();

    await user.click(screen.getByRole('button', { name: 'Mais ações' }));
    await user.click(screen.getByRole('button', { name: /Apagar do corpus/ }));
    await user.click(screen.getByRole('button', { name: 'Cancelar' }));
    expect(onDelete).not.toHaveBeenCalled();

    await user.click(screen.getByRole('button', { name: 'Mais ações' }));
    await user.keyboard('{Escape}');
    expect(screen.queryByRole('button', { name: 'Copiar caminho' })).toBeNull();

    await user.click(screen.getByRole('button', { name: 'Mais ações' }));
    await user.click(screen.getByRole('button', { name: /Apagar do corpus/ }));
    await user.click(screen.getByRole('button', { name: 'Apagar do corpus' }));
    expect(onDelete).toHaveBeenCalledTimes(1);
  });

  it('fecha o menu ao clicar fora e não quebra se a cópia falhar', async () => {
    const user = userEvent.setup();
    Object.defineProperty(navigator, 'clipboard', {
      value: { writeText: vi.fn().mockRejectedValue(new Error('negado')) },
      configurable: true,
    });
    renderView();

    await user.click(screen.getByRole('button', { name: 'Mais ações' }));
    await user.click(document.body);
    expect(screen.queryByRole('button', { name: 'Copiar caminho' })).toBeNull();

    await user.click(screen.getByRole('button', { name: 'Mais ações' }));
    await user.click(screen.getByRole('button', { name: 'Copiar caminho' }));
    expect(screen.queryByText('caminho copiado')).toBeNull();
  });

  it('com highlightChunkId, abre os chunks, destaca o trecho citado e rola até ele', () => {
    const scrollIntoView = vi.fn();
    Element.prototype.scrollIntoView = scrollIntoView;
    renderView({ highlightChunkId: 'c2' });

    const list = screen.getByRole('list', { name: 'Trechos indexados' });
    const cited = within(list).getByText('Segundo trecho').closest('li') as HTMLElement;
    expect(cited.classList.contains('reader__chunk--cited')).toBe(true);
    expect(within(cited).getByText('trecho citado')).toBeTruthy();
    expect(within(list).getByText('Primeiro trecho').closest('li')?.classList.contains('reader__chunk--cited')).toBe(false);
    expect(screen.getByRole('radio', { name: 'Trechos' }).getAttribute('aria-checked')).toBe('true');
    expect(scrollIntoView).toHaveBeenCalledTimes(1);
    expect(scrollIntoView).toHaveBeenCalledWith({ block: 'center' });
  });

  it('trecho que a nota não tem mais: abre a leitura normal, sem destaque nem erro', () => {
    renderView({ highlightChunkId: 'c-antigo' });

    expect(screen.queryByRole('list', { name: 'Trechos indexados' })).toBeNull();
    expect(document.querySelector('.reader__chunk--cited')).toBeNull();
    expect(document.querySelector('.reader__body')).toBeTruthy();
  });
});
