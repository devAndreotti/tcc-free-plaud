import { afterEach, describe, expect, it, vi } from 'vitest';
import { ENTRY_MS, easeOutCubic, entryAt, prefersReducedMotion, projectNodes, shouldAnimateEntry } from './graphMotion';

describe('easeOutCubic', () => {
  it('vai de 0 a 1, limitado nas bordas, e desacelera no fim', () => {
    expect(easeOutCubic(0)).toBe(0);
    expect(easeOutCubic(1)).toBe(1);
    expect(easeOutCubic(-3)).toBe(0);
    expect(easeOutCubic(9)).toBe(1);
    // ease-out: na metade do tempo já percorreu mais da metade do caminho
    expect(easeOutCubic(0.5)).toBeGreaterThan(0.5);
    expect(easeOutCubic(0.9) - easeOutCubic(0.8)).toBeLessThan(easeOutCubic(0.2) - easeOutCubic(0.1));
  });
});

describe('entryAt: abertura de ENTRY_MS (600 ms)', () => {
  it('começa no centro (0), termina na posição da simulação (1) e fica em 1 depois', () => {
    expect(entryAt(1000, 1000)).toBe(0);
    expect(entryAt(1000, 1000 + ENTRY_MS)).toBe(1);
    expect(entryAt(1000, 1000 + ENTRY_MS * 3)).toBe(1);
    expect(ENTRY_MS).toBe(600);
  });

  it('sem abertura em andamento (null) já está na posição final', () => {
    expect(entryAt(null, 123)).toBe(1);
  });

  it('no meio do caminho do tempo, a fração é a do ease-out', () => {
    expect(entryAt(0, ENTRY_MS / 2)).toBeCloseTo(easeOutCubic(0.5));
  });
});

describe('shouldAnimateEntry: quando reabrir o grafo', () => {
  const ids = ['a', 'b', 'c', 'd'];

  it('primeira carga (nada antes) anima', () => {
    expect(shouldAnimateEntry(new Set(), ids, false)).toBe(true);
  });

  it('trocar de modo anima, mesmo com os mesmos nós', () => {
    expect(shouldAnimateEntry(new Set(ids), ids, true)).toBe(true);
  });

  it('mesmo vault e mesmo modo (ex.: as ligações chegaram depois) não reabrem', () => {
    expect(shouldAnimateEntry(new Set(ids), ids, false)).toBe(false);
  });

  it('um rescan que acrescenta uma nota não reabre o desenho', () => {
    expect(shouldAnimateEntry(new Set(ids), [...ids, 'e'], false)).toBe(false);
  });

  it('trocar de vault (maioria dos nós é nova) reabre', () => {
    expect(shouldAnimateEntry(new Set(ids), ['x', 'y', 'z', 'a'], false)).toBe(true);
  });

  it('sem nós não há o que animar', () => {
    expect(shouldAnimateEntry(new Set(ids), [], true)).toBe(false);
  });
});

describe('projectNodes: escala radial a partir do centro', () => {
  const nodes = [{ id: 'a', x: 100, y: 0 }, { id: 'b', x: 0, y: -50 }];

  it('k = 1 devolve os próprios nós (mesma referência, sem custo)', () => {
    expect(projectNodes(nodes, 0, 0, 1)).toBe(nodes);
  });

  it('k = 0 põe todos no centro', () => {
    expect(projectNodes(nodes, 10, 20, 0)).toEqual([{ id: 'a', x: 10, y: 20 }, { id: 'b', x: 10, y: 20 }]);
  });

  it('k = 0.5 fica na metade do caminho e não altera o original', () => {
    const half = projectNodes(nodes, 0, 0, 0.5);
    expect(half[0]).toEqual({ id: 'a', x: 50, y: 0 });
    expect(half[1]).toEqual({ id: 'b', x: 0, y: -25 });
    expect(nodes[0].x).toBe(100);
  });
});

describe('prefersReducedMotion', () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('sem matchMedia (jsdom) não pede redução', () => {
    expect(prefersReducedMotion()).toBe(false);
  });

  it('respeita prefers-reduced-motion: reduce', () => {
    vi.stubGlobal('matchMedia', (q: string) => ({ matches: q === '(prefers-reduced-motion: reduce)' }));
    expect(prefersReducedMotion()).toBe(true);
  });

  it('sem a preferência, a abertura segue', () => {
    vi.stubGlobal('matchMedia', () => ({ matches: false }));
    expect(prefersReducedMotion()).toBe(false);
  });
});
