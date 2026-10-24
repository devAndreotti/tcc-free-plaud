import { describe, expect, it } from 'vitest';
import type { SimEdge, SimNode } from './vaultGraph';
import {
  CLICK_SLOP,
  edgeInSelection,
  folderSubtreeIds,
  frameCamera,
  hitTest,
  isClick,
  lerpCamera,
  neighborIds,
  selectionAnnouncement,
  selectionSet,
} from './graphSelection';

const node = (id: string, x: number, y: number, kind: SimNode['kind'] = 'note', depth = 1): SimNode => ({
  id, label: id, kind, depth, x, y, vx: 0, vy: 0, degree: 0,
});

// Árvore: raiz → A → (A/x, A/sub → A/sub/y); B → B/z. Ligação A/x ↔ B/z.
const tree: SimEdge[] = [
  { source: 'dir:', target: 'dir:A' },
  { source: 'dir:', target: 'dir:B' },
  { source: 'dir:A', target: 'A/x' },
  { source: 'dir:A', target: 'dir:A/sub' },
  { source: 'dir:A/sub', target: 'A/sub/y' },
  { source: 'dir:B', target: 'B/z' },
  { source: 'A/x', target: 'B/z', kind: 'link' },
];

describe('neighborIds / selectionSet', () => {
  it('vizinhos diretos incluem pai, filhos e ligações, nos dois sentidos', () => {
    expect([...neighborIds('A/x', tree)].sort()).toEqual(['B/z', 'dir:A']);
    expect([...neighborIds('B/z', tree)].sort()).toEqual(['A/x', 'dir:B']);
    expect([...neighborIds('dir:A', tree)].sort()).toEqual(['A/x', 'dir:', 'dir:A/sub']);
  });

  it('não inclui o próprio nó nem vizinhos de segundo grau', () => {
    expect(neighborIds('A/x', tree).has('A/x')).toBe(false);
    expect(neighborIds('A/x', tree).has('dir:')).toBe(false);
  });

  it('selectionSet acrescenta o próprio nó; sem seleção devolve null', () => {
    expect([...selectionSet('A/x', tree)!].sort()).toEqual(['A/x', 'B/z', 'dir:A']);
    expect(selectionSet(null, tree)).toBeNull();
  });

  it('nó sem arestas tem vizinhança vazia', () => {
    expect(neighborIds('solto', tree).size).toBe(0);
    expect([...selectionSet('solto', tree)!]).toEqual(['solto']);
  });

  it('aresta entre dois nós da seleção é destacada; aresta que sai dela não', () => {
    const set = selectionSet('A/x', tree)!;
    const link = tree.find((e) => e.kind === 'link')!;
    expect(edgeInSelection(link, set)).toBe(true);
    expect(edgeInSelection({ source: 'dir:', target: 'dir:A' }, set)).toBe(false);
    expect(edgeInSelection({ source: 'dir:', target: 'dir:A' }, selectionSet('dir:A', tree)!)).toBe(true);
    expect(edgeInSelection({ source: 'dir:A/sub', target: 'A/sub/y' }, set)).toBe(false);
  });
});

describe('hitTest', () => {
  const nodes = [node('a', 0, 0), node('b', 100, 0)];

  it('acha o nó dentro do raio (com folga de 5 px na tela)', () => {
    expect(hitTest(nodes, { x: 0, y: 0 }, 1)?.id).toBe('a');
    expect(hitTest(nodes, { x: 6, y: 0 }, 1)?.id).toBe('a');
    expect(hitTest(nodes, { x: 50, y: 0 }, 1)).toBeNull();
  });

  it('a folga é em pixels de tela: com zoom de 2x o alvo mede menos no mundo', () => {
    expect(hitTest(nodes, { x: 6, y: 0 }, 2)).toBeNull();
    expect(hitTest(nodes, { x: 4, y: 0 }, 2)?.id).toBe('a');
  });

  it('entre dois nós sobrepostos devolve o mais próximo', () => {
    const pair = [node('far', 0, 0), node('near', 2, 0)];
    expect(hitTest(pair, { x: 2.5, y: 0 }, 1)?.id).toBe('near');
  });

  it('lista vazia não acerta nada', () => {
    expect(hitTest([], { x: 0, y: 0 }, 1)).toBeNull();
  });
});

describe('isClick: clique vs arrasto', () => {
  it('sem movimento é clique', () => {
    expect(isClick({ x: 10, y: 10 }, { x: 10, y: 10 })).toBe(true);
  });

  it('movimento menor que o limiar ainda é clique', () => {
    expect(isClick({ x: 0, y: 0 }, { x: CLICK_SLOP - 1, y: 0 })).toBe(true);
  });

  it('a partir do limiar é arrasto (inclusive na diagonal)', () => {
    expect(isClick({ x: 0, y: 0 }, { x: CLICK_SLOP, y: 0 })).toBe(false);
    expect(isClick({ x: 0, y: 0 }, { x: 3, y: 3 })).toBe(false);
  });
});

describe('folderSubtreeIds / frameCamera', () => {
  it('a pasta A contém as subpastas e notas abaixo dela, mas não irmãos', () => {
    const ids = folderSubtreeIds('dir:A', tree);
    expect([...ids].sort()).toEqual(['A/sub/y', 'A/x', 'dir:A', 'dir:A/sub']);
  });

  it('ligações [[...]] não puxam nós de fora da subárvore', () => {
    expect(folderSubtreeIds('dir:B', tree).has('A/x')).toBe(false);
  });

  it('a câmera enquadra só o subconjunto: nós de fora não reduzem o zoom', () => {
    const nodes = [node('dir:A', 0, 0, 'folder', 1), node('A/x', 10, 0), node('B/z', 1000, 1000)];
    const cam = frameCamera(nodes, new Set(['dir:A', 'A/x']), 300, 300);
    const screenX = (x: number) => x * cam.scale + cam.x;
    const screenY = (y: number) => y * cam.scale + cam.y;
    expect(screenX(0)).toBeGreaterThanOrEqual(0);
    expect(screenX(10)).toBeLessThanOrEqual(300);
    expect(screenY(0)).toBeGreaterThanOrEqual(0);
    expect(screenY(0)).toBeLessThanOrEqual(300);
    expect(cam.scale).toBeGreaterThan(1);
  });
});

describe('lerpCamera', () => {
  it('t=0 é a origem, t=1 é o destino, t=0.5 é o meio', () => {
    const a = { x: 0, y: 0, scale: 1 };
    const b = { x: 10, y: -20, scale: 3 };
    expect(lerpCamera(a, b, 0)).toEqual(a);
    expect(lerpCamera(a, b, 1)).toEqual(b);
    expect(lerpCamera(a, b, 0.5)).toEqual({ x: 5, y: -10, scale: 2 });
  });
});

describe('selectionAnnouncement', () => {
  it('anuncia o nome e o número de ligações, no singular e no plural', () => {
    expect(selectionAnnouncement('Arquitetura', 3)).toBe('Selecionado: Arquitetura, 3 ligações');
    expect(selectionAnnouncement('Solta', 1)).toBe('Selecionado: Solta, 1 ligação');
    expect(selectionAnnouncement('Vazia', 0)).toBe('Selecionado: Vazia, 0 ligações');
  });
});
