import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { MarkdownNode } from '../lib/vaultGraph';
import ForceGraph from './ForceGraph';

// O canvas não roda no jsdom: aqui só importa o que fica sobre o painel
vi.mock('../lib/vaultGraph', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../lib/vaultGraph')>();
  return { ...actual, tick: () => {} };
});

const note = (path: string): MarkdownNode => ({
  id: path,
  name: path.split('/').at(-1)!.replace(/\.md$/, ''),
  path,
  size: 1,
  modified: '',
});

const HINT_TITLE = 'Nenhuma ligação [[…]] encontrada nas 2 notas';
const HINT_TIP = 'Use [[Nome da nota]] no Markdown para ligar notas.';

beforeEach(() => {
  vi.stubGlobal('requestAnimationFrame', (cb: FrameRequestCallback) => { cb(0); return 1; });
  vi.stubGlobal('cancelAnimationFrame', () => {});
  vi.spyOn(HTMLCanvasElement.prototype, 'getContext').mockImplementation(() => ({
    clearRect() {}, save() {}, restore() {}, scale() {}, translate() {}, beginPath() {}, moveTo() {},
    lineTo() {}, stroke() {}, arc() {}, fill() {}, fillText() {}, measureText: () => ({ width: 10 }),
    roundRect() {}, strokeText() {},
  } as never));
  // ResizeObserver que entrega imediatamente um painel 320×600
  class FakeResizeObserver {
    private readonly cb: ResizeObserverCallback;
    constructor(cb: ResizeObserverCallback) { this.cb = cb; }
    observe(target: Element) {
      this.cb([{ contentRect: { width: 320, height: 600 }, target } as unknown as ResizeObserverEntry], this as never);
    }
    unobserve() {}
    disconnect() {}
  }
  vi.stubGlobal('ResizeObserver', FakeResizeObserver);
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe('ForceGraph: estado vazio do modo Links', () => {
  const vault = [note('A/x.md'), note('B/y.md')];

  it('modo Links sem nenhuma ligação mostra o aviso com o número de notas e a dica', () => {
    render(<ForceGraph vaultNodes={vault} mode="links" links={[]} />);
    expect(screen.getByText(HINT_TITLE)).toBeTruthy();
    expect(screen.getByText(HINT_TIP)).toBeTruthy();
  });

  it('o aviso só usa singular quando há uma nota', () => {
    render(<ForceGraph vaultNodes={[note('solo.md')]} mode="links" links={[]} />);
    expect(screen.getByText('Nenhuma ligação [[…]] encontrada nas 1 nota')).toBeTruthy();
  });

  it('uma ligação repetida ou que aponta para fora do vault não conta: o aviso continua', () => {
    render(
      <ForceGraph
        vaultNodes={vault}
        mode="links"
        links={[{ source: 'A/x.md', target: 'A/x.md' }, { source: 'A/x.md', target: 'fora.md' }]}
      />,
    );
    expect(screen.getByText(HINT_TITLE)).toBeTruthy();
  });

  it('modo Links com ao menos uma ligação não mostra o aviso', () => {
    render(<ForceGraph vaultNodes={vault} mode="links" links={[{ source: 'A/x.md', target: 'B/y.md' }]} />);
    expect(screen.queryByText(HINT_TITLE)).toBeNull();
  });

  it('modo Ambos sem ligações não mostra nada extra', () => {
    render(<ForceGraph vaultNodes={vault} mode="ambos" links={[]} />);
    expect(screen.queryByText(HINT_TITLE)).toBeNull();
    expect(screen.queryByText(HINT_TIP)).toBeNull();
  });

  it('modo Pastas não mostra o aviso de ligações', () => {
    render(<ForceGraph vaultNodes={vault} mode="pastas" links={[]} />);
    expect(screen.queryByText(HINT_TITLE)).toBeNull();
  });

  it('sem notas mantém a mensagem atual, sem aviso', () => {
    render(<ForceGraph vaultNodes={[]} mode="links" links={[]} />);
    expect(screen.getByText('Nenhuma nota indexada nesta vault. Indexe uma pasta na Fila.')).toBeTruthy();
    expect(screen.queryByText(HINT_TITLE)).toBeNull();
  });
});
