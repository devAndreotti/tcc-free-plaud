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
import { iconBody, notifyNoteIcons, readNoteIconsMode, titleParts, type TitlePart } from '../lib/noteIcons';

export type Ctx = CanvasRenderingContext2D;

// Fonte da interface (PR 147), para rótulos e pílula do foco
const UI_FONT = 'system-ui, -apple-system, "Segoe UI", Roboto, sans-serif';

// Largura do ícone de emoji no rótulo, em relação ao tamanho da fonte
const ICON_EM = 1.1;

const iconImages = new Map<string, HTMLImageElement>();

/** Imagem do ícone na cor pedida (a raiz do SVG resolve o currentColor); null até carregar. */
function iconImage(key: string, color: string): HTMLImageElement | null {
  const body = iconBody(key);
  if (!body) return null;
  const id = `${key}|${color}`;
  let image = iconImages.get(id);
  if (!image) {
    image = new Image();
    image.onload = notifyNoteIcons;
    image.src = `data:image/svg+xml,${encodeURIComponent(`<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32" width="32" height="32" color="${color}">${body}</svg>`)}`;
    iconImages.set(id, image);
  }
  return image.complete && image.naturalWidth > 0 ? image : null;
}

/** Largura do título em unidades do contexto: texto medido mais o espaço de cada ícone. */
function titleWidth(ctx: Ctx, parts: TitlePart[], size: number): number {
  return parts.reduce((sum, part) => sum + (typeof part === 'string' ? ctx.measureText(part).width : size * ICON_EM), 0);
}

/**
 * Escreve o título respeitando o textAlign e o textBaseline atuais. Título só de texto é um fillText normal;
 * com ícones, cada parte vai em sequência. `halo` contorna o texto na cor de strokeStyle.
 */
function fillTitle(ctx: Ctx, parts: TitlePart[], x: number, y: number, size: number, halo = false) {
  const [only] = parts;
  if (parts.length === 1 && typeof only === 'string') {
    if (halo) ctx.strokeText(only, x, y);
    ctx.fillText(only, x, y);
    return;
  }
  const align = ctx.textAlign;
  let cursor = align === 'center' ? x - titleWidth(ctx, parts, size) / 2 : x;
  ctx.textAlign = 'left';
  for (const part of parts) {
    if (typeof part === 'string') {
      if (halo) ctx.strokeText(part, cursor, y);
      ctx.fillText(part, cursor, y);
      cursor += ctx.measureText(part).width;
    } else {
      const image = iconImage(part.key, String(ctx.fillStyle));
      if (image) ctx.drawImage(image, cursor, ctx.textBaseline === 'middle' ? y - size / 2 : y - size * 0.86, size, size);
      cursor += size * ICON_EM;
    }
  }
  ctx.textAlign = align;
}

export function readPalette(el: Element) {
  const css = getComputedStyle(el);
  const v = (name: string) => css.getPropertyValue(name).trim();
  return {
    edge: v('--ag-hairline'),
    node: v('--ag-ink-muted'),
    folder: v('--accent-blue-light'), // raiz: segue o destaque do tema, como a 1ª cor da paleta
    label: v('--ag-ink-2'),
    text: v('--ag-ink'),
    glow: v('--ag-glow'),
    hover: v('--ag-accent'),
    link: v('--ag-accent'),
    focus: v('--ag-accent'),
    bg: v('--ag-plane'),
    tipBg: v('--ag-surface'),
    tipFg: v('--ag-ink'),
    /** cores das pastas de 1º nível, na ordem de GRAPH_COLOR_TOKENS */
    groups: GRAPH_COLOR_TOKENS.map(v),
    /** opacidade da cor de pasta nas notas (--graph-note-alpha, por tema) */
    noteAlpha: parseNoteAlpha(v('--graph-note-alpha')),
  };
}

// Opacidade padrão das notas quando o token não existe ou não é número
const NOTE_FILL_ALPHA = 0.75;

function parseNoteAlpha(raw: string): number {
  const n = Number(raw);
  return raw !== '' && Number.isFinite(n) && n >= 0 && n <= 1 ? n : NOTE_FILL_ALPHA;
}

export type Palette = ReturnType<typeof readPalette>;

