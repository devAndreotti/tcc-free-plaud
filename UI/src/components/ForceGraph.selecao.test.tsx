import { fireEvent, render } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { MarkdownNode } from '../lib/vaultGraph';
import { buildGraph, fitCamera } from '../lib/vaultGraph';
import ForceGraph from './ForceGraph';

// Sem a simulação, as posições são só a espiral determinística de buildGraph
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

function makeCtx() {
  return {
    clearRect: vi.fn(), save: vi.fn(), restore: vi.fn(), scale: vi.fn(), translate: vi.fn(),
    beginPath: vi.fn(), moveTo: vi.fn(), lineTo: vi.fn(), stroke: vi.fn(), arc: vi.fn(),
    fill: vi.fn(), fillText: vi.fn(),
    strokeStyle: '', lineWidth: 0, fillStyle: '', font: '', textAlign: '', globalAlpha: 1,
  };
}

class FakeResizeObserver {
  private readonly cb: ResizeObserverCallback;
  constructor(cb: ResizeObserverCallback) { this.cb = cb; }
  observe(target: Element) {
    const entry = { contentRect: { width: 320, height: 600 }, target } as unknown as ResizeObserverEntry;
    this.cb([entry], this as unknown as ResizeObserver);
  }
  unobserve() {}
  disconnect() {}
}

let ctx: ReturnType<typeof makeCtx>;

beforeEach(() => {
  ctx = makeCtx();
  vi.spyOn(HTMLCanvasElement.prototype, 'getContext').mockImplementation(() => ctx as never);
  vi.stubGlobal('ResizeObserver', FakeResizeObserver);
  vi.stubGlobal('requestAnimationFrame', (cb: FrameRequestCallback) => { cb(0); return 1; });
  vi.stubGlobal('cancelAnimationFrame', () => {});
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

// Posição na tela do nó de id dado (mesmo cálculo do componente: espiral + enquadramento inicial)
const screenPos = (vault: MarkdownNode[], id: string) => {
  const { nodes } = buildGraph(vault, 320, 600);
  const cam = fitCamera(nodes, 320, 600);
  const target = nodes.find((n) => n.id === id)!;
  return { x: target.x * cam.scale + cam.x, y: target.y * cam.scale + cam.y };
};

const clickAt = (canvas: HTMLElement, p: { x: number; y: number }) => {
  fireEvent.mouseMove(canvas, { clientX: p.x, clientY: p.y });
  fireEvent.mouseDown(canvas, { clientX: p.x, clientY: p.y });
  fireEvent.mouseUp(canvas, { clientX: p.x, clientY: p.y });
};

const live = (container: HTMLElement) => container.querySelector('[aria-live="polite"]')!.textContent;

const vault = [note('A/x.md'), note('B/y.md')];

describe('ForceGraph: seleção por clique', () => {
  it('a região aria-live começa vazia e é visualmente oculta (sr-only)', () => {
    const { container } = render(<ForceGraph vaultNodes={vault} />);
    const region = container.querySelector('[aria-live="polite"]')!;
    expect(region.textContent).toBe('');
    expect(region.className).toBe('sr-only');
  });

  it('clicar numa nota seleciona e anuncia o nome e as ligações', () => {
    const onOpenNote = vi.fn();
    const { container } = render(<ForceGraph vaultNodes={vault} onOpenNote={onOpenNote} />);
    clickAt(container.querySelector('canvas')!, screenPos(vault, 'A/x.md'));
    expect(live(container)).toBe('Selecionado: x, 1 ligação');
    expect(onOpenNote).toHaveBeenCalledWith('A/x.md');
  });

  it('clicar numa pasta seleciona e anuncia, sem abrir nada', () => {
    const onOpenNote = vi.fn();
    const { container } = render(<ForceGraph vaultNodes={vault} onOpenNote={onOpenNote} />);
    clickAt(container.querySelector('canvas')!, screenPos(vault, 'dir:A'));
    // A tem a raiz (dir:) e a nota x como vizinhos diretos
    expect(live(container)).toBe('Selecionado: A, 2 ligações');
    expect(onOpenNote).not.toHaveBeenCalled();
  });

  it('clique no vazio limpa a seleção', () => {
    const { container } = render(<ForceGraph vaultNodes={vault} />);
    const canvas = container.querySelector('canvas')!;
    clickAt(canvas, screenPos(vault, 'A/x.md'));
    expect(live(container)).not.toBe('');
    clickAt(canvas, { x: -500, y: -500 });
    expect(live(container)).toBe('');
  });

  it('Esc limpa a seleção quando o canvas tem o foco', () => {
    const { container } = render(<ForceGraph vaultNodes={vault} />);
    const canvas = container.querySelector('canvas')!;
    expect(canvas.getAttribute('tabindex')).toBe('0');
    clickAt(canvas, screenPos(vault, 'A/x.md'));
    fireEvent.keyDown(canvas, { key: 'a' });
    expect(live(container)).not.toBe('');
    fireEvent.keyDown(canvas, { key: 'Escape' });
    expect(live(container)).toBe('');
  });

  it('arrastar não seleciona (e não abre a nota)', () => {
    const onOpenNote = vi.fn();
    const { container } = render(<ForceGraph vaultNodes={vault} onOpenNote={onOpenNote} />);
    const canvas = container.querySelector('canvas')!;
    const p = screenPos(vault, 'A/x.md');
    fireEvent.mouseMove(canvas, { clientX: p.x, clientY: p.y });
    fireEvent.mouseDown(canvas, { clientX: p.x, clientY: p.y });
    fireEvent.mouseMove(canvas, { clientX: p.x + 30, clientY: p.y });
    fireEvent.mouseUp(canvas, { clientX: p.x + 30, clientY: p.y });
    expect(live(container)).toBe('');
    expect(onOpenNote).not.toHaveBeenCalled();
  });

  it('ao selecionar, o desenho do frame é refeito com o anel no nó (ver graphDraw.test.ts para o alpha)', () => {
    const { container } = render(<ForceGraph vaultNodes={vault} />);
    const canvas = container.querySelector('canvas')!;
    const arcsBefore = ctx.arc.mock.calls.length;
    clickAt(canvas, screenPos(vault, 'A/x.md'));
    expect(ctx.arc.mock.calls.length).toBeGreaterThan(arcsBefore);
  });
});
