/**
 * graphLabels.ts — escolha dos rótulos do grafo que não se sobrepõem (sem React, testável).
 *
 * drawLabels (components/graphDraw.ts) mede cada rótulo em coordenadas de tela e pede a este módulo
 * quais cabem. Quem tem prioridade mais alta é desenhado primeiro; um rótulo que sobrepõe um já
 * escolhido é pulado (não é apagado: volta quando o zoom ou a seleção deixar espaço).
 */

/** Caixa de um rótulo em px de tela (já com a folga) */
export interface LabelBox {
  id: string;
  /** menor vence: selecionado 0, vizinhos 1, pastas 2 + profundidade, notas por último */
  priority: number;
  left: number;
  right: number;
  top: number;
  bottom: number;
}

/** Folga (px de tela) em volta de cada rótulo: sem ela, dois textos encostados parecem um só */
export const LABEL_PADDING = 2;

/** Prioridade das notas: abaixo de qualquer pasta (pastas de profundidade até ~100 ainda vêm antes) */
const NOTE_RANK = 1000;

/**
 * Prioridade de um rótulo: selecionado > vizinho da seleção > pasta (a mais rasa primeiro) > nota.
 * `isNeighbor` vale para quem está na seleção sem ser o selecionado (ver selectionSet).
 */
export function labelPriority(
  n: { id: string; kind: 'note' | 'folder'; depth: number },
  selectedId: string | null,
  isNeighbor: boolean,
): number {
  if (n.id === selectedId) return 0;
  if (isNeighbor) return 1;
  if (n.kind === 'folder') return 2 + n.depth;
  return NOTE_RANK;
}

/** Duas caixas se tocam (encostar não conta como sobreposição). */
export function boxesOverlap(a: LabelBox, b: LabelBox): boolean {
  return a.left < b.right && b.left < a.right && a.top < b.bottom && b.top < a.bottom;
}

/**
 * Ids dos rótulos a desenhar. Ordem: prioridade crescente; entre prioridades iguais, a ordem da
 * lista (a do grafo), para o resultado não mudar de um frame para o outro.
 */
export function pickLabels(boxes: LabelBox[]): Set<string> {
  const order = boxes
    .map((box, index) => ({ box, index }))
    .sort((x, y) => x.box.priority - y.box.priority || x.index - y.index);
  const placed: LabelBox[] = [];
  const shown = new Set<string>();
  for (const { box } of order) {
    if (placed.some((p) => boxesOverlap(p, box))) continue;
    placed.push(box);
    shown.add(box.id);
  }
  return shown;
}
