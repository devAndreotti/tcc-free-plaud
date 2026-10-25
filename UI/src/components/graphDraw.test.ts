import { describe, expect, it } from 'vitest';
import type { SimEdge, SimNode } from '../lib/vaultGraph';
import { DIM_ALPHA, selectionSet } from '../lib/graphSelection';
import { drawEdges, drawLabels, drawNodes, tooltipDetail, type Highlight, type Palette } from './graphDraw';

// Contexto que anota o globalAlpha no momento de cada desenho (arc, stroke, fillText)
function recorder() {
  const arcs: { x: number; y: number; r: number; alpha: number; fill?: string }[] = [];
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
    fill() { const last = arcs.at(-1); if (last) last.fill = ctx.fillStyle; },
    fillText(text: string) { texts.push({ text, alpha: ctx.globalAlpha }); },
    // Largura proporcional ao tamanho da fonte (em unidades de mundo, como o navegador mede): 0,6 em por caractere
    measureText(text: string) {
      const px = parseFloat(/([\d.]+)px/.exec(ctx.font)?.[1] ?? '10');
      return { width: text.length * 0.6 * px, actualBoundingBoxAscent: 0.8 * px, actualBoundingBoxDescent: 0.2 * px };
    },
  };
  return { ctx, arcs, strokes, texts };
}

const pal: Palette = {
  edge: '#333', node: '#888', folder: '#66f', label: '#aaa', text: '#fff', hover: '#f0f', link: '#0ff',
  focus: '#0ff', bg: '#000', tipBg: '#111', tipFg: '#eee',
  groups: ['#g1', '#g2', '#g3', '#g4', '#g5', '#g6', '#g7', '#g8'],
};
const cam = { x: 0, y: 0, scale: 1 };

