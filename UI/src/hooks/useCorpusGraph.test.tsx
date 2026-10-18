import type { ReactNode } from 'react';
import { act, renderHook, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { QueueContext } from '../contexts/QueueContextObject';
import { bridge } from '../services/bridge';
import { buildCorpusNodes, useCorpusGraph } from './useCorpusGraph';

vi.mock('../services/bridge', () => ({
  bridge: { listNotes: vi.fn(), listCorpusRoots: vi.fn() },
}));

const bridgeMock = vi.mocked(bridge);

const note = (over: Partial<{ note_id: string; title: string; source_path: string; created_at: string }> = {}) => ({
  note_id: 'arq--1',
  title: 'Arquitetura',
  source_type: 'md',
  source_path: 'C:\\Vault\\Projetos\\escolio\\Arquitetura.md',
  created_at: '2026-10-18T12:00:00',
  tags: [],
  chunk_count: 1,
  ...over,
});

describe('buildCorpusNodes', () => {
  it('regressao: caminho relativo à raiz que contém a nota, com o nome da raiz como 1º nível', () => {
    const nodes = buildCorpusNodes(
      [note()],
      [{ root: 'C:\\Vault\\Projetos', notes_count: 1 }],
    );
    expect(nodes).toEqual([
      expect.objectContaining({ id: 'arq--1', name: 'Arquitetura', path: 'Projetos/escolio/Arquitetura.md' }),
    ]);
  });

  it('regressao: nota fora de qualquer raiz vai para a pasta Soltas', () => {
    const nodes = buildCorpusNodes(
      [note({ note_id: 'fora', title: 'Solta', source_path: 'D:\\Outro\\Solta.md' })],
      [{ root: 'C:\\Vault\\Projetos', notes_count: 1 }],
    );
    expect(nodes[0].path).toBe('Soltas/Solta.md');
  });

  it('regressao: usa a raiz mais específica quando uma contém a outra', () => {
    const nodes = buildCorpusNodes(
      [note()],
      [
        { root: 'C:\\Vault', notes_count: 0 },
        { root: 'C:\\Vault\\Projetos', notes_count: 1 },
      ],
    );
    expect(nodes[0].path).toBe('Projetos/escolio/Arquitetura.md');
  });

  it('sem título, usa o nome do arquivo', () => {
    const nodes = buildCorpusNodes([note({ title: '' })], []);
    expect(nodes[0].name).toBe('Arquitetura');
  });
});

describe('useCorpusGraph', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    bridgeMock.listNotes.mockResolvedValue([note()]);
    bridgeMock.listCorpusRoots.mockResolvedValue([{ root: 'C:\\Vault\\Projetos', notes_count: 1 }]);
  });

  it('regressao: monta os nós a partir de listNotes ao montar', async () => {
    const { result } = renderHook(() => useCorpusGraph());
    await waitFor(() => expect(result.current.nodes).toHaveLength(1));
    expect(result.current.nodes[0]).toMatchObject({ id: 'arq--1', path: 'Projetos/escolio/Arquitetura.md' });
  });

  it('recarrega quando o corpus avisa (nota apagada ou indexada)', async () => {
    const { result } = renderHook(() => useCorpusGraph());
    await waitFor(() => expect(result.current.nodes).toHaveLength(1));

    bridgeMock.listNotes.mockResolvedValue([]);
    await act(async () => { window.dispatchEvent(new Event('escolio:corpus-changed')); });
    await waitFor(() => expect(result.current.nodes).toHaveLength(0));
  });

  it('refresh() recarrega sob demanda', async () => {
    const { result } = renderHook(() => useCorpusGraph());
    await waitFor(() => expect(result.current.nodes).toHaveLength(1));

    bridgeMock.listNotes.mockResolvedValue([note({ note_id: 'b', title: 'B' }), note({ note_id: 'c', title: 'C' })]);
    await act(async () => { await result.current.refresh(); });
    expect(result.current.nodes.map((n) => n.id)).toEqual(['b', 'c']);
  });

  it('regressao: recarrega quando um job da Fila termina (status diferente de running)', async () => {
    let job: { job_id: string; status: string } = { job_id: 'j1', status: 'running' };
    const wrapper = ({ children }: { children: ReactNode }) => (
      <QueueContext.Provider value={{ job } as never}>{children}</QueueContext.Provider>
    );
    const { rerender } = renderHook(() => useCorpusGraph(), { wrapper });
    await waitFor(() => expect(bridgeMock.listNotes).toHaveBeenCalledTimes(1));

    job = { job_id: 'j1', status: 'completed' };
    rerender();
    await waitFor(() => expect(bridgeMock.listNotes).toHaveBeenCalledTimes(2));
  });
});
