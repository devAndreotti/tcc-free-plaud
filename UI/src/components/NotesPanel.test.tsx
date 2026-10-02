import { cleanup, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import NotesPanel, { __resetNotesCacheForTests } from './NotesPanel';

const bridgeMock = vi.hoisted(() => ({
  listNotes: vi.fn(),
  getNoteDetail: vi.fn(),
  deleteNote: vi.fn(),
  reindexNote: vi.fn(),
}));

vi.mock('../services/bridge', () => ({
  bridge: bridgeMock,
}));

const noteSummary = {
  note_id: 'nota-alpha',
  title: 'Nota alpha',
  source_type: 'md',
  source_path: 'vault/nota-alpha.md',
  created_at: '2026-05-25T10:00:00+00:00',
  tags: ['md'],
  chunk_count: 1,
};

const noteDetail = {
  ...noteSummary,
  structured_markdown: '# Nota alpha\n\nConteudo estruturado.',
  chunks: [
    {
      chunk_id: 'nota-alpha::v1::0000',
      chunk_index: 0,
      char_start: 0,
      char_end: 32,
      token_count: 4,
      snippet: 'Conteudo estruturado.',
    },
  ],
};

describe('NotesPanel', () => {
  afterEach(() => {
    cleanup();
  });

  beforeEach(() => {
    __resetNotesCacheForTests();
    bridgeMock.listNotes.mockReset();
    bridgeMock.getNoteDetail.mockReset();
    bridgeMock.deleteNote.mockReset();
    bridgeMock.reindexNote.mockReset();

    bridgeMock.listNotes.mockResolvedValue([noteSummary]);
    bridgeMock.getNoteDetail.mockResolvedValue(noteDetail);
    bridgeMock.deleteNote.mockResolvedValue({ ok: true, note_id: 'nota-alpha', deleted_vectors: 1 });
    bridgeMock.reindexNote.mockResolvedValue({
      ok: true,
      note_id: 'nota-alpha',
      status: 'success',
      chunks_indexed: 1,
      message: 'Nota indexada.',
    });
  });

  it('lista notas e abre a nota em modo leitura, com chunks sob demanda', async () => {
    const user = userEvent.setup();
    render(<NotesPanel />);

    expect((await screen.findAllByText('Nota alpha')).length).toBeGreaterThan(0);
    expect(await screen.findByText('Conteudo estruturado.')).toBeTruthy();
    // O título do markdown não é repetido: já aparece como título da leitura.
    expect(screen.queryByText('# Nota alpha', { exact: false })).toBeNull();

    await user.click(screen.getByLabelText('Mostrar chunks'));

    expect(screen.getByText('#0 · 4 tok')).toBeTruthy();
    expect(screen.getByRole('list', { name: 'Chunks indexados' })).toBeTruthy();
  });

  it('mostra erro controlado quando listagem falha', async () => {
    bridgeMock.listNotes.mockRejectedValueOnce(new Error('Falha DB'));

    render(<NotesPanel />);

    expect(await screen.findByText('Falha DB')).toBeTruthy();
  });

  it('reindexa e apaga com confirmação no popover, sem digitar nada', async () => {
    const user = userEvent.setup();
    render(<NotesPanel />);

    await screen.findByText('Conteudo estruturado.');
    await user.click(screen.getByRole('button', { name: 'Reindexar' }));

    await waitFor(() => {
      expect(bridgeMock.reindexNote).toHaveBeenCalledWith('nota-alpha');
    });

    await user.click(screen.getByRole('button', { name: 'Mais ações' }));
    await user.click(screen.getByRole('menuitem', { name: /Apagar do corpus/ }));

    const dialog = screen.getByRole('alertdialog', { name: 'Apagar do corpus?' });
    expect(dialog.textContent).toContain('O arquivo no vault não é alterado.');
    expect(bridgeMock.deleteNote).not.toHaveBeenCalled();

    await user.click(screen.getByRole('button', { name: 'Apagar do corpus' }));

    await waitFor(() => {
      expect(bridgeMock.deleteNote).toHaveBeenCalledWith('nota-alpha', 'APAGAR');
    });
  });

  it('cancelar o popover não apaga nada', async () => {
    const user = userEvent.setup();
    render(<NotesPanel />);

    await screen.findByText('Conteudo estruturado.');
    await user.click(screen.getByRole('button', { name: 'Mais ações' }));
    await user.click(screen.getByRole('menuitem', { name: /Apagar do corpus/ }));
    await user.click(screen.getByRole('button', { name: 'Cancelar' }));

    expect(screen.queryByRole('alertdialog')).toBeNull();
    expect(bridgeMock.deleteNote).not.toHaveBeenCalled();
  });

  it('mostra skeleton no primeiro load, sem cache', async () => {
    let resolveList: (notes: (typeof noteSummary)[]) => void = () => {};
    bridgeMock.listNotes.mockReturnValue(
      new Promise((resolve) => {
        resolveList = resolve;
      })
    );

    render(<NotesPanel />);

    expect(document.querySelectorAll('.skeleton-box').length).toBeGreaterThan(0);
    expect(screen.queryByText('Nota alpha')).toBeNull();

    resolveList([noteSummary]);

    expect((await screen.findAllByText('Nota alpha')).length).toBeGreaterThan(0);
    expect(document.querySelectorAll('.skeleton-box').length).toBe(0);
  });

  it('reusa o cache ao remontar, sem mostrar skeleton, e revalida em segundo plano', async () => {
    const first = render(<NotesPanel />);
    expect((await screen.findAllByText('Nota alpha')).length).toBeGreaterThan(0);
    first.unmount();

    bridgeMock.listNotes.mockClear();
    let resolveSecond: (notes: (typeof noteSummary)[]) => void = () => {};
    bridgeMock.listNotes.mockReturnValue(
      new Promise((resolve) => {
        resolveSecond = resolve;
      })
    );

    render(<NotesPanel />);

    // Mostra o cache imediatamente - sem skeleton, sem tela vazia.
    expect(screen.getByText('Nota alpha')).toBeTruthy();
    expect(document.querySelectorAll('.skeleton-box').length).toBe(0);
    expect(bridgeMock.listNotes).toHaveBeenCalledTimes(1);

    resolveSecond([noteSummary]);
    await waitFor(() => expect(screen.getByText('Nota alpha')).toBeTruthy());
  });
});
