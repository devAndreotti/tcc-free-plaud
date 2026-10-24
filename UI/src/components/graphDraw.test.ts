import { describe, expect, it } from 'vitest';
import type { SimEdge, SimNode } from '../lib/vaultGraph';
import { DIM_ALPHA, selectionSet } from '../lib/graphSelection';
import { drawEdges, drawLabels, drawNodes, type Highlight, type Palette } from './graphDraw';

// Contexto que anota o globalAlpha no momento de cada desenho (arc, stroke, fillText)
function recorder() {
  const arcs: { x: number; y: number; r: number; alpha: number }[] = [];
  const strokes: { alpha: number; segments: number }[] = [];
  const texts: { text: string; alpha: number }[] = [];
  let segments = 0;
  const ctx = {
    globalAlpha: 1, fillStyle: '', strokeStyle: '', lineWidth: 1, font: '', textAlign: '', textBaseline: '',
    beginPath() { segments = 0; },
    moveTo() { segments += 1; },
    lineTo() {},
    stroke() { strokes.push({ alpha: ctx.globalAlpha, segments }); },
    arc(x: number, y: number, r: number) { arcs.push({ x, y, r, alpha: ctx.globalAlpha }); },
    fill() {},
    fillText(text: string) { texts.push({ text, alpha: ctx.globalAlpha }); },
  };
  return { ctx, arcs, strokes, texts };
}

const pal: Palette = {
  edge: '#333', node: '#888', folder: '#66f', label: '#aaa', text: '#fff', hover: '#f0f', link: '#0ff',
  focus: '#0ff', bg: '#000', tipBg: '#111', tipFg: '#eee',
};
const cam = { x: 0, y: 0, scale: 1 };

const node = (id: string, x: number, y: number, kind: SimNode['kind'] = 'note', depth = 1): SimNode => ({
  id, label: id.replace('dir:', ''), kind, depth, x, y, vx: 0, vy: 0, degree: 0,
});

// Raiz (0,0) → A (10,0) → A/x (20,0); raiz → B (-10,0) → B/y (-20,0); ligação A/x ↔ B/y
const nodes = [
  node('dir:', 0, 0, 'folder', 0),
  node('dir:A', 10, 0, 'folder', 1),
  node('A/x', 20, 0),
  node('dir:B', -10, 0, 'folder', 1),
  node('B/y', -20, 0),
];
const edges: SimEdge[] = [
  { source: 'dir:', target: 'dir:A' },
  { source: 'dir:A', target: 'A/x' },
  { source: 'dir:', target: 'dir:B' },
  { source: 'dir:B', target: 'B/y' },
  { source: 'A/x', target: 'B/y', kind: 'link' },
];

// Seleção de A/x = A/x + vizinhos diretos: a pasta A (árvore) e B/y (ligação). Fora: raiz e dir:B.
const hl = (selectedId: string | null): Highlight => ({
  hoveredId: null,
  selectedId,
  sel: selectionSet(selectedId, edges),
  scale: 1,
});

describe('drawNodes: seleção apaga o que está fora da vizinhança', () => {
  it('sem seleção todos os nós saem em alpha cheio e sem anel', () => {
    const rec = recorder();
    drawNodes(rec.ctx as never, nodes, pal, hl(null));
    expect(rec.arcs).toHaveLength(nodes.length);
    expect(rec.arcs.every((a) => a.alpha === 1)).toBe(true);
  });

  it('com A/x selecionado: ele e os vizinhos diretos ficam em alpha 1; o resto recua', () => {
    const rec = recorder();
    drawNodes(rec.ctx as never, nodes, pal, hl('A/x'));
    const alphaOf = (x: number) => rec.arcs.find((a) => a.x === x)!.alpha;
    expect(alphaOf(20)).toBe(1); // A/x (selecionado)
    expect(alphaOf(10)).toBe(1); // dir:A (pai, pela árvore)
    expect(alphaOf(-20)).toBe(1); // B/y (vizinho pela ligação [[...]])
    expect(alphaOf(0)).toBe(DIM_ALPHA); // raiz: não é vizinha de A/x
    expect(alphaOf(-10)).toBe(DIM_ALPHA); // dir:B: não é vizinha de A/x
  });

  it('o selecionado ganha um anel (um arco a mais, com raio maior que o nó, em alpha cheio)', () => {
    const rec = recorder();
    drawNodes(rec.ctx as never, nodes, pal, hl('A/x'));
    const ring = rec.arcs.at(-1)!;
    expect(rec.arcs).toHaveLength(nodes.length + 1);
    expect(ring.x).toBe(20);
    expect(ring.r).toBeGreaterThan(2.6);
    expect(ring.alpha).toBe(1);
  });
});

describe('drawEdges: arestas com as duas pontas na seleção ficam em cor plena', () => {
  it('sem seleção só há passadas em alpha cheio (árvore) e 35% (ligação)', () => {
    const rec = recorder();
    drawEdges(rec.ctx as never, nodes, edges, pal, cam, null);
    expect(rec.strokes.map((s) => s.alpha)).toEqual([1, 0.35]);
  });

  it('com A/x selecionado: árvore e ligação de fora recuam; dir:A→A/x e A/x↔B/y ficam por cima', () => {
    const rec = recorder();
    drawEdges(rec.ctx as never, nodes, edges, pal, cam, selectionSet('A/x', edges));
    // Ordem das passadas: árvore fora, ligação fora, árvore dentro, ligação dentro.
    // Árvore fora: raiz→dir:A, raiz→dir:B, dir:B→B/y (3 trechos). Ligação fora: nenhuma.
    // Árvore dentro: dir:A→A/x (1). Ligação dentro: A/x↔B/y (1).
    expect(rec.strokes.map((s) => s.segments)).toEqual([3, 0, 1, 1]);
    expect(rec.strokes[0].alpha).toBeCloseTo(DIM_ALPHA);
    expect(rec.strokes[1].alpha).toBeCloseTo(0.35 * DIM_ALPHA);
    expect(rec.strokes[2].alpha).toBe(1);
    expect(rec.strokes[3].alpha).toBeCloseTo(0.35);
  });
});

describe('drawLabels: rótulos fora da seleção saem apagados', () => {
  it('com seleção, rótulos fora dela saem em alpha reduzido', () => {
    const rec = recorder();
    drawLabels(rec.ctx as never, nodes, pal, { x: 0, y: 0, scale: 2 }, selectionSet('A/x', edges));
    const alphaOf = (text: string) => rec.texts.find((t) => t.text === text)!.alpha;
    expect(alphaOf('A/x')).toBe(1);
    expect(alphaOf('B/y')).toBe(1);
    expect(alphaOf('B')).toBe(DIM_ALPHA); // dir:B
  });

  it('sem seleção todos os rótulos visíveis saem em alpha cheio', () => {
    const rec = recorder();
    drawLabels(rec.ctx as never, nodes, pal, { x: 0, y: 0, scale: 2 }, null);
    expect(rec.texts.every((t) => t.alpha === 1)).toBe(true);
  });
});
