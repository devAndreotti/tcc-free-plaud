/**
 * graphSelection.ts — seleção por clique no grafo (sem React, testável).
 *
 * Vizinhança, teste de acerto (hit-test), distinção entre clique e arrasto, enquadramento de uma
 * pasta e o texto que a região aria-live anuncia. O desenho fica em components/graphDraw.ts.
 */

import { fitCamera, nodeRadius, type Camera, type SimEdge, type SimNode } from './vaultGraph';

/** Deslocamento (px na tela) acima do qual o gesto é arrasto, não clique */
export const CLICK_SLOP = 4;

/** Opacidade do que sai da seleção (nó, aresta ou rótulo) */
export const DIM_ALPHA = 0.15;

/** Vizinhos diretos de um nó, por qualquer aresta (árvore ou ligação), nos dois sentidos. */
export function neighborIds(id: string, edges: SimEdge[]): Set<string> {
  const out = new Set<string>();
  for (const e of edges) {
    if (e.source === id) out.add(e.target);
    else if (e.target === id) out.add(e.source);
  }
  return out;
}

/** O nó selecionado e os vizinhos diretos; null quando não há seleção. */
export function selectionSet(id: string | null, edges: SimEdge[]): Set<string> | null {
  if (id === null) return null;
  const set = neighborIds(id, edges);
  set.add(id);
  return set;
}

/** Aresta com as duas pontas na seleção: a ligação do nó ou entre dois vizinhos dele. */
export function edgeInSelection(e: SimEdge, set: Set<string>): boolean {
  return set.has(e.source) && set.has(e.target);
}

/** Nó mais próximo sob o ponto (coordenadas de mundo); folga de 5 px na tela facilita o alvo. */
export function hitTest(nodes: SimNode[], world: { x: number; y: number }, scale: number): SimNode | null {
  let best: SimNode | null = null;
  let bestD2 = Infinity;
  for (const n of nodes) {
    const r = nodeRadius(n) + 5 / scale;
    const d2 = (n.x - world.x) ** 2 + (n.y - world.y) ** 2;
    if (d2 <= r * r && d2 < bestD2) {
      best = n;
      bestD2 = d2;
    }
  }
  return best;
}

/** Clique = soltou a menos de `slop` px do ponto em que apertou. */
export function isClick(from: { x: number; y: number }, to: { x: number; y: number }, slop = CLICK_SLOP): boolean {
  return Math.hypot(to.x - from.x, to.y - from.y) < slop;
}

/** A pasta e tudo abaixo dela na árvore (subpastas e notas). Ligações [[...]] não contam. */
export function folderSubtreeIds(folderId: string, edges: SimEdge[]): Set<string> {
  const children = new Map<string, string[]>();
  for (const e of edges) {
    if (e.kind === 'link') continue;
    const list = children.get(e.source);
    if (list) list.push(e.target);
    else children.set(e.source, [e.target]);
  }
  const out = new Set<string>([folderId]);
  const stack = [folderId];
  while (stack.length > 0) {
    const id = stack.pop()!;
    for (const child of children.get(id) ?? []) {
      if (!out.has(child)) {
        out.add(child);
        stack.push(child);
      }
    }
  }
  return out;
}

/** Câmera que enquadra só os nós de `ids` (o mesmo ajuste de fitCamera, aplicado a um subconjunto). */
export function frameCamera(nodes: SimNode[], ids: Set<string>, width: number, height: number): Camera {
  return fitCamera(nodes.filter((n) => ids.has(n.id)), width, height);
}

/** Interpolação linear entre duas câmeras; t em [0, 1]. */
export function lerpCamera(from: Camera, to: Camera, t: number): Camera {
  return {
    x: from.x + (to.x - from.x) * t,
    y: from.y + (to.y - from.y) * t,
    scale: from.scale + (to.scale - from.scale) * t,
  };
}

/** Texto anunciado ao selecionar: "Selecionado: <nome>, N ligações". */
export function selectionAnnouncement(label: string, linkCount: number): string {
  const ligacoes = linkCount === 1 ? '1 ligação' : `${linkCount} ligações`;
  return `Selecionado: ${label}, ${ligacoes}`;
}
