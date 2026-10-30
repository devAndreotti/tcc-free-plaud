/**
 * graphColors.ts — cor automática das pastas de 1º nível no grafo (sem React, testável).
 *
 * Cada pasta de 1º nível escolhe uma das 8 cores da paleta (tokens --graph-1…--graph-8 em
 * index.css) pelo hash do nome: a mesma pasta tem a mesma cor em qualquer sessão, qualquer
 * ordem de carga e qualquer vault. As notas herdam a cor da pasta; a legenda lista as pastas.
 */

/** Quantas cores a paleta tem (tokens --graph-1…--graph-8) */
export const GRAPH_PALETTE_SIZE = 8;

/** Nomes dos tokens CSS, na ordem do índice da paleta */
export const GRAPH_COLOR_TOKENS = Array.from({ length: GRAPH_PALETTE_SIZE }, (_, i) => `--graph-${i + 1}`);

/** Máximo de pastas listadas na legenda; as demais viram contagem */
export const GRAPH_LEGEND_MAX = 8;

/** Hash FNV-1a de 32 bits sobre as unidades UTF-16 do nome: estável entre execuções e engines. */
export function stableHash(name: string): number {
  let h = 0x811c9dc5;
  for (let i = 0; i < name.length; i++) {
    h ^= name.charCodeAt(i);
    h = Math.imul(h, 0x01000193);
  }
  return h >>> 0;
}

/** Índice (0…7) da cor da pasta de 1º nível pelo nome. */
export function folderPaletteIndex(name: string): number {
  return stableHash(name) % GRAPH_PALETTE_SIZE;
}

/**
 * Cor de cada pasta de 1º nível NESTE vault: parte do hash do nome e, se a cor já é de outra pasta,
 * segue para a próxima livre. Nenhuma pasta divide cor enquanto houver até 8; com mais, repete pelo
 * hash. Os nomes entram em ordem alfabética, então o resultado não depende da ordem de carga.
 */
export function assignPaletteSlots(groups: string[]): Map<string, number> {
  const names = [...new Set(groups.filter((g) => g !== ''))].sort((a, b) => a.localeCompare(b, 'pt-BR'));
  const slots = new Map<string, number>();
  const taken = new Set<number>();
  for (const name of names) {
    let slot = folderPaletteIndex(name);
    if (taken.size < GRAPH_PALETTE_SIZE) {
      while (taken.has(slot)) slot = (slot + 1) % GRAPH_PALETTE_SIZE;
      taken.add(slot);
    }
    slots.set(name, slot);
  }
  return slots;
}

/** Nome da pasta de 1º nível de um caminho relativo ("Estudos/Cisco/x.md" → "Estudos"); '' na raiz. */
export function topFolderOf(path: string): string {
  const parts = path.replaceAll('\\', '/').split('/');
  return parts.length > 1 ? parts[0] : '';
}

export interface LegendEntry { name: string; token: string }

/**
 * Legenda: pastas de 1º nível em ordem alfabética, no máximo `max`; o restante vira `overflow`.
 * Recebe os nomes (podem repetir) e devolve cada um só uma vez.
 */
export function legendEntries(groups: string[], max = GRAPH_LEGEND_MAX): { shown: LegendEntry[]; overflow: number; total: number } {
  const names = [...new Set(groups.filter((g) => g !== ''))].sort((a, b) => a.localeCompare(b, 'pt-BR'));
  const slots = assignPaletteSlots(names);
  const shown = names.slice(0, max).map((name) => ({ name, token: GRAPH_COLOR_TOKENS[slots.get(name) ?? folderPaletteIndex(name)] }));
  return { shown, overflow: names.length - shown.length, total: names.length };
}
