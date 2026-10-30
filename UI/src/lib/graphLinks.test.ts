/**
 * Validação do grafo com ligações [[...]] reais (dados sintéticos pequenos e explícitos).
 *
 * Vault de exemplo (cada linha é uma nota; a pasta vem do caminho):
 *   A/x.md  (X)  — liga a B/y.md (Y) e a C/z.md (Z); também tem um laço e um link quebrado
 *   A/w.md  (W)  — recebe a ligação de Y
 *   B/y.md  (Y)  — liga de volta a X (a mesma ligação nos dois sentidos) e a W
 *   C/z.md  (Z)  — só recebe a ligação de X
 *   solta.md (S) — na raiz, sem nenhuma ligação
 *
 * Ligações brutas (como viriam do índice): X→Y, Y→X (repetida), X→Z, Y→W, X→X (laço),
 * X→Nao/existe.md (nota inexistente). Só X→Y, X→Z e Y→W devem contar no grafo.
 */

import { describe, expect, it } from 'vitest';
import type { MarkdownNode, VaultLink } from './vaultGraph';
import { buildGraph, pathToRoot, visibleLinks } from './vaultGraph';
import { edgeInSelection, folderSubtreeIds, neighborIds, selectionSet } from './graphSelection';
import { labelPriority } from './graphLabels';

const note = (path: string): MarkdownNode => ({
  id: path,
  name: path.split('/').at(-1)!.replace(/\.md$/, ''),
  path,
  size: 1,
  modified: '',
});

const vault = [note('A/x.md'), note('A/w.md'), note('B/y.md'), note('C/z.md'), note('solta.md')];

const links: VaultLink[] = [
  { source: 'A/x.md', target: 'B/y.md' },
  { source: 'B/y.md', target: 'A/x.md' },
  { source: 'A/x.md', target: 'C/z.md' },
  { source: 'B/y.md', target: 'A/w.md' },
  { source: 'A/x.md', target: 'A/x.md' },
  { source: 'A/x.md', target: 'Nao/existe.md' },
];

const X = 'A/x.md';
const Y = 'B/y.md';
const Z = 'C/z.md';
const W = 'A/w.md';
const S = 'solta.md';

describe('ligações [[...]] válidas', () => {
  it('descarta laço, nota inexistente e repetição (A→B e B→A viram uma linha só)', () => {
    const valid = visibleLinks(vault, links);
    expect(valid).toHaveLength(3);
    const pairs = valid.map((l) => [l.source, l.target].sort().join(' ↔ ')).sort();
    expect(pairs).toEqual(['A/x.md ↔ B/y.md', 'A/x.md ↔ C/z.md', 'A/w.md ↔ B/y.md'].sort());
  });
});

describe('vizinhança por ligação (modo Ambos: árvore + ligações)', () => {
  const { edges } = buildGraph(vault, 400, 400, [], links, 'ambos');

  it('a nota vê a própria pasta e as notas que liga, nos dois sentidos', () => {
    expect(neighborIds(X, edges)).toEqual(new Set(['dir:A', Y, Z]));
    expect(neighborIds(Y, edges)).toEqual(new Set(['dir:B', X, W]));
    expect(neighborIds(Z, edges)).toEqual(new Set(['dir:C', X]));
  });

  it('nota sem ligação só tem a pasta (na raiz, a pasta raiz); o laço e o link quebrado não criam vizinho', () => {
    expect(neighborIds(S, edges)).toEqual(new Set(['dir:']));
    expect(neighborIds(X, edges).has(X)).toBe(false);
    expect(neighborIds(X, edges).has('Nao/existe.md')).toBe(false);
  });

  it('a pasta enquadrada não puxa as notas ligadas de outras pastas (ligação não é árvore)', () => {
    expect(folderSubtreeIds('dir:A', edges)).toEqual(new Set(['dir:A', X, W]));
  });
});

