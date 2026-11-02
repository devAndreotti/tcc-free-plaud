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

/** Usuário pediu menos movimento: na Aparência (data-motion "always"/"never") ou, sem escolha, no sistema operacional */
export function prefersReducedMotion(): boolean {
  const forced = document.documentElement.dataset.motion;
  if (forced) return forced === 'always';
  return typeof window.matchMedia === 'function' && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
}

/**
 * Anima a montagem do grafo quando ele é novo: primeira carga, troca de modo ou vault
 * (mais da metade dos nós é nova). Um rescan que só acrescenta notas não reabre o desenho.
 */
export function shouldAnimateEntry(prevIds: Set<string>, nextIds: string[], modeChanged: boolean): boolean {
  if (nextIds.length === 0) return false;
  if (modeChanged || prevIds.size === 0) return true;
  // Reabre quando a maior parte do desenho anterior sumiu (outra vault); grafo que só cresce (indexação) não reabre.
  const next = new Set(nextIds);
  const gone = [...prevIds].filter((id) => !next.has(id)).length;
  return gone * 2 > prevIds.size;
}

/** Duração do crescimento de um nó que acabou de entrar no grafo. */
export const POP_MS = 450;

/** Tamanho do nó novo neste instante: nasce pequeno, passa um pouco do normal e assenta (1 = normal). */
export function popAt(start: number | undefined, now: number): number {
  if (start === undefined) return 1;
  const t = Math.min(1, Math.max(0, (now - start) / POP_MS));
  const back = 1 + 2.2 * (t - 1) ** 3 + 1.2 * (t - 1) ** 2;
  return 0.2 + 0.8 * back;
}

/** Anel do arquivo em indexação: fase de 0 a 1 que recomeça a cada 1,4 s (0 = perto do nó e visível; 1 = longe e apagado). */
export const ringPhase = (now: number) => (now % 1400) / 1400;

/** Posição exibida de cada nó: interpolação radial do centro (k = 0) até a simulação (k = 1). */
export function projectNodes<T extends { x: number; y: number }>(nodes: T[], cx: number, cy: number, k: number): T[] {
  if (k >= 1) return nodes;
  return nodes.map((n) => ({ ...n, x: cx + (n.x - cx) * k, y: cy + (n.y - cy) * k }));
}