/** O que destacar neste frame: o hover, o nó selecionado e a sua vizinhança (null = sem seleção). */
export interface Highlight {
  hoveredId: string | null;
  selectedId: string | null;
  sel: Set<string> | null;
  scale: number;
  /** Tamanho do nó neste quadro (nó recém-chegado cresce); sem isso, todos no tamanho normal. */
  popOf?: (id: string) => number;
}

/** Linha do tooltip com a pasta: a própria (pasta) ou a que contém a nota; também em texto, não só cor. */
export function tooltipDetail(n: SimNode): string {
  if (n.pending) return 'Lida, aguardando gravação';
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

// Notas herdam a cor da pasta, mais apagadas que a pasta (pal.noteAlpha); hover e seleção voltam a ser cheias
function fillStrength(n: SimNode, hl: Highlight, noteAlpha: number): number {
  if (n.kind !== 'note' || n.colorSlot === null) return 1;
  return n.id === hl.hoveredId || n.id === hl.selectedId ? 1 : noteAlpha;
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
    ctx.lineWidth = (isLink ? 1 : 0.7) / cam.scale;
    ctx.globalAlpha = base * (isLink ? 0.45 : 1) * (sel && !inSel ? DIM_ALPHA : 1);
    ctx.stroke();
  }
  ctx.globalAlpha = base;
}

// Halo das pastas e do nó sob o mouse: raio em múltiplos do nó e opacidade da cor do nó
const HALO_SCALE = 2.2;
const HALO_ALPHA = 0.28;

