import { describe, expect, it } from 'vitest';
import type { MarkdownNode } from './vaultGraph';
import { buildGraph, fitCamera, pathToRoot, tick } from './vaultGraph';

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

  it('pathToRoot devolve a nota e as pastas até a raiz (destaque da fonte no grafo)', () => {
    const { nodes, edges } = buildGraph([note('Estudos/Cisco/Cisco.md'), note('raiz.md')], 400, 400);

    expect(pathToRoot('Estudos/Cisco/Cisco.md', nodes, edges)).toEqual([
      'Estudos/Cisco/Cisco.md',
      'dir:Estudos/Cisco',
      'dir:Estudos',
      'dir:',
    ]);
    expect(pathToRoot('outra-vault.md', nodes, edges)).toEqual([]);
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

  it('posições iniciais são determinísticas e nenhum nó nasce sobre outro', () => {
    const vault = [note('A/x.md'), note('A/y.md'), note('B/z.md'), note('raiz.md')];
    const a = buildGraph(vault, 400, 400).nodes;
    const b = buildGraph(vault, 400, 400).nodes;
    expect(a.map((n) => [n.x, n.y])).toEqual(b.map((n) => [n.x, n.y]));

    const spots = new Set(a.map((n) => `${n.x},${n.y}`));
    expect(spots.size).toBe(a.length);
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

describe('vaultGraph.tick (regressão da física)', () => {
  it('converge: notas ficam perto da sua pasta, nada vira NaN e a velocidade tem teto', () => {
    const vault = Array.from({ length: 40 }, (_, i) => note(`P${i % 4}/n${i}.md`));
    const { nodes, edges } = buildGraph(vault, 400, 400);
    nodes[0].x = 3000; // nó jogado longe volta sem salto: o teto de velocidade limita cada passo
    for (let i = 0; i < 300; i++) tick(nodes, edges, 200, 200);

    const byId = new Map(nodes.map((n) => [n.id, n]));
    for (const n of nodes) {
      expect(Number.isFinite(n.x) && Number.isFinite(n.y)).toBe(true);
      expect(Math.hypot(n.vx, n.vy)).toBeLessThanOrEqual(30 + 1e-9);
    }
    for (const e of edges.filter((e) => byId.get(e.target)?.kind === 'note')) {
      const a = byId.get(e.source)!, b = byId.get(e.target)!;
      expect(Math.hypot(a.x - b.x, a.y - b.y)).toBeLessThan(200);
    }
  });
});

describe('vaultGraph.buildGraph por modo (pastas, links, ambos)', () => {
  const vault = [note('A/x.md'), note('A/y.md'), note('B/z.md'), note('solta.md')];
  const links = [
    { source: 'A/x.md', target: 'B/z.md' },
    { source: 'B/z.md', target: 'A/x.md' }, // mesma ligação nos dois sentidos: conta uma vez
    { source: 'A/x.md', target: 'fora.md' }, // nota que não está no vault: ignorada
  ];

  it('pastas: árvore como antes e nenhuma ligação', () => {
    const { nodes, edges } = buildGraph(vault, 400, 400, [], links, 'pastas');
    expect(nodes.filter((n) => n.kind === 'folder')).toHaveLength(3);
    expect(nodes).toHaveLength(7);
    expect(edges).toHaveLength(6);
    expect(edges.some((e) => e.kind === 'link')).toBe(false);
  });

  it('links: só notas e as ligações; notas sem ligação continuam no grafo', () => {
    const { nodes, edges } = buildGraph(vault, 400, 400, [], links, 'links');
    expect(nodes.every((n) => n.kind === 'note')).toBe(true);
    expect(nodes).toHaveLength(4);
    expect(nodes.find((n) => n.id === 'solta.md')?.degree).toBe(0);
    expect(edges).toEqual([{ source: 'A/x.md', target: 'B/z.md', kind: 'link' }]);
  });

  it('ambos: árvore e ligações juntas', () => {
    const { nodes, edges } = buildGraph(vault, 400, 400, [], links, 'ambos');
    expect(nodes).toHaveLength(7);
    expect(edges).toHaveLength(7);
    expect(edges.filter((e) => e.kind === 'link')).toEqual([{ source: 'A/x.md', target: 'B/z.md', kind: 'link' }]);
  });

  it('o padrão é ambos: sem ligações o grafo é só a árvore', () => {
    expect(buildGraph(vault, 400, 400).edges).toHaveLength(6);
    expect(buildGraph(vault, 400, 400, [], links).edges).toHaveLength(7);
  });
});

describe('vaultGraph: ligações entre notas', () => {
  const vault = [note('A/x.md'), note('B/z.md')];
  const links = [{ source: 'A/x.md', target: 'B/z.md' }];

  it('pathToRoot ignora ligações: a nota sobe só pela árvore', () => {
    const { nodes, edges } = buildGraph(vault, 400, 400, [], links, 'ambos');
    expect(pathToRoot('B/z.md', nodes, edges)).toEqual(['B/z.md', 'dir:B', 'dir:']);
  });

  it('no modo links, pathToRoot devolve só a nota', () => {
    const { nodes, edges } = buildGraph(vault, 400, 400, [], links, 'links');
    expect(pathToRoot('B/z.md', nodes, edges)).toEqual(['B/z.md']);
  });

  it('a ligação aproxima as duas notas a ~60 px (repouso próprio), mais que nota ↔ pasta (~26)', () => {
    const { nodes, edges } = buildGraph(vault, 400, 400, [], links, 'links');
    for (let i = 0; i < 400; i++) tick(nodes, edges, 200, 200);
    const [a, b] = nodes;
    const dist = Math.hypot(a.x - b.x, a.y - b.y);
    expect(dist).toBeGreaterThan(50);
    expect(dist).toBeLessThan(80);
  });
});
