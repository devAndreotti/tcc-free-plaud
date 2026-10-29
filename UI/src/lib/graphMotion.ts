/**
 * graphMotion.ts — abertura do grafo ao montar ou trocar de modo/vault (sem React, testável).
 *
 * Os nós partem do centro e se abrem até a posição da simulação em ENTRY_MS, com ease-out. É uma
 * escala radial aplicada no desenho e no acerto de clique: a simulação e a física não mudam.
 */

/** Duração da abertura (ms) */
export const ENTRY_MS = 600;

/** Ease-out cúbico; t é limitado a [0, 1] */
export function easeOutCubic(t: number): number {
  const c = Math.min(1, Math.max(0, t));
  return 1 - (1 - c) ** 3;
}

/** Fração da posição final já percorrida (0 no centro, 1 na posição da simulação). */
export function entryAt(startMs: number | null, nowMs: number): number {
  if (startMs === null) return 1;
  return easeOutCubic((nowMs - startMs) / ENTRY_MS);
}

/** Usuário pediu menos movimento no sistema operacional */
export function prefersReducedMotion(): boolean {
  return typeof window.matchMedia === 'function' && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
}

/**
 * Anima a montagem do grafo quando ele é novo: primeira carga, troca de modo ou vault
 * (mais da metade dos nós é nova). Um rescan que só acrescenta notas não reabre o desenho.
 */
export function shouldAnimateEntry(prevIds: Set<string>, nextIds: string[], modeChanged: boolean): boolean {
  if (nextIds.length === 0) return false;
  if (modeChanged || prevIds.size === 0) return true;
  const fresh = nextIds.filter((id) => !prevIds.has(id)).length;
  return fresh * 2 > nextIds.length;
}

/** Posição exibida de cada nó: interpolação radial do centro (k = 0) até a simulação (k = 1). */
export function projectNodes<T extends { x: number; y: number }>(nodes: T[], cx: number, cy: number, k: number): T[] {
  if (k >= 1) return nodes;
  return nodes.map((n) => ({ ...n, x: cx + (n.x - cx) * k, y: cy + (n.y - cy) * k }));
}
