/**
 * graphDraw.ts — desenho de um frame do grafo em Canvas 2D (funções puras sobre o contexto).
 *
 * Usado por ForceGraph.tsx, que só orquestra: câmera, eventos e o loop da simulação.
 * Cores vêm dos tokens do tema (index.css) lidas uma vez por frame.
 */

import type { Camera, SimEdge, SimNode } from '../lib/vaultGraph';
import { nodeRadius } from '../lib/vaultGraph';
import { DIM_ALPHA, edgeInSelection } from '../lib/graphSelection';
import { GRAPH_COLOR_TOKENS } from '../lib/graphColors';
import { LABEL_PADDING, labelPriority, pickLabels, type LabelBox } from '../lib/graphLabels';

export type Ctx = CanvasRenderingContext2D;

export function readPalette(el: Element) {
  const css = getComputedStyle(el);
  const v = (name: string) => css.getPropertyValue(name).trim();
  return {
    edge: v('--border-color'),
    node: v('--text-muted'),
    folder: v('--accent-blue'),
    label: v('--text-secondary'),
    text: v('--text-primary'),
    hover: v('--accent-blue-light'),
    link: v('--accent-blue-light'),
    focus: v('--accent-blue-light'),
    bg: v('--bg-primary'),
    tipBg: v('--tip-bg'),
    tipFg: v('--tip-fg'),
    /** cores das pastas de 1º nível, na ordem de GRAPH_COLOR_TOKENS */
    groups: GRAPH_COLOR_TOKENS.map(v),
  };
}

export type Palette = ReturnType<typeof readPalette>;

/** O que destacar neste frame: o hover, o nó selecionado e a sua vizinhança (null = sem seleção). */
export interface Highlight {
  hoveredId: string | null;
  selectedId: string | null;
  sel: Set<string> | null;
  scale: number;
}

/** Linha do tooltip com a pasta: a própria (pasta) ou a que contém a nota; também em texto, não só cor. */
export function tooltipDetail(n: SimNode): string {
  if (n.kind === 'folder') return n.depth === 0 ? 'Raiz do vault' : `Pasta: ${n.folder}`;
  return n.folder ? `Pasta: ${n.folder}` : 'Na raiz do vault';
}

// Pasta de 1º nível: cor da paleta; a raiz e o que está sem grupo mantêm o cinza/azul do tema
function nodeColor(n: SimNode, pal: Palette, hoveredId: string | null): string {
  if (n.id === hoveredId) return pal.hover;
  const group = n.colorSlot === null ? undefined : pal.groups[n.colorSlot];
  if (n.kind === 'folder') return n.depth === 0 ? pal.folder : group ?? pal.folder;
  return group ?? pal.node;
}

// Notas herdam a cor da pasta, mais apagadas que a pasta; hover e seleção voltam a ser cheias
const NOTE_FILL_ALPHA = 0.75;

function fillStrength(n: SimNode, hl: Highlight): number {
  if (n.kind !== 'note' || n.colorSlot === null) return 1;
  return n.id === hl.hoveredId || n.id === hl.selectedId ? 1 : NOTE_FILL_ALPHA;
}

/** Arestas da árvore em cinza; ligações [[...]] por cima, mais grossas e em azul claro transparente. */
export function drawEdges(ctx: Ctx, nodes: SimNode[], edges: SimEdge[], pal: Palette, cam: Camera, sel: Set<string> | null) {
  const map = new Map(nodes.map((n) => [n.id, n]));
  const base = ctx.globalAlpha;
  // Quem sai da seleção vai antes (mais apagado); quem está nela por último, por cima
  const passes: [isLink: boolean, inSel: boolean][] = sel
    ? [[false, false], [true, false], [false, true], [true, true]]
    : [[false, true], [true, true]];

  for (const [isLink, inSel] of passes) {
    ctx.beginPath();
    for (const e of edges) {
      if ((e.kind === 'link') !== isLink) continue;
      if (sel && edgeInSelection(e, sel) !== inSel) continue;
      const a = map.get(e.source), b = map.get(e.target);
      if (!a || !b) continue;
      ctx.moveTo(a.x, a.y);
      ctx.lineTo(b.x, b.y);
    }
    ctx.strokeStyle = isLink ? pal.link : pal.edge;
    ctx.lineWidth = (isLink ? 1.2 : 0.8) / cam.scale;
    ctx.globalAlpha = base * (isLink ? 0.35 : 1) * (sel && !inSel ? DIM_ALPHA : 1);
    ctx.stroke();
  }
  ctx.globalAlpha = base;
}

/** Nós, e por cima do selecionado um anel (a seleção não depende só da cor). */
export function drawNodes(ctx: Ctx, nodes: SimNode[], pal: Palette, hl: Highlight) {
  const base = ctx.globalAlpha;
  for (const n of nodes) {
    ctx.globalAlpha = base * fillStrength(n, hl) * (!hl.sel || hl.sel.has(n.id) ? 1 : DIM_ALPHA);
    ctx.beginPath();
    ctx.arc(n.x, n.y, nodeRadius(n), 0, Math.PI * 2);
    ctx.fillStyle = nodeColor(n, pal, hl.hoveredId);
    ctx.fill();
  }
  ctx.globalAlpha = base;

  if (hl.selectedId === null) return;
  const selected = nodes.find((n) => n.id === hl.selectedId);
  if (!selected) return;
  ctx.strokeStyle = pal.text;
  ctx.lineWidth = 2 / hl.scale;
  ctx.beginPath();
  ctx.arc(selected.x, selected.y, nodeRadius(selected) + 4 / hl.scale, 0, Math.PI * 2);
  ctx.stroke();
}

