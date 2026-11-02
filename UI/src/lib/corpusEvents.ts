// Avisos do corpus para quem mostra notas e contagens.

/** Algo foi indexado, reindexado ou apagado: quem escuta relê tudo. */
export const CORPUS_CHANGED = 'escolio:corpus-changed';

/** Um lote do job em andamento foi gravado: mais leve que corpus-changed, não pede o diagnóstico de novo. */
export const CORPUS_PROGRESS_EVENT = 'escolio:corpus-progress';

/** Avisa que o job da Fila gravou mais notas: a barra lateral, as vaults e as listas acompanham ao vivo. */
export function notifyCorpusProgress(): void {
  window.dispatchEvent(new Event(CORPUS_PROGRESS_EVENT));
}
