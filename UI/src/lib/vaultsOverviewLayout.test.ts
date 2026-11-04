import { describe, expect, it } from 'vitest';
import type { VaultOverview } from '../services/bridge';
import { buildOverviewLayout, searchOverview, VIEW_H, VIEW_W } from './vaultsOverviewLayout';

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
