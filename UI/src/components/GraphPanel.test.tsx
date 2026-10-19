import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import GraphPanel from './GraphPanel';

// O grafo de verdade precisa de canvas: aqui só interessa qual modo chega até ele
vi.mock('./ForceGraph', () => ({
  default: (props: { mode: string }) => <div data-testid="force-graph" data-mode={props.mode} />,
}));

const graph = vi.hoisted(() => ({
  nodes: [{ id: 'a', name: 'A', path: 'P/a.md', size: 0, modified: '' }],
  refresh: () => {},
}));
vi.mock('../hooks/useCorpusGraph', () => ({
  useCorpusGraph: () => ({ nodes: graph.nodes, links: [], refresh: graph.refresh }),
}));

const STORAGE_KEY = 'escolio:graph:mode';
const renderPanel = () => render(<GraphPanel isOpen onToggle={() => {}} />);
const pressed = (name: string) => screen.getByRole('button', { name }).getAttribute('aria-pressed');
const shownMode = () => screen.getByTestId('force-graph').getAttribute('data-mode');

beforeEach(() => {
  window.localStorage.clear();
});

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe('GraphPanel: seletor Pastas · Links · Ambos', () => {
  it('começa em Ambos e marca o botão ativo com aria-pressed', () => {
    renderPanel();
    expect(pressed('Ambos')).toBe('true');
    expect(pressed('Pastas')).toBe('false');
    expect(shownMode()).toBe('ambos');
  });

  it('trocar o modo muda aria-pressed, chega ao grafo e fica salvo para a próxima vez', () => {
    const first = renderPanel();
    fireEvent.click(screen.getByRole('button', { name: 'Links' }));
    expect(pressed('Links')).toBe('true');
    expect(pressed('Ambos')).toBe('false');
    expect(shownMode()).toBe('links');
    expect(window.localStorage.getItem(STORAGE_KEY)).toBe('links');

    first.unmount();
    renderPanel();
    expect(pressed('Links')).toBe('true');
    expect(shownMode()).toBe('links');
  });

  it('sem acesso ao armazenamento o seletor continua funcionando', () => {
    vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
      throw new Error('bloqueado');
    });
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new Error('bloqueado');
    });
    renderPanel();
    fireEvent.click(screen.getByRole('button', { name: 'Pastas' }));
    expect(pressed('Pastas')).toBe('true');
    expect(shownMode()).toBe('pastas');
  });
});