const node = (id: string, x: number, y: number, kind: SimNode['kind'] = 'note', depth = 1): SimNode => ({
  id, label: id.replace('dir:', ''), kind, depth, group: '', folder: '', colorSlot: null,
  x, y, vx: 0, vy: 0, degree: 0,
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

describe('drawNodes: cor automática por pasta de 1º nível', () => {
  const colored: SimNode[] = [
    { ...node('dir:', 0, 0, 'folder', 0) },
    { ...node('dir:A', 10, 0, 'folder', 1), group: 'A', folder: 'A', colorSlot: 2 },
    { ...node('A/x', 20, 0), group: 'A', folder: 'A', colorSlot: 2 },
    node('solta', 30, 0),
  ];

  it('pasta de 1º nível usa a cor do grupo; a raiz segue a cor de pasta do tema', () => {
    const rec = recorder();
    drawNodes(rec.ctx as never, colored, pal, hl(null));
    expect(rec.arcs[0].fill).toBe(pal.folder); // raiz
    expect(rec.arcs[1].fill).toBe('#g3'); // dir:A, slot 2 → groups[2]
    expect(rec.arcs[1].alpha).toBe(1);
  });

  it('nota herda a cor da pasta com menos opacidade; nota sem grupo fica no cinza do tema', () => {
    const rec = recorder();
    drawNodes(rec.ctx as never, colored, pal, hl(null));
    expect(rec.arcs[2].fill).toBe('#g3');
    expect(rec.arcs[2].alpha).toBeCloseTo(0.75);
    expect(rec.arcs[3].fill).toBe(pal.node);
    expect(rec.arcs[3].alpha).toBe(1);
  });

  it('hover volta a nota para cor cheia (o destaque do hover vence a cor da pasta)', () => {
    const rec = recorder();
    drawNodes(rec.ctx as never, colored, pal, { ...hl(null), hoveredId: 'A/x' });
    expect(rec.arcs[2].fill).toBe(pal.hover);
    expect(rec.arcs[2].alpha).toBe(1);
  });
});

describe('tooltipDetail: a pasta aparece em texto, não só na cor', () => {
  it('pasta mostra o próprio caminho; a raiz diz que é a raiz', () => {
    expect(tooltipDetail({ ...node('dir:A/B', 0, 0, 'folder', 2), folder: 'A/B' })).toBe('Pasta: A/B');
    expect(tooltipDetail(node('dir:', 0, 0, 'folder', 0))).toBe('Raiz do vault');
  });

  it('nota mostra a pasta que a contém; na raiz diz isso', () => {
    expect(tooltipDetail({ ...node('n', 0, 0), folder: 'Estudos/Cisco' })).toBe('Pasta: Estudos/Cisco');
    expect(tooltipDetail(node('n', 0, 0))).toBe('Na raiz do vault');
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

describe('drawLabels: com seleção, só o selecionado e os vizinhos têm nome', () => {
  it('rótulos fora da seleção não são desenhados', () => {
    const rec = recorder();
    drawLabels(rec.ctx as never, nodes, pal, { x: 0, y: 0, scale: 2 }, selectionSet('A/x', edges));
    const alphaOf = (text: string) => rec.texts.find((t) => t.text === text)?.alpha;
    expect(alphaOf('A/x')).toBe(1);
    expect(alphaOf('B/y')).toBe(1);
    expect(alphaOf('B')).toBeUndefined(); // dir:B fica como fundo, sem nome
  });

  it('com seleção, o selecionado tem nome em qualquer zoom; vizinhos só se couberem sem colidir', () => {
    const rec = recorder();
    drawLabels(rec.ctx as never, nodes, pal, { x: 0, y: 0, scale: 0.3 }, selectionSet('A/x', edges), 'A/x');
    // Com zoom baixo, 'A' (pai), 'A/x' e 'B/y' ficam a poucos px uns dos outros: o selecionado é desenhado
    // primeiro e os vizinhos que sobrepõem seu rótulo são pulados. Raiz e dir:B ficam ocultas.
    expect(rec.texts.map((t) => t.text)).toEqual(['A/x']);
  });

  it('o selecionado ganha nome mesmo quando um vizinho está logo ao lado (regressão: a pasta selecionada sob o vizinho)', () => {
    const rec = recorder();
    // Pasta selecionada e uma nota vizinha no mesmo ponto; a nota vem primeiro na lista
    const scene: SimNode[] = [node('Nota', 100, 100, 'note', 1), node('dir:A', 100.5, 100, 'folder', 1)];
    const sceneEdges: SimEdge[] = [{ source: 'dir:A', target: 'Nota' }];
    drawLabels(rec.ctx as never, scene, pal, cam, selectionSet('dir:A', sceneEdges), 'dir:A');
    expect(rec.texts.map((t) => t.text)).toEqual(['A']);
  });

  it('sem seleção, a pasta vence a nota quando os rótulos colidem (pasta antes de nota)', () => {
    const rec = recorder();
    // Nota e pasta a 1 px uma da outra; com zoom 2 as duas são visíveis, então só a prioridade decide
    const scene: SimNode[] = [node('solo', 100, 100, 'note', 1), node('dir:A', 100.5, 100, 'folder', 1)];
    drawLabels(rec.ctx as never, scene, pal, { x: 0, y: 0, scale: 2 }, null, null);
    expect(rec.texts.map((t) => t.text)).toEqual(['A']);
  });

  it('pasta mais rasa vence a mais funda quando colidem (sem seleção)', () => {
    const rec = recorder();
    const scene: SimNode[] = [node('dir:X/Y', 100.5, 100, 'folder', 2), node('dir:X', 100, 100, 'folder', 1)];
    drawLabels(rec.ctx as never, scene, pal, { x: 0, y: 0, scale: 1 }, null, null);
    expect(rec.texts.map((t) => t.text)).toEqual(['X']);
  });

  it('a colisão é medida em tela: a mesma distância no mundo colide com zoom baixo e não com zoom alto', () => {
    // Duas pastas de 1º nível a 6 unidades de mundo. Largura de 1 letra: 6,6 px em qualquer zoom.
    const pair: SimNode[] = [node('dir:A', 0, 0, 'folder', 1), node('dir:B', 6, 0, 'folder', 1)];
    const low = recorder();
    drawLabels(low.ctx as never, pair, pal, { x: 0, y: 0, scale: 1 }, null, null); // 6 px entre centros: colide
    expect(low.texts.map((t) => t.text)).toEqual(['A']);
    const high = recorder();
    drawLabels(high.ctx as never, pair, pal, { x: 0, y: 0, scale: 2 }, null, null); // 12 px entre centros: cabe
    expect(high.texts.map((t) => t.text)).toEqual(['A', 'B']);
  });

  it('mede o rótulo com o ctx (largura em tela = medida × scale)', () => {
    const rec = recorder();
    const seen: string[] = [];
    const ctx = Object.assign(rec.ctx, {
      measureText(text: string) { seen.push(text); return { width: 10, actualBoundingBoxAscent: 8, actualBoundingBoxDescent: 2 }; },
    });
    drawLabels(ctx as never, [node('dir:A', 0, 0, 'folder', 1)], pal, { x: 0, y: 0, scale: 1 }, null, null);
    expect(seen).toEqual(['A']);
  });

  it('sem seleção, zoom baixo não mostra nenhum rótulo de nota ou pasta', () => {
    const rec = recorder();
    drawLabels(rec.ctx as never, nodes, pal, { x: 0, y: 0, scale: 0.3 }, null);
    expect(rec.texts).toHaveLength(0);
  });

  it('sem seleção todos os rótulos visíveis saem em alpha cheio', () => {
    const rec = recorder();
    drawLabels(rec.ctx as never, nodes, pal, { x: 0, y: 0, scale: 2 }, null);
    expect(rec.texts.every((t) => t.alpha === 1)).toBe(true);
  });
});
