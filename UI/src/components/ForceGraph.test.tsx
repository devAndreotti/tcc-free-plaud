import { act, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { MarkdownNode } from '../lib/vaultGraph';
import { buildGraph, fitCamera } from '../lib/vaultGraph';
import { nearestInDirection, nearestToPoint, neighborIds, selectionAnnouncement } from '../lib/graphSelection';
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

  it('zoom pela roda não é passivo: o preventDefault da página vale', () => {
    const { container } = render(<ForceGraph vaultNodes={[note('A/x.md')]} />);
    const canvas = container.querySelector('canvas')!;
    const wheel = new WheelEvent('wheel', { deltaY: -100, clientX: 50, clientY: 50, cancelable: true });
    canvas.dispatchEvent(wheel);
    expect(wheel.defaultPrevented).toBe(true);
  });
});

// Teclado do canvas: setas, Enter, Home, Esc e o texto de ajuda (sr-only)
describe('ForceGraph: teclado', () => {
  const vault = [note('A/x.md'), note('B/y.md')];
  // Mesmo cálculo do componente com o painel 320×600 (a câmera enquadra o grafo inteiro)
  const scene = () => {
    const { nodes, edges } = buildGraph(vault, 320, 600);
    const cam = fitCamera(nodes, 320, 600);
    return { nodes, edges, cam };
  };
  const live = (container: HTMLElement) => container.querySelector('[aria-live="polite"]')!.textContent;
  const screenPos = (id: string) => {
    const { nodes, cam } = scene();
    const target = nodes.find((n) => n.id === id)!;
    return { x: target.x * cam.scale + cam.x, y: target.y * cam.scale + cam.y };
  };

  it('o canvas liga a ajuda de teclas (sr-only) por aria-describedby, com setas, Enter, Home, Esc e Tab', () => {
    const { container } = render(<ForceGraph vaultNodes={vault} />);
    const canvas = container.querySelector('canvas')!;
    const help = document.getElementById(canvas.getAttribute('aria-describedby')!);
    expect(help?.classList.contains('sr-only')).toBe(true);
    for (const word of ['setas', 'Enter', 'Home', 'Esc', 'Tab']) expect(help?.textContent).toContain(word);
  });

  it('Tab não é interceptado: o navegador leva o foco para fora do canvas', () => {
    const { container } = render(<ForceGraph vaultNodes={vault} />);
    const canvas = container.querySelector('canvas')!;
    expect(fireEvent.keyDown(canvas, { key: 'Tab' })).toBe(true); // true = não foi cancelado
  });

  it('a primeira seta escolhe o nó mais perto do centro; a seguinte anda para o vizinho na direção', () => {
    const { container } = render(<ForceGraph vaultNodes={vault} />);
    const canvas = container.querySelector('canvas')!;
    const { nodes, edges, cam } = scene();

    fireEvent.keyDown(canvas, { key: 'ArrowRight' });
    const center = { x: (160 - cam.x) / cam.scale, y: (300 - cam.y) / cam.scale };
    const first = nearestToPoint(nodes, center)!;
    expect(live(container)).toBe(selectionAnnouncement(first.label, neighborIds(first.id, edges).size));

    fireEvent.keyDown(canvas, { key: 'ArrowRight' });
    const next = nearestInDirection(nodes, first.id, 'right');
    expect(next).not.toBeNull(); // o cenário tem vizinho à direita
    expect(live(container)).toBe(selectionAnnouncement(next!.label, neighborIds(next!.id, edges).size));
  });

  it('seta sem nó na direção mantém a seleção e anuncia que não há nada ali', () => {
    // Com dois nós (a raiz e a nota), só a direção da outra ponta tem vizinho; nas demais não há nada
    const solo = [note('solo.md')];
    const { container } = render(<ForceGraph vaultNodes={solo} />);
    const canvas = container.querySelector('canvas')!;
    const { nodes, edges, cam } = (() => {
      const g = buildGraph(solo, 320, 600);
      return { ...g, cam: fitCamera(g.nodes, 320, 600) };
    })();
    fireEvent.keyDown(canvas, { key: 'ArrowRight' });
    const first = nearestToPoint(nodes, { x: (160 - cam.x) / cam.scale, y: (300 - cam.y) / cam.scale })!;
    expect(live(container)).toBe(selectionAnnouncement(first.label, neighborIds(first.id, edges).size));

    const KEY = { up: 'ArrowUp', down: 'ArrowDown', left: 'ArrowLeft', right: 'ArrowRight' } as const;
    const dir = (Object.keys(KEY) as (keyof typeof KEY)[]).find((d) => nearestInDirection(nodes, first.id, d) === null);
    expect(dir).toBeDefined();
    fireEvent.keyDown(canvas, { key: KEY[dir!] });
    expect(live(container)).toBe('Nenhum nó nessa direção');
  });

  it('Enter sem seleção só anuncia; Enter numa nota selecionada a abre de novo', () => {
    const onOpenNote = vi.fn();
    const { container } = render(<ForceGraph vaultNodes={vault} onOpenNote={onOpenNote} />);
    const canvas = container.querySelector('canvas')!;

    fireEvent.keyDown(canvas, { key: 'Enter' });
    expect(onOpenNote).not.toHaveBeenCalled();
    expect(live(container)).toBe('Nenhum nó selecionado: use as setas para escolher um');

    // Clique numa nota já a seleciona e abre (1ª chamada); Enter abre a mesma nota de novo
    const p = screenPos('A/x.md');
    fireEvent.mouseMove(canvas, { clientX: p.x, clientY: p.y });
    fireEvent.mouseDown(canvas, { clientX: p.x, clientY: p.y });
    fireEvent.mouseUp(canvas, { clientX: p.x, clientY: p.y });
    expect(onOpenNote).toHaveBeenCalledTimes(1);

    fireEvent.keyDown(canvas, { key: 'Enter' });
    expect(onOpenNote).toHaveBeenCalledTimes(2);
    expect(onOpenNote).toHaveBeenLastCalledWith('A/x.md');
  });

  it('Enter numa pasta selecionada enquadra a pasta e não abre nota', () => {
    const onOpenNote = vi.fn();
    const { container } = render(<ForceGraph vaultNodes={vault} onOpenNote={onOpenNote} />);
    const canvas = container.querySelector('canvas')!;
    const p = screenPos('dir:A');
    fireEvent.mouseDown(canvas, { clientX: p.x, clientY: p.y });
    fireEvent.mouseUp(canvas, { clientX: p.x, clientY: p.y });
    expect(onOpenNote).not.toHaveBeenCalled();

    fireEvent.keyDown(canvas, { key: 'Enter' });
    expect(onOpenNote).not.toHaveBeenCalled();
    expect(live(container)).toBe('Pasta enquadrada: A');
  });

  it('Esc limpa a seleção feita pelo teclado; Home enquadra o grafo inteiro depois de um zoom', () => {
    const { container } = render(<ForceGraph vaultNodes={vault} />);
    const canvas = container.querySelector('canvas')!;

    fireEvent.keyDown(canvas, { key: 'ArrowRight' });
    expect(live(container)).toMatch(/^Selecionado: /);
    fireEvent.keyDown(canvas, { key: 'Escape' });
    expect(live(container)).toBe('');

    fireEvent.wheel(canvas, { deltaY: -100, clientX: 50, clientY: 50 });
    fireEvent.keyDown(canvas, { key: 'Home' });
    expect(live(container)).toBe('Grafo inteiro enquadrado');
  });
});
