import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { MarkdownNode } from '../lib/vaultGraph';
import { buildGraph, fitCamera } from '../lib/vaultGraph';
import ForceGraph from './ForceGraph';

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
  vi.spyOn(HTMLCanvasElement.prototype, 'getContext').mockImplementation(() => ({
    clearRect() {}, save() {}, restore() {}, scale() {}, translate() {}, beginPath() {}, moveTo() {},
    lineTo() {}, stroke() {}, arc() {}, fill() {}, fillText() {}, measureText: () => ({ width: 10 }),
    roundRect() {}, strokeText() {},
  } as never));
  vi.stubGlobal('ResizeObserver', FakeResizeObserver);
  vi.stubGlobal('requestAnimationFrame', (cb: FrameRequestCallback) => { cb(0); return 1; });
  vi.stubGlobal('cancelAnimationFrame', () => {});
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

const vault = [note('Estudos/Cisco/x.md'), note('Pessoas/ana.md'), note('solta.md')];

// Posição na tela de um nó (mesmo cálculo do componente)
const screenPos = (id: string) => {
  const { nodes } = buildGraph(vault, 320, 600);
  const cam = fitCamera(nodes, 320, 600);
  const target = nodes.find((n) => n.id === id)!;
  return { x: target.x * cam.scale + cam.x, y: target.y * cam.scale + cam.y };
};

describe('ForceGraph: legenda das pastas de 1º nível', () => {
  it('no modo Ambos a legenda aparece, fechada, com o total de pastas', () => {
    render(<ForceGraph vaultNodes={vault} mode="ambos" />);
    const toggle = screen.getByRole('button', { name: /Pastas/ });
    expect(toggle.getAttribute('aria-expanded')).toBe('false');
    expect(screen.queryByText('Estudos')).toBeNull();
    expect(toggle.textContent).toContain('2');
  });

  it('abrir a legenda lista as pastas de 1º nível em ordem', () => {
    render(<ForceGraph vaultNodes={vault} mode="pastas" />);
    fireEvent.click(screen.getByRole('button', { name: /Pastas/ }));
    expect(screen.getByText('Estudos')).toBeTruthy();
    expect(screen.getByText('Pessoas')).toBeTruthy();
    expect(screen.getByRole('button', { name: /Pastas/ }).getAttribute('aria-expanded')).toBe('true');
  });

  it('no modo Links não há legenda (não há pastas no desenho)', () => {
    render(<ForceGraph vaultNodes={vault} mode="links" />);
    expect(screen.queryByRole('button', { name: /Pastas/ })).toBeNull();
  });

  it('sem notas não há legenda', () => {
    render(<ForceGraph vaultNodes={[]} mode="ambos" />);
    expect(screen.queryByRole('button', { name: /Pastas/ })).toBeNull();
  });
});

describe('ForceGraph: tooltip mostra a pasta em texto', () => {
  it('passar o mouse numa nota mostra a pasta que a contém', () => {
    const { container } = render(<ForceGraph vaultNodes={vault} />);
    const canvas = container.querySelector('canvas')!;
    const p = screenPos('Estudos/Cisco/x.md');
    fireEvent.mouseMove(canvas, { clientX: p.x, clientY: p.y });
    expect(screen.getByText('x')).toBeTruthy();
    expect(screen.getByText('Pasta: Estudos/Cisco')).toBeTruthy();
  });

  it('passar o mouse numa nota da raiz diz que ela está na raiz', () => {
    const { container } = render(<ForceGraph vaultNodes={vault} />);
    const canvas = container.querySelector('canvas')!;
    const p = screenPos('solta.md');
    fireEvent.mouseMove(canvas, { clientX: p.x, clientY: p.y });
    expect(screen.getByText('Na raiz do vault')).toBeTruthy();
  });
});
