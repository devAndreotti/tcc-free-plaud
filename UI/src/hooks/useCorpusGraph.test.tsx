import type { ReactNode } from 'react';
import { act, renderHook, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { QueueContext } from '../contexts/QueueContextObject';
import { bridge } from '../services/bridge';
import { buildCorpusNodes, useCorpusGraph } from './useCorpusGraph';

vi.mock('../services/bridge', () => ({
  bridge: { listNotes: vi.fn(), listCorpusRoots: vi.fn(), listNoteLinks: vi.fn() },
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
    bridgeMock.listNoteLinks.mockResolvedValue([]);
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

  it('regressao: durante a indexação, cada lote gravado (committed_count sobe) já entra no grafo', async () => {
    let job: { job_id: string; status: string; progress: { committed_count: number } } = {
      job_id: 'j1', status: 'running', progress: { committed_count: 0 },
    };
    const wrapper = ({ children }: { children: ReactNode }) => (
      <QueueContext.Provider value={{ job } as never}>{children}</QueueContext.Provider>
    );
    const { result, rerender } = renderHook(() => useCorpusGraph(), { wrapper });
    await waitFor(() => expect(bridgeMock.listNotes).toHaveBeenCalledTimes(1));

    // Outro poll do mesmo lote não relê o corpus
    job = { ...job, progress: { committed_count: 0 } };
    rerender();
    expect(bridgeMock.listNotes).toHaveBeenCalledTimes(1);

    bridgeMock.listNotes.mockResolvedValue([note(), note({ note_id: 'b', title: 'B' })]);
    job = { ...job, progress: { committed_count: 32 } };
    rerender();
    await waitFor(() => expect(result.current.nodes).toHaveLength(2));
    expect(bridgeMock.listNotes).toHaveBeenCalledTimes(2);
  });

  // Job rodando, com o provider relendo a variável a cada render (o job chega novo a cada consulta).
  const withJob = (read: () => unknown) => ({ children }: { children: ReactNode }) => (
    <QueueContext.Provider value={{ job: read() } as never}>{children}</QueueContext.Provider>
  );
  const running = (progress: object) => ({ job_id: 'j1', status: 'running', progress });

  it('durante o job, cada lote pede só as notas novas e soma às que já estavam', async () => {
    let job = running({ committed_count: 0 });
    const { result, rerender } = renderHook(() => useCorpusGraph(), { wrapper: withJob(() => job) });
    await waitFor(() => expect(result.current.nodes).toHaveLength(1));

    bridgeMock.listNotes.mockResolvedValue([note({ note_id: 'b', title: 'B', created_at: '2026-10-18T12:05:00' })]);
    job = running({ committed_count: 32 });
    rerender();

    await waitFor(() => expect(result.current.nodes.map((n) => n.id)).toEqual(['arq--1', 'b']));
    expect(bridgeMock.listNotes).toHaveBeenLastCalledWith({ since: '2026-10-18T12:00:00' });
  });

  it('no fim do job a leitura é completa: é ela que tira do grafo o que foi apagado', async () => {
    let job: { job_id: string; status: string; progress: object } = running({ committed_count: 32 });
    const { result, rerender } = renderHook(() => useCorpusGraph(), { wrapper: withJob(() => job) });
    await waitFor(() => expect(result.current.nodes).toHaveLength(1));

    bridgeMock.listNotes.mockClear();
    bridgeMock.listNotes.mockResolvedValue([]);
    job = { job_id: 'j1', status: 'completed', progress: { committed_count: 40 } };
    rerender();

    await waitFor(() => expect(result.current.nodes).toHaveLength(0));
    expect(bridgeMock.listNotes).toHaveBeenCalledWith();
  });

  it('arquivo lido e não gravado vira nó pendente, o arquivo atual é o ativo e a gravação tira o pendente', async () => {
    const lida = 'C:\\Vault\\Projetos\\escolio\\Fila.md';
    let job = running({ committed_count: 0, pending_files: [lida], current_path: lida });
    const { result, rerender } = renderHook(() => useCorpusGraph(), { wrapper: withJob(() => job) });
    await waitFor(() => expect(result.current.nodes).toHaveLength(2));

    const pending = result.current.nodes.find((n) => n.pending);
    expect(pending).toMatchObject({ id: 'pending:Projetos/escolio/Fila.md', name: 'Fila', path: 'Projetos/escolio/Fila.md' });
    expect(result.current.activeId).toBe(pending?.id);
    expect(result.current.live).toEqual({ current: 'Fila.md', pending: 1 });

    bridgeMock.listNotes.mockResolvedValue([note({ note_id: 'fila', title: 'Fila', source_path: lida, created_at: '2026-10-18T12:05:00' })]);
    job = running({ committed_count: 32, pending_files: [], current_path: lida });
    rerender();

    await waitFor(() => expect(result.current.nodes.map((n) => n.id)).toEqual(['arq--1', 'fila']));
    expect(result.current.nodes.some((n) => n.pending)).toBe(false);
    expect(result.current.activeId).toBe('fila');
    expect(result.current.live).toEqual({ current: 'Fila.md', pending: 0 });
  });

  it('nota que já existe não ganha pendente repetido quando uma versão nova está a caminho', async () => {
    const job = running({ committed_count: 0, pending_files: ['c:/vault/projetos/escolio/arquitetura.md'] });
    const { result } = renderHook(() => useCorpusGraph(), { wrapper: withJob(() => job) });
    // Antes da primeira leitura o arquivo aparece como pendente; com a nota carregada, fica só ela.
    await waitFor(() => expect(result.current.nodes.map((n) => n.id)).toEqual(['arq--1']));
    expect(result.current.nodes[0].pending).toBeUndefined();
  });

  it('consulta do job sem novidade não remonta o grafo (mesma lista de nós)', async () => {
    let job = running({ committed_count: 0, pending_files: ['C:\\Vault\\Projetos\\a.md'], current_path: 'C:\\Vault\\Projetos' });
    const { result, rerender } = renderHook(() => useCorpusGraph(), { wrapper: withJob(() => job) });
    await waitFor(() => expect(result.current.nodes).toHaveLength(2));
    const before = result.current.nodes;

    job = running({ committed_count: 0, pending_files: ['C:\\Vault\\Projetos\\a.md'], current_path: 'C:\\Vault\\Projetos' });
    rerender();

    expect(result.current.nodes).toBe(before);
    // Passo do job em cima da pasta inteira: não há arquivo para destacar nem nome para mostrar.
    expect(result.current.activeId).toBeNull();
    expect(result.current.live?.current).toBeNull();
  });

  it('sem job, nada de ao vivo', async () => {
    const { result } = renderHook(() => useCorpusGraph());
    await waitFor(() => expect(result.current.nodes).toHaveLength(1));
    expect(result.current.live).toBeNull();
    expect(result.current.activeId).toBeNull();
  });

  it('uma leitura lenta de antes não sobrescreve a mais nova', async () => {
    const { result } = renderHook(() => useCorpusGraph());
    await waitFor(() => expect(result.current.nodes).toHaveLength(1));

    let releaseOld: (value: ReturnType<typeof note>[]) => void = () => {};
    bridgeMock.listNotes.mockReturnValueOnce(new Promise((resolve) => { releaseOld = resolve; }) as never);
    bridgeMock.listNotes.mockResolvedValueOnce([note(), note({ note_id: 'b', title: 'B' })]);
    let old: Promise<void> = Promise.resolve();
    await act(async () => {
      old = result.current.refresh();
      await result.current.refresh();
    });
    expect(result.current.nodes).toHaveLength(2);

    await act(async () => { releaseOld([]); await old; });
    expect(result.current.nodes).toHaveLength(2);
  });

  it('ligações só entram no grafo quando as duas pontas são notas listadas', async () => {
    bridgeMock.listNotes.mockResolvedValue([note(), note({ note_id: 'b', title: 'B' })]);
    bridgeMock.listNoteLinks.mockResolvedValue([
      { source: 'arq--1', target: 'b' },
      { source: 'arq--1', target: 'apagada' },
    ]);
    const { result } = renderHook(() => useCorpusGraph());
    await waitFor(() => expect(result.current.nodes).toHaveLength(2));
    expect(result.current.links).toEqual([{ source: 'arq--1', target: 'b' }]);
  });

  it('falha ao ler as ligações não impede o grafo de pastas e notas', async () => {
    bridgeMock.listNoteLinks.mockRejectedValue(new Error('banco indisponível'));
    const { result } = renderHook(() => useCorpusGraph());
    await waitFor(() => expect(result.current.nodes).toHaveLength(1));
    expect(result.current.links).toEqual([]);
  });
});
