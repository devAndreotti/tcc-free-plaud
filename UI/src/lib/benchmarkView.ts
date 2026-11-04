/**
 * benchmarkView.ts
 * Contas da tela de Benchmark sobre o resultado do backend: nada aqui mede de novo, só agrupa e conta.
 */
import type { BenchmarkCompareResult, BenchmarkQueryRow, BenchmarkRunRow } from '../services/bridge';

export const isNegative = (row: BenchmarkQueryRow): boolean => row.category === 'negativa';
/** Certo é responder o que está nas notas e recusar o que não está. */
export const decidedRight = (row: BenchmarkQueryRow): boolean => (isNegative(row) ? !row.answered : Boolean(row.answered));
export const foundNote = (row: BenchmarkQueryRow): boolean => Boolean(row.relevant_rank && row.relevant_rank <= 3);
export const withAi = (provider: string | null | undefined): boolean => Boolean(provider && provider !== 'extractive');

const SUBTYPES: [string, string, string][] = [
  ['quase-acerto', 'Quase certas', 'A nota quase diz o que foi perguntado, e o chat respondeu mesmo assim.'],
  ['vocabulario-presente', 'Mesmas palavras', 'As palavras estão nas notas, mas a resposta não.'],
  ['fora-do-dominio', 'Fora do assunto', 'Nada nas notas fala disso.'],
];

export interface WhyTile {
  key: string;
  title: string;
  count: number;
  total: number;
  text: string;
  worst: boolean;
}

export type RowFilter = 'todas' | 'certas' | 'erradas' | `g:${string}`;

export const matchesFilter = (row: BenchmarkQueryRow, filter: RowFilter, subtypes: Record<string, string>): boolean => {
  if (filter === 'todas') return true;
  if (filter === 'certas') return decidedRight(row);
  if (filter === 'erradas') return !decidedRight(row);
  if (filter === 'g:recusou') return !isNegative(row) && !row.answered;
  if (filter === 'g:inventou') return isNegative(row) && Boolean(row.answered);
  return isNegative(row) && Boolean(row.answered) && subtypes[row.sample_id] === filter.slice(2);
};

/** Onde o chat errou: pergunta com resposta que ele recusou e, nas sem resposta, cada tipo que ele respondeu. */
export const whyTiles = (rows: BenchmarkQueryRow[], subtypes: Record<string, string>): WhyTile[] => {
  const positives = rows.filter((row) => !isNegative(row));
  const negatives = rows.filter(isNegative);
  const refused = positives.filter((row) => !row.answered);
  const blocked = refused.filter(foundNote).length;
  const tiles: Omit<WhyTile, 'worst'>[] = [{
    key: 'g:recusou',
    title: 'Tinha resposta e recusou',
    count: refused.length,
    total: positives.length,
    text: `${blocked} com a nota certa no top 3: a regra barrou. ${refused.length - blocked} sem a nota: a busca falhou.`,
  }];
  const typed = negatives.some((row) => subtypes[row.sample_id]);
  if (typed) {
    for (const [id, title, text] of SUBTYPES) {
      const group = negatives.filter((row) => subtypes[row.sample_id] === id);
      if (group.length > 0) tiles.push({ key: `g:${id}`, title, count: group.filter((row) => row.answered).length, total: group.length, text });
    }
  } else if (negatives.length > 0) {
    tiles.push({ key: 'g:inventou', title: 'Não tinha e respondeu', count: negatives.filter((row) => row.answered).length, total: negatives.length, text: 'O chat respondeu algo que não está nas notas.' });
  }
  const worst = typed ? Math.max(...tiles.map((tile) => (tile.total ? tile.count / tile.total : 0))) : -1;
  return tiles.map((tile) => ({ ...tile, worst: tile.total > 0 && tile.count / tile.total === worst }));
};

export interface RowGroup {
  name: string;
  rows: BenchmarkQueryRow[];
}

export const groupRows = (rows: BenchmarkQueryRow[], mode: 'decisao' | 'nota'): RowGroup[] => {
  const positives = rows.filter((row) => !isNegative(row));
  const negatives = rows.filter(isNegative);
  if (mode === 'decisao') {
    return [{ name: 'Tinham resposta', rows: positives }, { name: 'Não tinham resposta', rows: negatives }].filter((group) => group.rows.length > 0);
  }
  const notes = [...new Set(positives.map((row) => row.expected_note_id ?? 'sem nota'))];
  const groups = notes.map((note) => ({ name: note.replace(/-/g, ' '), rows: positives.filter((row) => (row.expected_note_id ?? 'sem nota') === note) }));
  return negatives.length > 0 ? [...groups, { name: 'Sem resposta nas notas', rows: negatives }] : groups;
};

/** A rodada mais recente da mesma suite no outro modo (com ou sem IA), para o seletor e a comparação. */
export const otherModeRun = (runs: BenchmarkRunRow[], result: BenchmarkCompareResult): BenchmarkRunRow | null =>
  runs.find((run) => run.suite_name === result.suite_name && withAi(run.answer_provider) !== withAi(result.answer_provider)) ?? null;

const comma = (value: number, digits: number) => value.toFixed(digits).replace('.', ',');
const percent = (value: number | null) => (value == null ? '—' : `${Math.round(value * 100)}%`);

/** Tabela em Markdown para colar no TCC: a rodada mais recente de cada suite, sem IA e com IA. */
export const tccTable = (runs: BenchmarkRunRow[]): string => {
  const suites = [...new Set(runs.map((run) => run.suite_name ?? ''))].filter(Boolean);
  const lines = ['| Suíte | MRR (IC 95%) | Recall@3 | Decisões certas sem IA | Decisões certas com IA |', '|---|---|---|---|---|'];
  for (const suite of suites) {
    const of = (ai: boolean) => runs.find((run) => run.suite_name === suite && withAi(run.answer_provider) === ai) ?? null;
    const plain = of(false);
    const ai = of(true);
    const base = plain ?? ai;
    if (!base) continue;
    const ci = base.mrr_ci ? ` (${comma(base.mrr_ci[0], 3)} a ${comma(base.mrr_ci[1], 3)})` : '';
    const mrr = base.mrr == null ? '—' : `${comma(base.mrr, 3)}${ci}`;
    const recall = base.recall_at_3 == null ? '—' : `${comma(base.recall_at_3 * 100, 1)}%`;
    lines.push(`| ${suite} | ${mrr} | ${recall} | ${percent(plain?.accuracy ?? null)} | ${percent(ai?.accuracy ?? null)} |`);
  }
  lines.push('', 'Busca híbrida. Com IA: a rodada mais recente.');
  if (suites.some((suite) => suite.includes('cego'))) lines.push('O lote cego foi escrito por um agente de IA e ainda não foi revisado pelos autores.');
  return lines.join('\n');
};