/** Nós, e por cima do selecionado um anel (a seleção não depende só da cor). */
export function drawNodes(ctx: Ctx, nodes: SimNode[], pal: Palette, hl: Highlight) {
  const base = ctx.globalAlpha;
  for (const n of nodes) {
    const dim = !hl.sel || hl.sel.has(n.id) ? 1 : DIM_ALPHA;
    const r = nodeRadius(n) * (hl.popOf?.(n.id) ?? 1);
    const color = nodeColor(n, pal, hl.hoveredId);
    // Lido e ainda não gravado: só o contorno tracejado, na cor da pasta
    if (n.pending) {
      ctx.globalAlpha = base * dim;
      ctx.beginPath();
      ctx.arc(n.x, n.y, r + 1 / hl.scale, 0, Math.PI * 2);
      ctx.strokeStyle = color;
      ctx.lineWidth = 1.2 / hl.scale;
      ctx.setLineDash([2.5 / hl.scale, 2.5 / hl.scale]);
      ctx.stroke();
      ctx.setLineDash([]);
      continue;
    }
    // Halo translúcido (estilo do PR 147) na cor do próprio nó: pastas e o nó sob o mouse
    if (n.kind === 'folder' || n.id === hl.hoveredId) {
      ctx.globalAlpha = base * HALO_ALPHA * dim;
      ctx.beginPath();
      ctx.arc(n.x, n.y, r * HALO_SCALE, 0, Math.PI * 2);
      ctx.fillStyle = color;
      ctx.fill();
    }
    ctx.globalAlpha = base * fillStrength(n, hl, pal.noteAlpha) * dim;
    ctx.beginPath();
    ctx.arc(n.x, n.y, r, 0, Math.PI * 2);
    ctx.fillStyle = color;
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

/**
 * Arquivo em indexação: anel na cor de destaque e o nome ao lado. `phase` (0–1) faz o anel abrir e apagar;
 * null (Reduzir animações) deixa o anel parado. Tamanhos em px de tela, para aparecer em qualquer zoom.
 */
export function drawActive(ctx: Ctx, node: SimNode, pal: Palette, scale: number, phase: number | null) {
  const px = 1 / scale;
  const base = ctx.globalAlpha;
  const r = nodeRadius(node);
  ctx.strokeStyle = pal.link;
  ctx.lineWidth = 2 * px;
  ctx.globalAlpha = base * (phase === null ? 0.9 : 0.9 * (1 - phase));
  ctx.beginPath();
  ctx.arc(node.x, node.y, r + (phase === null ? 6 : 3 + 12 * phase) * px, 0, Math.PI * 2);
  ctx.stroke();
  ctx.globalAlpha = base;
  ctx.font = `${LABEL_FONT_PX * px}px ${UI_FONT}`;
  ctx.textAlign = 'left';
  ctx.textBaseline = 'middle';
  ctx.fillStyle = pal.text;
  fillTitle(ctx, titleParts(node.label, readNoteIconsMode()), node.x + r + 10 * px, node.y, LABEL_FONT_PX * px);
  ctx.textBaseline = 'alphabetic';
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
  const size = LABEL_FONT_PX / cam.scale;
  const mode = readNoteIconsMode();
  ctx.fillStyle = pal.label;
  ctx.font = `${size}px ${UI_FONT}`;
  ctx.textAlign = 'center';

  // Candidatos: quem passa pelas regras de zoom e seleção, com a caixa medida em tela
  const candidates: { n: SimNode; parts: TitlePart[]; boxes: LabelBox }[] = [];
  for (const n of nodes) {
    const inSel = sel?.has(n.id) ?? false;
    if (sel && !inSel) continue; // com seleção, só o nó e os vizinhos têm nome: o resto fica como fundo
    if (n.kind === 'folder' && n.depth === 0 && !inSel) continue;
    const minScale = n.kind === 'note' ? NOTE_LABEL_SCALE : n.depth === 1 ? 0.45 : 1.2;
    if (!inSel && cam.scale < minScale) continue;

    // A fonte está em unidades de mundo (tamanho 11 ÷ scale): medir × scale dá px de tela
    const parts = titleParts(n.label, mode);
    const m = ctx.measureText(parts.filter((part) => typeof part === 'string').join(''));
    const width = (m.width + parts.filter((part) => typeof part !== 'string').length * size * ICON_EM) * cam.scale;
    const ascent = (m.actualBoundingBoxAscent ?? LABEL_FONT_PX * 0.8 / cam.scale) * cam.scale;
    const descent = (m.actualBoundingBoxDescent ?? LABEL_FONT_PX * 0.2 / cam.scale) * cam.scale;
    const sx = n.x * cam.scale + cam.x;
    const baseline = n.y * cam.scale + cam.y - (nodeRadius(n) + 4); // mesma posição do desenho, em tela
    candidates.push({
      n,
      parts,
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
  for (const { n, parts } of candidates) {
    if (!shown.has(n.id)) continue;
    ctx.globalAlpha = base;
    fillTitle(ctx, parts, n.x, n.y - (nodeRadius(n) + 4) / cam.scale, size);
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
  const mode = readNoteIconsMode();
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
  ctx.font = `${11 * px}px ${UI_FONT}`;
  ctx.textAlign = 'center';
  ctx.lineJoin = 'round';
  ctx.lineWidth = 3 * px;
  ctx.strokeStyle = pal.bg;
  for (const n of path.slice(1)) {
    if (n.depth === 0) continue; // a raiz não tem nome
    fillTitle(ctx, titleParts(n.label, mode), n.x, n.y - radius(n) - 5 * px, 11 * px, true);
  }

  // Nome da nota numa pílula acima dela, sem sair pelas bordas do painel
  const label = target.label.length > 42 ? `${target.label.slice(0, 41)}…` : target.label;
  const labelParts = titleParts(label, mode);
  ctx.font = `600 ${12 * px}px ${UI_FONT}`;
  const w = titleWidth(ctx, labelParts, 12 * px) + 16 * px;
  const h = 22 * px;
  const minX = (6 - cam.x) * px;
  const maxX = (viewW - 6 - cam.x) * px - w;
  const left = Math.max(minX, Math.min(maxX, target.x - w / 2));
  const top = target.y - 18 * px - h;
  ctx.fillStyle = pal.tipBg;
  ctx.beginPath();
  ctx.roundRect(left, top, w, h, 10 * px);
  ctx.fill();
  ctx.strokeStyle = pal.focus;
  ctx.lineWidth = 1 * px;
  ctx.stroke();
  ctx.fillStyle = pal.tipFg;
  ctx.textBaseline = 'middle';
  fillTitle(ctx, labelParts, left + w / 2, top + h / 2, 12 * px);
  ctx.textBaseline = 'alphabetic';
}
