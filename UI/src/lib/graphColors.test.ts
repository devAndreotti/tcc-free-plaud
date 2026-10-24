/// <reference types="node" />
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';
import type { MarkdownNode } from './vaultGraph';
import { buildGraph } from './vaultGraph';
import {
  GRAPH_COLOR_TOKENS,
  GRAPH_LEGEND_MAX,
  folderPaletteIndex,
  legendEntries,
  stableHash,
  topFolderOf,
} from './graphColors';

const note = (path: string): MarkdownNode => ({
  id: path,
  name: path.split('/').at(-1)!.replace(/\.md$/, ''),
  path,
  size: 1,
  modified: '',
});

describe('cor estável por nome da pasta', () => {
  it('o hash é fixo: a mesma entrada dá o mesmo valor (regressão: não mudar a paleta de todo mundo)', () => {
    expect(stableHash('Estudos')).toBe(388130584);
    expect(stableHash('Estudos')).toBe(stableHash('Estudos'));
  });

  it('índices conhecidos (travados): mudar a função muda a cor de todas as pastas salvas', () => {
    expect(folderPaletteIndex('Estudos')).toBe(0);
    expect(folderPaletteIndex('Pessoas')).toBe(1);
    expect(folderPaletteIndex('Arquitetura')).toBe(2);
    expect(folderPaletteIndex('A')).toBe(4);
    expect(folderPaletteIndex('B')).toBe(5);
  });

  it('todo índice fica entre 0 e 7, e nomes comuns espalham pelas 8 cores', () => {
    const names = Array.from({ length: 40 }, (_, i) => `Pasta ${i + 1}`);
    const slots = new Set(names.map(folderPaletteIndex));
    expect([...slots].every((s) => s >= 0 && s < 8)).toBe(true);
    expect(slots.size).toBeGreaterThanOrEqual(6);
  });

  it('nomes com acento e espaço também têm índice estável', () => {
    expect(folderPaletteIndex('Diário de Bordo')).toBe(folderPaletteIndex('Diário de Bordo'));
    expect(folderPaletteIndex('Diário')).toBe(1);
  });

  it('a ordem em que as notas chegam não muda a cor de nenhuma pasta', () => {
    const notes = [note('Estudos/a.md'), note('Pessoas/b.md'), note('Projetos/Sub/c.md'), note('solta.md')];
    const colorsOf = (list: MarkdownNode[]) => {
      const { nodes } = buildGraph(list, 400, 400);
      return new Map(nodes.map((n) => [n.id, n.colorSlot]));
    };
    const forward = colorsOf(notes);
    const backward = colorsOf([...notes].reverse());
    for (const [id, slot] of forward) expect(backward.get(id)).toBe(slot);
  });

  it('nó recebe o grupo (pasta de 1º nível) e o índice; nota na raiz não tem cor de pasta', () => {
    const { nodes } = buildGraph([note('Estudos/Cisco/x.md'), note('solta.md')], 400, 400);
    const x = nodes.find((n) => n.id === 'Estudos/Cisco/x.md')!;
    expect(x.group).toBe('Estudos');
    expect(x.colorSlot).toBe(folderPaletteIndex('Estudos'));
    expect(x.folder).toBe('Estudos/Cisco');
    expect(nodes.find((n) => n.id === 'solta.md')!.colorSlot).toBeNull();
    expect(nodes.find((n) => n.id === 'dir:')!.colorSlot).toBeNull(); // raiz do vault: sem cor de grupo
  });

  it('pasta de 2º nível herda a cor da pasta de 1º nível', () => {
    const { nodes } = buildGraph([note('Estudos/Cisco/x.md')], 400, 400);
    const cisco = nodes.find((n) => n.id === 'dir:Estudos/Cisco')!;
    expect(cisco.group).toBe('Estudos');
    expect(cisco.colorSlot).toBe(folderPaletteIndex('Estudos'));
  });
});

describe('topFolderOf', () => {
  it('devolve a pasta de 1º nível, aceitando barra invertida', () => {
    expect(topFolderOf('Estudos/Cisco/x.md')).toBe('Estudos');
    expect(topFolderOf('Estudos\\Cisco\\x.md')).toBe('Estudos');
    expect(topFolderOf('x.md')).toBe('');
  });
});

