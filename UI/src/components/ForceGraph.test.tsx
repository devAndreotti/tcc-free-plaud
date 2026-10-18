import { act, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { MarkdownNode } from '../lib/vaultGraph';
import { buildGraph, fitCamera } from '../lib/vaultGraph';
import ForceGraph from './ForceGraph';

// Sem a simulação, as posições são só a espiral determinística de buildGraph:
// assim o teste acha o nó exato para passar o mouse por cima dele.
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
    strokeStyle: '', lineWidth: 0, fillStyle: '', font: '', textAlign: '',
  };
}

// ResizeObserver que entrega imediatamente um painel 320×600
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
  document.documentElement.removeAttribute('data-theme');
});

describe('ForceGraph', () => {
  it('sem notas mostra o estado vazio e não desenha', () => {
    render(<ForceGraph vaultNodes={[]} />);
    expect(screen.getByText('Nenhuma nota indexada nesta vault. Indexe uma pasta na Fila.')).toBeTruthy();
    expect(ctx.arc).not.toHaveBeenCalled();
  });

  it('com notas de 2 pastas desenha os nós e rotula as pastas', () => {
    render(<ForceGraph vaultNodes={[note('A/x.md'), note('B/y.md')]} />);
    expect(ctx.arc).toHaveBeenCalled();
    const labels = ctx.fillText.mock.calls.map((c) => c[0]);
    expect(labels).toEqual(expect.arrayContaining(['A', 'B']));
  });

  it('scroll, arrastar, duplo clique e sair do canvas não quebram e redesenham', async () => {
    const { container } = render(<ForceGraph vaultNodes={[note('A/x.md'), note('B/y.md')]} />);
    const canvas = container.querySelector('canvas')!;
    const redraws = () => ctx.clearRect.mock.calls.length;

    let before = redraws();
    fireEvent.wheel(canvas, { deltaY: -100, clientX: 50, clientY: 50 });
    expect(redraws()).toBeGreaterThan(before);

    before = redraws();
    fireEvent.wheel(canvas, { deltaY: 100, clientX: 50, clientY: 50 });
    expect(redraws()).toBeGreaterThan(before);

    before = redraws();
    fireEvent.mouseDown(canvas, { clientX: 10, clientY: 10 });
    fireEvent.mouseMove(canvas, { clientX: 30, clientY: 40 });
    fireEvent.mouseUp(canvas);
    expect(redraws()).toBeGreaterThan(before);

    before = redraws();
    fireEvent.doubleClick(canvas);
    expect(redraws()).toBeGreaterThan(before);

    before = redraws();
    fireEvent.mouseLeave(canvas);
    expect(redraws()).toBeGreaterThanOrEqual(before);

    // Trocar o tema redesenha pelo MutationObserver
    before = redraws();
    await act(async () => { document.documentElement.setAttribute('data-theme', 'dark'); });
    expect(redraws()).toBeGreaterThan(before);
  });

  it('mousemove sobre um nó mostra o tooltip com o nome da nota e some ao sair dele', () => {
    const vault = [note('solo.md')];
    const { container } = render(<ForceGraph vaultNodes={vault} />);
    const canvas = container.querySelector('canvas')!;

    // Mesmo cálculo do componente: espiral determinística + enquadramento inicial (dpr 1, rect zerado)
    const { nodes } = buildGraph(vault, 320, 600);
    const cam = fitCamera(nodes, 320, 600);
    const target = nodes.find((n) => n.kind === 'note')!;
    fireEvent.mouseMove(canvas, { clientX: target.x * cam.scale + cam.x, clientY: target.y * cam.scale + cam.y });
    expect(screen.getByText('solo')).toBeTruthy();

    fireEvent.mouseMove(canvas, { clientX: 0, clientY: 0 });
    expect(screen.queryByText('solo')).toBeNull();
  });

  // Posição na tela do nó de id dado (mesmo cálculo do tooltip acima)
  const screenPos = (vault: MarkdownNode[], id: string) => {
    const { nodes } = buildGraph(vault, 320, 600);
    const cam = fitCamera(nodes, 320, 600);
    const target = nodes.find((n) => n.id === id)!;
    return { x: target.x * cam.scale + cam.x, y: target.y * cam.scale + cam.y };
  };

  it('regressao: clique sem arrastar num nó de nota chama onOpenNote com o note_id', () => {
    const vault = [note('A/x.md'), note('B/y.md')];
    const onOpenNote = vi.fn();
    const { container } = render(<ForceGraph vaultNodes={vault} onOpenNote={onOpenNote} />);
    const canvas = container.querySelector('canvas')!;
    const p = screenPos(vault, 'A/x.md');

    fireEvent.mouseMove(canvas, { clientX: p.x, clientY: p.y });
    fireEvent.mouseDown(canvas, { clientX: p.x, clientY: p.y });
    fireEvent.mouseUp(canvas, { clientX: p.x, clientY: p.y });
    expect(onOpenNote).toHaveBeenCalledTimes(1);
    expect(onOpenNote).toHaveBeenCalledWith('A/x.md');
  });

  it('regressao: arrastar a partir de um nó de nota não abre a nota', () => {
    const vault = [note('A/x.md'), note('B/y.md')];
    const onOpenNote = vi.fn();
    const { container } = render(<ForceGraph vaultNodes={vault} onOpenNote={onOpenNote} />);
    const canvas = container.querySelector('canvas')!;
    const p = screenPos(vault, 'A/x.md');

    fireEvent.mouseMove(canvas, { clientX: p.x, clientY: p.y });
    fireEvent.mouseDown(canvas, { clientX: p.x, clientY: p.y });
    fireEvent.mouseMove(canvas, { clientX: p.x + 30, clientY: p.y });
    fireEvent.mouseUp(canvas, { clientX: p.x + 30, clientY: p.y });
    expect(onOpenNote).not.toHaveBeenCalled();
  });

  it('regressao: clique em pasta não chama onOpenNote', () => {
    const vault = [note('A/x.md'), note('B/y.md')];
    const onOpenNote = vi.fn();
    const { container } = render(<ForceGraph vaultNodes={vault} onOpenNote={onOpenNote} />);
    const canvas = container.querySelector('canvas')!;
    const p = screenPos(vault, 'dir:A');

    fireEvent.mouseMove(canvas, { clientX: p.x, clientY: p.y });
    fireEvent.mouseDown(canvas, { clientX: p.x, clientY: p.y });
    fireEvent.mouseUp(canvas, { clientX: p.x, clientY: p.y });
    expect(onOpenNote).not.toHaveBeenCalled();
  });

  it('regressao: sem onOpenNote, clicar numa nota não quebra', () => {
    const vault = [note('A/x.md')];
    const { container } = render(<ForceGraph vaultNodes={vault} />);
    const canvas = container.querySelector('canvas')!;
    const p = screenPos(vault, 'A/x.md');
    fireEvent.mouseDown(canvas, { clientX: p.x, clientY: p.y });
    expect(() => fireEvent.mouseUp(canvas, { clientX: p.x, clientY: p.y })).not.toThrow();
  });
});
