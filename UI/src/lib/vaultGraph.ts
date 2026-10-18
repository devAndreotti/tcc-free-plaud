/**
 * vaultGraph.ts — montagem, enquadramento e física do grafo do vault (sem React, testável).
 *
 * Cada pasta (pelo caminho completo) vira um nó, cada nota se liga à sua pasta e cada pasta à
 * pasta-mãe: o grafo mostra a árvore do vault.
 */

import type { MarkdownNode } from '../hooks/useVault';

// ─── Tipos internos ──────────────────────────────────────────────────────────

export interface SimNode {
  id: string;
  label: string;
  kind: 'note' | 'folder';
  depth: number; // profundidade da pasta (0 = raiz do vault); notas usam a da pasta + 1
  x: number;     // pixels lógicos (CSS px)
  y: number;
  vx: number;
  vy: number;
  degree: number;
}

export interface SimEdge { source: string; target: string }
export interface Camera { x: number; y: number; scale: number }

// ─── Constantes ──────────────────────────────────────────────────────────────

const REPULSION     = 900;
const ATTRACTION    = 0.05;
const DAMPING       = 0.82;
const CENTER_PULL   = 0.004;
const NOTE_EDGE_LEN = 26;  // nota ↔ pasta
const DIR_EDGE_LEN  = 70;  // pasta ↔ pasta-mãe
const MAX_SPEED     = 30;
const FIT_PADDING   = 24;
const GOLDEN_ANGLE  = 2.399963; // radianos (~137,5°): espalha nós novos sem alinhá-los

// ─── Helpers ─────────────────────────────────────────────────────────────────

function folderOf(path: string): string {
  const parts = path.replaceAll('\\', '/').split('/');
  return parts.slice(0, -1).join('/');
}

export function nodeRadius(n: SimNode): number {
  return n.kind === 'folder' ? Math.min(9, 3.5 + Math.sqrt(n.degree)) : 2.6;
}

// ─── Constrói grafo a partir dos nós do vault ────────────────────────────────

export function buildGraph(
  vaultNodes: MarkdownNode[],
  logW: number,
  logH: number,
  previous: SimNode[] = [],
): { nodes: SimNode[]; edges: SimEdge[] } {
  const cx = logW / 2;
  const cy = logH / 2;
  const kept = new Map(previous.map((n) => [n.id, n]));
  // Posição nova: espiral de ângulo áureo pelo índice do nó (determinística, sem Math.random)
  const place = (id: string, i: number): Pick<SimNode, 'x' | 'y' | 'vx' | 'vy'> => {
    const old = kept.get(id); // rescan do mesmo vault não embaralha o desenho
    if (old) return { x: old.x, y: old.y, vx: 0, vy: 0 };
    const angle = i * GOLDEN_ANGLE;
    const r = 8 * Math.sqrt(i);
    return { x: cx + r * Math.cos(angle), y: cy + r * Math.sin(angle), vx: 0, vy: 0 };
  };

  const nodes: SimNode[] = [];
  const edges: SimEdge[] = [];
  const folders = new Set<string>();

  // Pasta pelo caminho completo: "A/Pessoas" e "B/Pessoas" são nós distintos.
  const ensureFolder = (dir: string): string => {
    const id = `dir:${dir}`;
    if (folders.has(dir)) return id;
    folders.add(dir);
    const parts = dir ? dir.split('/') : [];
    nodes.push({ id, label: parts.at(-1) ?? 'vault', kind: 'folder', depth: parts.length, degree: 0, ...place(id, nodes.length) });
    if (dir) edges.push({ source: ensureFolder(parts.slice(0, -1).join('/')), target: id });
    return id;
  };

  for (const n of vaultNodes) {
    const dir = folderOf(n.path);
    const folderId = ensureFolder(dir);
    const depth = dir ? dir.split('/').length + 1 : 1;
    nodes.push({ id: n.id, label: n.name, kind: 'note', depth, degree: 0, ...place(n.id, nodes.length) });
    edges.push({ source: folderId, target: n.id });
  }

  const deg = new Map<string, number>();
  for (const e of edges) {
    deg.set(e.source, (deg.get(e.source) ?? 0) + 1);
    deg.set(e.target, (deg.get(e.target) ?? 0) + 1);
  }
  for (const n of nodes) n.degree = deg.get(n.id) ?? 0;

  return { nodes, edges };
}

// ─── Câmera que enquadra todos os nós ────────────────────────────────────────

export function fitCamera(nodes: SimNode[], width: number, height: number): Camera {
  if (nodes.length === 0 || width <= 0 || height <= 0) return { x: 0, y: 0, scale: 1 };
  let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
  for (const n of nodes) {
    minX = Math.min(minX, n.x); maxX = Math.max(maxX, n.x);
    minY = Math.min(minY, n.y); maxY = Math.max(maxY, n.y);
  }
  const spanX = Math.max(maxX - minX, 1);
  const spanY = Math.max(maxY - minY, 1);
  const scale = Math.max(1e-4, Math.min(2, (width - 2 * FIT_PADDING) / spanX, (height - 2 * FIT_PADDING) / spanY));
  return {
    scale,
    x: width / 2 - ((minX + maxX) / 2) * scale,
    y: height / 2 - ((minY + maxY) / 2) * scale,
  };
}

// ─── Um tick da simulação ────────────────────────────────────────────────────

export function tick(nodes: SimNode[], edges: SimEdge[], cx: number, cy: number) {
  const map = new Map(nodes.map((n) => [n.id, n]));

  // Repulsão entre todos os pares (ponytail: O(n²); ~740 nós no vault real cabem num frame, Barnes-Hut se passar de alguns milhares)
  for (let i = 0; i < nodes.length; i++) {
    for (let j = i + 1; j < nodes.length; j++) {
      const a = nodes[i], b = nodes[j];
      const dx = b.x - a.x, dy = b.y - a.y;
      const d2 = dx * dx + dy * dy + 0.01;
      const dist = Math.sqrt(d2);
      const f = REPULSION / d2;
      const fx = (dx / dist) * f, fy = (dy / dist) * f;
      a.vx -= fx; a.vy -= fy;
      b.vx += fx; b.vy += fy;
    }
  }

  // Atração pelas arestas (molas com comprimento por tipo de ligação)
  for (const e of edges) {
    const a = map.get(e.source), b = map.get(e.target);
    if (!a || !b) continue;
    const dx = b.x - a.x, dy = b.y - a.y;
    const dist = Math.hypot(dx, dy) || 1;
    const rest = b.kind === 'folder' ? DIR_EDGE_LEN : NOTE_EDGE_LEN;
    const delta = (dist - rest) * ATTRACTION;
    const fx = (dx / dist) * delta, fy = (dy / dist) * delta;
    a.vx += fx; a.vy += fy;
    b.vx -= fx; b.vy -= fy;
  }

  // Atração ao centro, amortecimento e teto de velocidade
  for (const n of nodes) {
    n.vx = (n.vx + (cx - n.x) * CENTER_PULL) * DAMPING;
    n.vy = (n.vy + (cy - n.y) * CENTER_PULL) * DAMPING;
    const speed = Math.hypot(n.vx, n.vy);
    if (speed > MAX_SPEED) { n.vx *= MAX_SPEED / speed; n.vy *= MAX_SPEED / speed; }
    n.x += n.vx; n.y += n.vy;
  }
}