describe('modo Links: só notas e ligações', () => {
  const { nodes, edges } = buildGraph(vault, 400, 400, [], links, 'links');

  it('não cria pastas; todas as notas continuam no grafo, mesmo as sem ligação', () => {
    expect(nodes.filter((n) => n.kind === 'folder')).toHaveLength(0);
    expect(nodes.map((n) => n.id).sort()).toEqual([S, W, X, Y, Z].sort());
  });

  it('vizinhos são só as notas ligadas; nota sem ligação fica sozinha na seleção', () => {
    expect(neighborIds(X, edges)).toEqual(new Set([Y, Z]));
    expect(neighborIds(W, edges)).toEqual(new Set([Y]));
    expect(selectionSet(S, edges)).toEqual(new Set([S]));
  });

  it('a raiz do caminho é a própria nota (no modo Links não há pasta-mãe)', () => {
    expect(pathToRoot(X, nodes, edges)).toEqual([X]);
  });
});

describe('modo Pastas: ligações não entram', () => {
  const { nodes, edges } = buildGraph(vault, 400, 400, [], links, 'pastas');

  it('a vizinhança é só a pasta, e não há arestas de ligação', () => {
    expect(neighborIds(X, edges)).toEqual(new Set(['dir:A']));
    expect(edges.some((e) => e.kind === 'link')).toBe(false);
  });

  it('o caminho até a raiz segue a árvore de pastas', () => {
    expect(pathToRoot(X, nodes, edges)).toEqual([X, 'dir:A', 'dir:']);
  });
});

describe('nota ligada a duas pastas (X em A, ligada a B e a C)', () => {
  const { nodes, edges } = buildGraph(vault, 400, 400, [], links, 'ambos');
  const sel = selectionSet(X, edges)!;

  it('a seleção reúne a própria pasta e as duas notas ligadas, de pastas diferentes', () => {
    expect(sel).toEqual(new Set([X, 'dir:A', Y, Z]));
    // B e C, pastas de Y e Z, não entram: a seleção não sobe para as pastas delas
    expect(sel.has('dir:B')).toBe(false);
    expect(sel.has('dir:C')).toBe(false);
  });

  it('arestas com as duas pontas na seleção ficam em destaque; as demais recuam', () => {
    expect(edgeInSelection({ source: 'dir:A', target: X }, sel)).toBe(true); // árvore
    expect(edgeInSelection({ source: X, target: Y, kind: 'link' }, sel)).toBe(true); // ligação
    expect(edgeInSelection({ source: X, target: Z, kind: 'link' }, sel)).toBe(true);
    expect(edgeInSelection({ source: 'dir:B', target: Y }, sel)).toBe(false); // pasta de Y fora
    expect(edgeInSelection({ source: Y, target: W, kind: 'link' }, sel)).toBe(false); // W fora
  });

  it('o caminho de X vai pela pasta A (ligação não é pai); Y e Z sobem pelas suas pastas', () => {
    expect(pathToRoot(X, nodes, edges)).toEqual([X, 'dir:A', 'dir:']);
    expect(pathToRoot(Y, nodes, edges)).toEqual([Y, 'dir:B', 'dir:']);
    expect(pathToRoot(Z, nodes, edges)).toEqual([Z, 'dir:C', 'dir:']);
  });

  it('rótulos: selecionado primeiro, depois pasta e vizinhos ligados, depois a pasta distante e as notas', () => {
    const byId = new Map(nodes.map((n) => [n.id, n]));
    const pri = (id: string) => labelPriority(byId.get(id)!, X, sel.has(id));
    expect(pri(X)).toBe(0);
    expect(pri('dir:A')).toBe(1);
    expect(pri(Y)).toBe(1);
    expect(pri(Z)).toBe(1);
    expect(pri('dir:B')).toBeGreaterThan(1); // pasta de vizinho, mas não é vizinha
    expect(pri(W)).toBeGreaterThan(pri('dir:B')); // nota comum fica por último entre as visíveis
  });
});
