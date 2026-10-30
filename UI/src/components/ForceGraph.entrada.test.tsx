import { cleanup, render } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { MarkdownNode } from '../lib/vaultGraph';
import { buildGraph } from '../lib/vaultGraph';
import ForceGraph from './ForceGraph';

// Sem a simulação: as posições são só a espiral de buildGraph, então o teste sabe onde cada nó vai parar
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

// Painel 320×600: o centro lógico é (160, 300)
const CX = 160;
const CY = 300;
const vault = [note('A/x.md'), note('B/y.md')]; // 5 nós: raiz, A, B, A/x, B/y
const NODE_COUNT = 5;

let arcs: ReturnType<typeof vi.fn>;

class FakeResizeObserver {
  private readonly cb: ResizeObserverCallback;
  constructor(cb: ResizeObserverCallback) { this.cb = cb; }
  observe(target: Element) {
    this.cb([{ contentRect: { width: 320, height: 600 }, target } as unknown as ResizeObserverEntry], this as never);
  }
  unobserve() {}
  disconnect() {}
}

beforeEach(() => {
  arcs = vi.fn();
  // Relógio parado: no jsdom o primeiro getComputedStyle é lento e o tempo real correria dentro do
  // loop síncrono. Com o relógio parado, todo quadro antes do fim fica em k = 0 (no centro).
  vi.spyOn(performance, 'now').mockReturnValue(1000);
  vi.spyOn(HTMLCanvasElement.prototype, 'getContext').mockImplementation(() => ({
    clearRect() {}, save() {}, restore() {}, scale() {}, translate() {}, beginPath() {}, moveTo() {},
    lineTo() {}, stroke() {}, arc: arcs, fill() {}, fillText() {}, measureText: () => ({ width: 10 }),
    roundRect() {}, strokeText() {},
  } as never));
  vi.stubGlobal('ResizeObserver', FakeResizeObserver);
  // rAF síncrono: a simulação inteira (300 quadros) roda dentro do render
  vi.stubGlobal('requestAnimationFrame', (cb: FrameRequestCallback) => { cb(0); return 1; });
  vi.stubGlobal('cancelAnimationFrame', () => {});
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

// Centros (x, y) de cada desenho de nó, na ordem em que foram desenhados
const points = () => arcs.mock.calls.map((c) => [c[0] as number, c[1] as number]);
const dist = (p: number[]) => Math.hypot(p[0] - CX, p[1] - CY);

describe('ForceGraph: abertura ao montar ou trocar de modo', () => {
  it('ao montar, o primeiro quadro desenha todos os nós no centro e a abertura parte daí', () => {
    render(<ForceGraph vaultNodes={vault} mode="ambos" />);
    const first = points().slice(0, NODE_COUNT);
    expect(first).toHaveLength(NODE_COUNT);
    for (const p of first) expect(dist(p)).toBeLessThan(0.5);
  });

  it('no fim da abertura os nós estão nas posições da simulação', () => {
    render(<ForceGraph vaultNodes={vault} mode="ambos" />);
    const { nodes } = buildGraph(vault, 320, 600);
    const last = points().slice(-NODE_COUNT);
    const expected = nodes.map((n) => [n.x, n.y]);
    for (const p of last) {
      expect(expected.some(([x, y]) => Math.abs(x - p[0]) < 0.01 && Math.abs(y - p[1]) < 0.01)).toBe(true);
    }
  });

  it('trocar de modo reabre o grafo: algum quadro novo tem todos os nós no centro', () => {
    const { rerender } = render(<ForceGraph vaultNodes={vault} mode="ambos" />);
    arcs.mockClear();
    rerender(<ForceGraph vaultNodes={vault} mode="pastas" />);
    // Cada quadro desenha NODE_COUNT nós; o da abertura inicial fica todo no centro
    const frames = Array.from({ length: Math.floor(points().length / NODE_COUNT) }, (_, i) =>
      points().slice(i * NODE_COUNT, (i + 1) * NODE_COUNT));
    expect(frames.some((f) => f.every((p) => dist(p) < 0.5))).toBe(true);
  });

  it('um novo array de ligações com as mesmas notas não reabre o grafo', () => {
    const { rerender } = render(<ForceGraph vaultNodes={vault} mode="ambos" links={[]} />);
    arcs.mockClear();
    rerender(<ForceGraph vaultNodes={vault} mode="ambos" links={[{ source: 'A/x.md', target: 'B/y.md' }]} />);
    const first = points().slice(0, NODE_COUNT);
    // Os nós continuam nas posições já calculadas: nem todos estão no centro
    expect(first.some((p) => dist(p) > 5)).toBe(true);
  });
});

describe('ForceGraph: movimento reduzido', () => {
  beforeEach(() => {
    vi.stubGlobal('matchMedia', (q: string) => ({ matches: q === '(prefers-reduced-motion: reduce)' }));
  });

  it('sem abertura: o primeiro quadro já sai nas posições finais, sem passar pelo centro', () => {
    render(<ForceGraph vaultNodes={vault} mode="ambos" />);
    const { nodes } = buildGraph(vault, 320, 600);
    const drawn = points();
    expect(drawn.length).toBeGreaterThan(0);
    const expected = nodes.map((n) => [n.x, n.y]);
    for (const p of drawn) {
      expect(expected.some(([x, y]) => Math.abs(x - p[0]) < 0.01 && Math.abs(y - p[1]) < 0.01)).toBe(true);
    }
  });
});
