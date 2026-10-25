import { describe, expect, it } from 'vitest';
import { boxesOverlap, labelPriority, pickLabels, type LabelBox } from './graphLabels';

const box = (id: string, left: number, right: number, priority: number, top = 0, bottom = 10): LabelBox => ({
  id, priority, left, right, top, bottom,
});

describe('labelPriority: selecionado > vizinhos > pastas (rasas antes) > notas', () => {
  const folder = (depth: number) => ({ id: `dir:${depth}`, kind: 'folder' as const, depth });
  const note = { id: 'n.md', kind: 'note' as const, depth: 2 };

  it('ordena a prioridade na ordem da regra', () => {
    const selected = labelPriority({ id: 'dir:A', kind: 'folder', depth: 1 }, 'dir:A', true);
    const neighbor = labelPriority({ id: 'n.md', kind: 'note', depth: 2 }, 'dir:A', true);
    const shallow = labelPriority(folder(1), null, false);
    const deep = labelPriority(folder(3), null, false);
    const lone = labelPriority(note, null, false);
    expect(selected).toBeLessThan(neighbor);
    expect(neighbor).toBeLessThan(shallow);
    expect(shallow).toBeLessThan(deep);
    expect(deep).toBeLessThan(lone);
  });

  it('o selecionado vence mesmo sem estar marcado como vizinho', () => {
    expect(labelPriority({ id: 'x.md', kind: 'note', depth: 2 }, 'x.md', false)).toBe(0);
  });
});

describe('boxesOverlap', () => {
  it('caixas que se cruzam colidem; encostar nas bordas não conta', () => {
    expect(boxesOverlap(box('a', 0, 10, 0), box('b', 5, 15, 0))).toBe(true);
    expect(boxesOverlap(box('a', 0, 10, 0), box('b', 10, 20, 0))).toBe(false);
  });

  it('caixas empilhadas na vertical só colidem se também se cruzam na horizontal', () => {
    expect(boxesOverlap(box('a', 0, 10, 0, 0, 10), box('b', 0, 10, 0, 10, 20))).toBe(false);
    expect(boxesOverlap(box('a', 0, 10, 0, 0, 10), box('b', 0, 10, 0, 9, 20))).toBe(true);
  });
});

describe('pickLabels', () => {
  it('sem colisão, todos os rótulos ficam', () => {
    const shown = pickLabels([box('a', 0, 10, 0), box('b', 20, 30, 0), box('c', 40, 50, 0)]);
    expect([...shown]).toEqual(['a', 'b', 'c']);
  });

  it('colisão: o de prioridade mais baixa (mais importante) fica, o outro sai', () => {
    const shown = pickLabels([box('nota', 0, 10, 1000), box('pasta', 5, 15, 3)]);
    expect([...shown]).toEqual(['pasta']);
  });

  it('a prioridade vale mesmo quando o importante vem por último na lista', () => {
    const shown = pickLabels([box('vizinho', 0, 10, 1), box('selecionado', 0, 10, 0)]);
    expect([...shown]).toEqual(['selecionado']);
  });

  it('entre prioridades iguais, quem vem antes na lista fica (resultado estável de frame a frame)', () => {
    const shown = pickLabels([box('primeiro', 0, 10, 3), box('segundo', 5, 15, 3)]);
    expect([...shown]).toEqual(['primeiro']);
  });

  it('a escolha é gulosa e não derruba um rótulo que não colide com nenhum aceito', () => {
    // A cobre B, mas B não cobre C: A entra, B sai, C entra
    const shown = pickLabels([box('A', 0, 10, 0), box('B', 8, 18, 1), box('C', 15, 25, 2)]);
    expect([...shown]).toEqual(['A', 'C']);
  });

  it('lista vazia devolve conjunto vazio', () => {
    expect(pickLabels([]).size).toBe(0);
  });
});
