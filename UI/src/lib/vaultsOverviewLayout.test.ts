import { describe, expect, it } from 'vitest';
import type { VaultOverview } from '../services/bridge';
import { buildOverviewLayout, MAX_ZOOM, NO_ZOOM, searchOverview, VIEW_H, VIEW_W, zoomAt } from './vaultsOverviewLayout';

const vault = (id: string, name: string, folders: Record<string, string[]>, color = 'teal') => {
  const notes = Object.entries(folders).flatMap(([folder, titles]) => titles.map((title) => ({ id: `${id}-${title}`, title, folder })));
  return {
    id, name, icon: 'notes', color, note_count: notes.length, chunk_count: notes.length * 5,
    folders: Object.entries(folders).map(([nome, titles]) => ({ name: nome, count: titles.length })),
    notes,
  } as unknown as VaultOverview;
};

const GRANDE = vault('o', 'Obsidian', { TI: Array.from({ length: 400 }, (_, i) => `Nota ${i}`), Xadrez: ['Aberturas', 'Finais'] }, 'rose');
const DEMO = vault('d', 'Demo', { '': ['Estudo Docker', 'Contrato'] });

describe('buildOverviewLayout', () => {
  it('fechado: só as vaults e nenhuma nota', () => {
    const l = buildOverviewLayout([DEMO, GRANDE], null, null);
    expect(l.vaults).toHaveLength(2);
    expect(l.dots).toHaveLength(0);
    expect(l.vaults.some((n) => n.dim)).toBe(false);
  });

  it('aberta: todas as notas entram, dentro do desenho, e a outra vault apaga', () => {
    const l = buildOverviewLayout([DEMO, GRANDE], 'o', null);
    expect(l.dots).toHaveLength(402);
    expect(l.folders.map((f) => f.name)).toEqual(['TI', 'Xadrez']);
    expect(l.dots.every((d) => d.x >= 0 && d.x <= VIEW_W && d.y >= 0 && d.y <= VIEW_H)).toBe(true);
    expect(l.vaults.find((n) => n.vault.id === 'd')?.dim).toBe(true);
    expect(l.vaults.find((n) => n.vault.id === 'o')?.dim).toBe(false);
  });

  it('a mesma nota fica sempre no mesmo lugar', () => {
    const a = buildOverviewLayout([DEMO, GRANDE], 'o', null).dots[10];
    const b = buildOverviewLayout([DEMO, GRANDE], 'o', null).dots[10];
    expect([a.x, a.y]).toEqual([b.x, b.y]);
  });

  it('notas na raiz da vault não criam nó de pasta', () => {
    const l = buildOverviewLayout([DEMO], 'd', null);
    expect(l.folders).toHaveLength(0);
    expect(l.dots).toHaveLength(2);
  });
});

describe('searchOverview', () => {
  it('acha por título e por pasta em todas as vaults, sem diferenciar maiúsculas', () => {
    expect(searchOverview([DEMO, GRANDE], 'docker').map((h) => h.vaultName)).toEqual(['Demo']);
    expect(searchOverview([DEMO, GRANDE], 'XADREZ')).toHaveLength(2);
    expect(searchOverview([DEMO, GRANDE], '   ')).toEqual([]);
  });

  it('a busca acende só o que achou e apaga a vault sem resultado', () => {
    const hits = searchOverview([DEMO, GRANDE], 'aberturas');
    const l = buildOverviewLayout([DEMO, GRANDE], null, hits);
    expect(l.dots.filter((d) => !d.dim).map((d) => d.note.title)).toEqual(['Aberturas']);
    expect(l.vaults.find((n) => n.vault.id === 'd')?.dim).toBe(true);
  });
});

describe('zoomAt', () => {
  it('o ponto sob o mouse fica parado ao aproximar e ao afastar', () => {
    const world = (v: { x: number; y: number; k: number }) => [(300 - v.x) / v.k, (200 - v.y) / v.k];
    const perto = zoomAt(NO_ZOOM, 300, 200, 2);
    expect(perto.k).toBe(2);
    expect(world(perto)).toEqual(world(NO_ZOOM));
    const meio = zoomAt(perto, 300, 200, 0.75);
    expect(world(meio).map((n) => Math.round(n * 1e6) / 1e6)).toEqual(world(NO_ZOOM));
  });

  it('não passa do teto nem fica abaixo do desenho inteiro', () => {
    expect(zoomAt({ x: -900, y: -900, k: 4.9 }, 0, 0, 3).k).toBe(MAX_ZOOM);
    expect(zoomAt({ x: -40, y: -40, k: 1.1 }, 0, 0, 0.5)).toEqual(NO_ZOOM);
  });
});
