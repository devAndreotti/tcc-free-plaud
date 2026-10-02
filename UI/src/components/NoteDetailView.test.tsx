import { cleanup, render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';
import type { NoteDetail } from '../services/bridge';
import { NoteDetailView } from './NoteDetailView';

const markdown = [
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

    expect(within(body).getByText('tags').nextSibling?.textContent).toBe('[kafka, adr]');
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

  it('mostra os chunks com a sobreposição entre eles', async () => {
    const user = userEvent.setup();
    renderView();

    await user.click(screen.getByRole('checkbox', { name: 'Mostrar chunks' }));

    const list = screen.getByRole('list', { name: 'Chunks indexados' });
    expect(within(list).getAllByRole('listitem')).toHaveLength(2);
    expect(within(list).getByText(/120 sobrepostos/)).toBeTruthy();
  });

  it('copia o caminho e apaga só depois de confirmar', async () => {
    const user = userEvent.setup();
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, 'clipboard', { value: { writeText }, configurable: true });
    const { onDelete } = renderView();

    await user.click(screen.getByRole('button', { name: 'Mais ações' }));
    await user.click(screen.getByRole('menuitem', { name: 'Copiar caminho' }));
    expect(writeText).toHaveBeenCalledWith('C:\\vault\\reunioes\\ata.md');
    expect(await screen.findByText('caminho copiado')).toBeTruthy();

    await user.click(screen.getByRole('button', { name: 'Mais ações' }));
    await user.click(screen.getByRole('menuitem', { name: /Apagar do corpus/ }));
    await user.click(screen.getByRole('button', { name: 'Cancelar' }));
    expect(onDelete).not.toHaveBeenCalled();

    await user.click(screen.getByRole('button', { name: 'Mais ações' }));
    await user.keyboard('{Escape}');
    expect(screen.queryByRole('menu')).toBeNull();

    await user.click(screen.getByRole('button', { name: 'Mais ações' }));
    await user.click(screen.getByRole('menuitem', { name: /Apagar do corpus/ }));
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
    expect(screen.queryByRole('menu')).toBeNull();

    await user.click(screen.getByRole('button', { name: 'Mais ações' }));
    await user.click(screen.getByRole('menuitem', { name: 'Copiar caminho' }));
    expect(screen.queryByText('caminho copiado')).toBeNull();
  });
});
