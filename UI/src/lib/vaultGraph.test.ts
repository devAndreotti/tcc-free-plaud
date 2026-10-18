import { describe, expect, it } from 'vitest';
import type { MarkdownNode } from '../hooks/useVault';
import { buildGraph, fitCamera } from './vaultGraph';

const note = (path: string): MarkdownNode => ({
  id: path,
  name: path.split('/').at(-1)!.replace(/\.md$/, ''),
  path,
  size: 1,
  modified: '',
});

describe('vaultGraph (regressão do grafo bagunçado)', () => {
  it('pastas de mesmo nome em caminhos diferentes viram nós distintos', () => {
    const { nodes } = buildGraph([note('A/Pessoas/ana.md'), note('B/Pessoas/bia.md')], 400, 400);
    const pessoas = nodes.filter((n) => n.kind === 'folder' && n.label === 'Pessoas');
    expect(pessoas.map((n) => n.id).sort()).toEqual(['dir:A/Pessoas', 'dir:B/Pessoas']);
  });

  it('toda nota se liga à sua pasta, mesmo em pastas grandes, e as pastas sobem até a raiz', () => {
    const many = Array.from({ length: 30 }, (_, i) => note(`Estudos/nota-${i}.md`));
    const { nodes, edges } = buildGraph([...many, note('raiz.md'), note('A/B/C/funda.md')], 400, 400);

    for (const n of nodes.filter((n) => n.kind === 'note')) expect(n.degree).toBe(1);
    expect(edges).toContainEqual({ source: 'dir:A/B', target: 'dir:A/B/C' });
    expect(edges).toContainEqual({ source: 'dir:', target: 'dir:A' });
    expect(edges).toContainEqual({ source: 'dir:', target: 'raiz.md' });
    expect(nodes.find((n) => n.id === 'dir:Estudos')?.degree).toBe(31);
  });

  it('reconstruir com os mesmos ids mantém as posições (rescan não embaralha)', () => {
    const vault = [note('A/x.md'), note('A/y.md')];
    const first = buildGraph(vault, 400, 400);
    const second = buildGraph(vault, 400, 400, first.nodes);
    for (const n of second.nodes) {
      const before = first.nodes.find((o) => o.id === n.id)!;
      expect([n.x, n.y]).toEqual([before.x, before.y]);
    }
  });

  it('fitCamera enquadra todos os nós dentro do canvas, mesmo espalhados', () => {
    const { nodes } = buildGraph([note('A/x.md'), note('B/y.md')], 320, 900);
    nodes[0].x = -5000; nodes[0].y = -3000;
    nodes[1].x = 8000; nodes[1].y = 6000;
    const cam = fitCamera(nodes, 320, 900);
    for (const n of nodes) {
      const sx = n.x * cam.scale + cam.x;
      const sy = n.y * cam.scale + cam.y;
      expect(sx).toBeGreaterThanOrEqual(0);
      expect(sx).toBeLessThanOrEqual(320);
      expect(sy).toBeGreaterThanOrEqual(0);
      expect(sy).toBeLessThanOrEqual(900);
    }
  });
});
