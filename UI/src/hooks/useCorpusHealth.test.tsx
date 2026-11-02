import { act, renderHook, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { notifyCorpusProgress } from '../lib/corpusEvents';
import { bridge } from '../services/bridge';
import { useCorpusHealth } from './useCorpusHealth';

vi.mock('../services/bridge', () => ({ bridge: { getBackendSettings: vi.fn() } }));

const getSettings = vi.mocked(bridge.getBackendSettings);
const settings = (notes: number, chunks: number, doctor: object | null) =>
  ({ notes_count: notes, sqlite_chunks_count: chunks, doctor }) as never;

describe('useCorpusHealth durante a indexação', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    getSettings.mockResolvedValue(settings(10, 60, { status: 'warning', error_count: 0, warning_count: 2 }));
  });

  it('lote gravado atualiza notas e trechos sem rodar o Doctor e sem perder o estado dele', async () => {
    const { result } = renderHook(() => useCorpusHealth('k'));
    await waitFor(() => expect(result.current?.notes).toBe(10));

    getSettings.mockResolvedValue(settings(42, 250, null));
    await act(async () => { notifyCorpusProgress(); });

    await waitFor(() => expect(result.current?.notes).toBe(42));
    expect(getSettings).toHaveBeenLastCalledWith({ doctor: false });
    expect(result.current).toMatchObject({ chunks: 250, status: 'warning', warningCount: 2 });
  });

  it('falha na contagem ao vivo mantém os números que já estavam na tela', async () => {
    const { result } = renderHook(() => useCorpusHealth('k'));
    await waitFor(() => expect(result.current?.notes).toBe(10));

    getSettings.mockRejectedValue(new Error('banco ocupado'));
    await act(async () => { notifyCorpusProgress(); });

    expect(result.current?.notes).toBe(10);
  });
});
