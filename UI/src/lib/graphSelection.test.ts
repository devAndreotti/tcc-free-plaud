import { describe, expect, it } from 'vitest';
import type { SimEdge, SimNode } from './vaultGraph';
import {
  CLICK_SLOP,
  arrowDirection,
  edgeInSelection,
  folderSubtreeIds,
  frameCamera,
  hitTest,
  isClick,
  lerpCamera,
  nearestInDirection,
  nearestToPoint,
  neighborIds,
  selectionAnnouncement,
  selectionSet,
} from './graphSelection';

const node = (id: string, x: number, y: number, kind: SimNode['kind'] = 'note', depth = 1): SimNode => ({
  id, label: id, kind, depth, group: '', folder: '', colorSlot: null, x, y, vx: 0, vy: 0, degree: 0,
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

describe('arrowDirection', () => {
  it('mapeia as quatro setas e ignora as demais teclas', () => {
    expect(arrowDirection('ArrowUp')).toBe('up');
    expect(arrowDirection('ArrowDown')).toBe('down');
    expect(arrowDirection('ArrowLeft')).toBe('left');
    expect(arrowDirection('ArrowRight')).toBe('right');
    expect(arrowDirection('Enter')).toBeNull();
    expect(arrowDirection('constructor')).toBeNull();
  });
});

describe('nearestInDirection: a seta vai ao vizinho mais próximo à frente', () => {
  // Y cresce para baixo (tela). Origem no centro, vizinhos em volta
  const pt = (id: string, x: number, y: number) => ({ id, x, y });
  const grid = [
    pt('c', 0, 0),
    pt('dir', 100, 0),      // à direita, em linha
    pt('far', 300, 0),      // à direita, mais longe
    pt('diag', 60, 60),     // 45° para baixo-direita: ainda no cone de 60°
    pt('side', 10, 200),    // quase abaixo: fora do cone para a direita
    pt('left', -50, 0),
    pt('up', 0, -80),
  ];

  it('direita escolhe o mais perto dentro do cone (não o "far" nem o "side")', () => {
    // dir (100) < diag (~85 de distância)? diag está a 84,8 e dir a 100: diag é mais perto e está no cone
    expect(nearestInDirection(grid, 'c', 'right')?.id).toBe('diag');
  });

  it('esquerda, cima e baixo acham o nó da própria direção', () => {
    expect(nearestInDirection(grid, 'c', 'left')?.id).toBe('left');
    expect(nearestInDirection(grid, 'c', 'up')?.id).toBe('up');
    // Para baixo: 'diag' (a 45°, a ~85 px) vence 'side' (quase vertical, a 200 px)
    expect(nearestInDirection(grid, 'c', 'down')?.id).toBe('diag');
  });

  it('não volta para o próprio nó e devolve null quando não há nada naquela direção', () => {
    const lone = [pt('a', 0, 0), pt('b', -10, 0)];
    expect(nearestInDirection(lone, 'a', 'right')).toBeNull();
    expect(nearestInDirection(lone, 'a', 'up')).toBeNull();
  });

  it('nó ao lado (fora do cone de 60°) não conta como "à direita"', () => {
    const onlySide = [pt('a', 0, 0), pt('s', 10, 100)];
    expect(nearestInDirection(onlySide, 'a', 'right')).toBeNull();
    expect(nearestInDirection(onlySide, 'a', 'down')?.id).toBe('s');
  });

  it('nós sobrepostos ao de partida não formam direção; id inexistente devolve null', () => {
    const stacked = [pt('a', 5, 5), pt('twin', 5, 5), pt('b', 50, 5)];
    expect(nearestInDirection(stacked, 'a', 'right')?.id).toBe('b');
    expect(nearestInDirection(stacked, 'nao-existe', 'right')).toBeNull();
  });

  it('a partir de um nó, andar para a direita e voltar pela esquerda reencontra o mesmo caminho', () => {
    const row = [pt('p', 0, 0), pt('q', 40, 0), pt('r', 90, 0)];
    expect(nearestInDirection(row, 'p', 'right')?.id).toBe('q');
    expect(nearestInDirection(row, 'q', 'right')?.id).toBe('r');
    expect(nearestInDirection(row, 'r', 'left')?.id).toBe('q');
  });
});

describe('nearestToPoint', () => {
  it('devolve o nó mais perto do ponto (ponto de partida sem seleção)', () => {
    const pt2 = (id: string, x: number, y: number) => ({ id, x, y });
    const nodes = [pt2('a', 0, 0), pt2('b', 30, 30), pt2('c', 200, 200)];
    expect(nearestToPoint(nodes, { x: 25, y: 25 })?.id).toBe('b');
    expect(nearestToPoint([], { x: 0, y: 0 })).toBeNull();
  });
});