describe('legendEntries', () => {
  it('ordena pelo nome (pt-BR), sem repetir e sem a raiz', () => {
    const { shown, overflow, total } = legendEntries(['Pessoas', 'Estudos', '', 'Pessoas', 'arquivo']);
    expect(shown.map((e) => e.name)).toEqual(['arquivo', 'Estudos', 'Pessoas']);
    expect(overflow).toBe(0);
    expect(total).toBe(3);
  });

  it('cada entrada aponta para o token da própria cor', () => {
    const { shown } = legendEntries(['Estudos']);
    expect(shown[0].token).toBe(GRAPH_COLOR_TOKENS[folderPaletteIndex('Estudos')]);
  });

  it(`mostra no máximo ${GRAPH_LEGEND_MAX} pastas e conta o resto`, () => {
    const many = Array.from({ length: 11 }, (_, i) => `Pasta ${String(i).padStart(2, '0')}`);
    const { shown, overflow, total } = legendEntries(many);
    expect(shown).toHaveLength(GRAPH_LEGEND_MAX);
    expect(overflow).toBe(3);
    expect(total).toBe(11);
  });

  it('sem pastas, a legenda fica vazia', () => {
    expect(legendEntries([])).toEqual({ shown: [], overflow: 0, total: 0 });
  });
});

// Contraste dos tokens em index.css: as cores precisam aparecer no fundo do painel nos dois temas
describe('paleta do grafo em index.css', () => {
  // Os testes rodam a partir da pasta UI (npm test / vitest); o CSS é lido direto do disco
  const css = readFileSync(resolve(process.cwd(), 'src/index.css'), 'utf8');
  const block = (selector: string) => {
    const start = css.indexOf(`${selector} {`);
    if (start < 0) throw new Error(`bloco ${selector} não encontrado`);
    return css.slice(start, css.indexOf('}', start));
  };
  const tokenIn = (text: string, name: string) => {
    const m = new RegExp(`${name}:\\s*(#[0-9a-fA-F]{6})`).exec(text);
    if (!m) throw new Error(`token ${name} ausente`);
    return m[1];
  };
  const luminance = (hex: string) => {
    const [r, g, b] = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16) / 255)
      .map((v) => (v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4));
    return 0.2126 * r + 0.7152 * g + 0.0722 * b;
  };
  const contrast = (a: string, b: string) => {
    const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x);
    return (hi + 0.05) / (lo + 0.05);
  };

  const themes = {
    escuro: block(':root'),
    claro: block(':root[data-theme="light"]'),
  };

  for (const [theme, text] of Object.entries(themes)) {
    it(`tema ${theme}: as 8 cores são diferentes entre si e chegam a 3:1 no fundo do painel`, () => {
      const colors = GRAPH_COLOR_TOKENS.map((t) => tokenIn(text, t));
      expect(new Set(colors).size).toBe(8);
      const bg = tokenIn(text, '--bg-primary');
      const panel = tokenIn(text, '--bg-panel');
      for (const c of colors) {
        expect(contrast(c, bg)).toBeGreaterThanOrEqual(3);
        expect(contrast(c, panel)).toBeGreaterThanOrEqual(3);
      }
    });
  }
});

describe('assignPaletteSlots', () => {
  it('não repete cor entre pastas enquanto couberem na paleta', async () => {
    const { assignPaletteSlots } = await import('./graphColors');
    const names = ['docs', 'Sprints', 'notas', 'UI', 'data', 'pipeline', 'src', 'tests'];
    const slots = assignPaletteSlots(names);
    expect(new Set(slots.values()).size).toBe(8);
  });

  it('não depende da ordem de entrada e ignora a raiz', async () => {
    const { assignPaletteSlots } = await import('./graphColors');
    const a = assignPaletteSlots(['docs', 'Sprints', '', 'notas']);
    const b = assignPaletteSlots(['notas', 'docs', 'Sprints', 'docs']);
    expect([...a.entries()].sort()).toEqual([...b.entries()].sort());
    expect(a.has('')).toBe(false);
  });

  it('com mais de 8 pastas repete cores sem falhar', async () => {
    const { assignPaletteSlots } = await import('./graphColors');
    const slots = assignPaletteSlots(Array.from({ length: 11 }, (_, i) => `pasta-${i}`));
    expect(slots.size).toBe(11);
    for (const v of slots.values()) expect(v).toBeGreaterThanOrEqual(0);
  });
});
