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
      message: 'Document indexed successfully.',
    });
  });

  it('lista notas e abre detalhe com markdown e chunks', async () => {
    render(<NotesPanel />);

    expect((await screen.findAllByText('Nota alpha')).length).toBeGreaterThan(0);
    expect(await screen.findByText('Markdown estruturado')).toBeTruthy();
    expect(screen.getByText('# Nota alpha', { exact: false })).toBeTruthy();
    expect(screen.getByText('nota-alpha::v1::0000')).toBeTruthy();
  });

  it('mostra erro controlado quando listagem falha', async () => {
    bridgeMock.listNotes.mockRejectedValueOnce(new Error('Falha DB'));

    render(<NotesPanel />);

    expect(await screen.findByText('Falha DB')).toBeTruthy();
  });

  it('executa reindex e delete com confirmacao textual', async () => {
    const user = userEvent.setup();
    render(<NotesPanel />);

    await screen.findByText('Markdown estruturado');
    await user.click(screen.getByRole('button', { name: 'Reindexar' }));

    await waitFor(() => {
      expect(bridgeMock.reindexNote).toHaveBeenCalledWith('nota-alpha');
    });

    await user.type(screen.getByLabelText('Confirmar exclusão'), 'APAGAR');
    await user.click(screen.getByRole('button', { name: /Apagar/ }));

    await waitFor(() => {
      expect(bridgeMock.deleteNote).toHaveBeenCalledWith('nota-alpha', 'APAGAR');
    });
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