// Rótulos das pastas só com zoom suficiente para não se sobreporem (1º nível antes dos demais);
// as notas ganham nome com mais zoom ainda, como no grafo do Obsidian (no modo Links só há notas).
const NOTE_LABEL_SCALE = 1.6;

const LABEL_FONT_PX = 11;

// Com seleção, o selecionado e os vizinhos diretos sempre levam nome, em qualquer zoom (se não colidirem).
// Rótulos que sobrepõem um já escolhido são pulados: prioridade em lib/graphLabels.ts.
export function drawLabels(
  ctx: Ctx,
  nodes: SimNode[],
  pal: Palette,
  cam: Camera,
  sel: Set<string> | null,
  selectedId: string | null = null,
) {
  const base = ctx.globalAlpha;
  ctx.fillStyle = pal.label;
  ctx.font = `${LABEL_FONT_PX / cam.scale}px sans-serif`;
  ctx.textAlign = 'center';

  // Candidatos: quem passa pelas regras de zoom e seleção, com a caixa medida em tela
  const candidates: { n: SimNode; boxes: LabelBox }[] = [];
  for (const n of nodes) {
    const inSel = sel?.has(n.id) ?? false;
    if (sel && !inSel) continue; // com seleção, só o nó e os vizinhos têm nome: o resto fica como fundo
    if (n.kind === 'folder' && n.depth === 0 && !inSel) continue;
    const minScale = n.kind === 'note' ? NOTE_LABEL_SCALE : n.depth === 1 ? 0.45 : 1.2;
    if (!inSel && cam.scale < minScale) continue;

    // A fonte está em unidades de mundo (tamanho 11 ÷ scale): medir × scale dá px de tela
    const m = ctx.measureText(n.label);
    const width = m.width * cam.scale;
    const ascent = (m.actualBoundingBoxAscent ?? LABEL_FONT_PX * 0.8 / cam.scale) * cam.scale;
    const descent = (m.actualBoundingBoxDescent ?? LABEL_FONT_PX * 0.2 / cam.scale) * cam.scale;
    const sx = n.x * cam.scale + cam.x;
    const baseline = n.y * cam.scale + cam.y - (nodeRadius(n) + 4); // mesma posição do desenho, em tela
    candidates.push({
      n,
      boxes: {
        id: n.id,
        priority: labelPriority(n, selectedId, inSel),
        left: sx - width / 2 - LABEL_PADDING,
        right: sx + width / 2 + LABEL_PADDING,
        top: baseline - ascent - LABEL_PADDING,
        bottom: baseline + descent + LABEL_PADDING,
      },
    });
  }

  const shown = pickLabels(candidates.map((c) => c.boxes));
  for (const { n } of candidates) {
    if (!shown.has(n.id)) continue;
    ctx.globalAlpha = base;
    ctx.fillText(n.label, n.x, n.y - (nodeRadius(n) + 4) / cam.scale);
  }
  ctx.globalAlpha = base;
}

// Nota em foco (hover numa fonte do chat) e o caminho de pastas até a raiz. Tamanhos em px de
// tela (÷ scale) para o destaque aparecer em qualquer zoom; viewW prende a pílula no painel.
export function drawFocus(ctx: Ctx, chain: string[], nodes: SimNode[], pal: Palette, cam: Camera, viewW: number) {
  const byId = new Map(nodes.map((n) => [n.id, n]));
  const path = chain.map((id) => byId.get(id)).filter((n): n is SimNode => n !== undefined);
  const [target] = path;
  if (!target) return;
  const px = 1 / cam.scale;
  const radius = (n: SimNode) => Math.max(nodeRadius(n), (n === target ? 6 : 4) * px);

  ctx.strokeStyle = pal.focus;
  ctx.lineWidth = 2 * px;
  ctx.beginPath();
  path.forEach((n, i) => (i === 0 ? ctx.moveTo(n.x, n.y) : ctx.lineTo(n.x, n.y)));
  ctx.stroke();

  ctx.fillStyle = pal.focus;
  ctx.globalAlpha = 0.25;
  ctx.beginPath();
  ctx.arc(target.x, target.y, 14 * px, 0, Math.PI * 2);
  ctx.fill();
  ctx.globalAlpha = 1;
  for (const n of path) {
    ctx.beginPath();
    ctx.arc(n.x, n.y, radius(n), 0, Math.PI * 2);
    ctx.fill();
  }

  // Nomes das pastas do caminho, com contorno da cor do fundo para a linha não cortar a letra
  ctx.font = `${11 * px}px sans-serif`;
  ctx.textAlign = 'center';
  ctx.lineJoin = 'round';
  ctx.lineWidth = 3 * px;
  ctx.strokeStyle = pal.bg;
  for (const n of path.slice(1)) {
    if (n.depth === 0) continue; // a raiz não tem nome
    const y = n.y - radius(n) - 5 * px;
    ctx.strokeText(n.label, n.x, y);
    ctx.fillText(n.label, n.x, y);
  }

  // Nome da nota numa pílula acima dela, sem sair pelas bordas do painel
  const label = target.label.length > 42 ? `${target.label.slice(0, 41)}…` : target.label;
  ctx.font = `600 ${12 * px}px sans-serif`;
  const w = ctx.measureText(label).width + 16 * px;
  const h = 22 * px;
  const minX = (6 - cam.x) * px;
  const maxX = (viewW - 6 - cam.x) * px - w;
  const left = Math.max(minX, Math.min(maxX, target.x - w / 2));
  const top = target.y - 18 * px - h;
  ctx.fillStyle = pal.tipBg;
  ctx.beginPath();
  ctx.roundRect(left, top, w, h, 6 * px);
  ctx.fill();
  ctx.fillStyle = pal.tipFg;
  ctx.textBaseline = 'middle';
  ctx.fillText(label, left + w / 2, top + h / 2);
  ctx.textBaseline = 'alphabetic';
}
