import { act, render } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { MarkdownNode } from '../lib/vaultGraph';
import { GRAPH_FOCUS_EVENT } from '../lib/vaultGraph';
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

function makeCtx() {
  return {
    clearRect: vi.fn(), save: vi.fn(), restore: vi.fn(), scale: vi.fn(), translate: vi.fn(),
    beginPath: vi.fn(), moveTo: vi.fn(), lineTo: vi.fn(), stroke: vi.fn(), arc: vi.fn(),
    fill: vi.fn(), fillText: vi.fn(), strokeText: vi.fn(), roundRect: vi.fn(),
    measureText: vi.fn(() => ({ width: 40 })),
    strokeStyle: '', lineWidth: 0, fillStyle: '', font: '', textAlign: '', textBaseline: '', lineJoin: '',
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

describe('ForceGraph: nota em foco vinda do chat', () => {
  it('evento de foco desenha o caminho até a raiz com a pílula do nome da nota', () => {
    render(<ForceGraph vaultNodes={[note('A/x.md'), note('B/y.md')]} />);
    ctx.roundRect.mockClear();
    act(() => {
      window.dispatchEvent(new CustomEvent(GRAPH_FOCUS_EVENT, { detail: 'A/x.md' }));
    });
    expect(ctx.roundRect).toHaveBeenCalled();
    expect(ctx.strokeText).toHaveBeenCalledWith('A', expect.any(Number), expect.any(Number));
    expect(ctx.fillText).toHaveBeenCalledWith('x', expect.any(Number), expect.any(Number));
  });

  it('foco com id desconhecido e foco nulo não quebram', () => {
    render(<ForceGraph vaultNodes={[note('A/x.md')]} />);
    ctx.roundRect.mockClear();
    act(() => {
      window.dispatchEvent(new CustomEvent(GRAPH_FOCUS_EVENT, { detail: 'nao-existe.md' }));
      window.dispatchEvent(new CustomEvent(GRAPH_FOCUS_EVENT, { detail: null }));
    });
    expect(ctx.roundRect).not.toHaveBeenCalled();
  });
});
