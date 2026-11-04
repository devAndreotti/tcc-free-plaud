import { useMemo, useState } from 'react';
import { discardText } from '../lib/discardReasons';
import type { BenchmarkQueryRow } from '../services/bridge';
import { STRATEGY_ORDER, nameOf } from './benchmarkFormat';
import './BenchmarkRun.css';

type Filter = 'todas' | 'certas' | 'erradas' | 'com' | 'sem';

const FILTERS: { id: Filter; label: string }[] = [
  { id: 'todas', label: 'Todas' },
  { id: 'certas', label: 'Decisão certa' },
  { id: 'erradas', label: 'Decisão errada' },
  { id: 'com', label: 'Têm resposta' },
  { id: 'sem', label: 'Não têm resposta' },
];

const isNegative = (row: BenchmarkQueryRow) => row.category === 'negativa';
// Certo é responder o que está nas notas e recusar o que não está.
const decidedRight = (row: BenchmarkQueryRow) => (isNegative(row) ? !row.answered : Boolean(row.answered));

const matches = (row: BenchmarkQueryRow, filter: Filter): boolean => {
  if (filter === 'certas') return decidedRight(row);
  if (filter === 'erradas') return !decidedRight(row);
  if (filter === 'com') return !isNegative(row);
  if (filter === 'sem') return isNegative(row);
  return true;
};

const rankText = (row: BenchmarkQueryRow): string => {
  if (isNegative(row)) return 'sem resposta nas notas';
  return row.relevant_rank ? `nota certa em ${row.relevant_rank}º` : 'nota certa não apareceu';
};

const QuestionRow = ({ row }: { row: BenchmarkQueryRow }) => (
  <li className="bench-q">
    <details>
      <summary>
        <span className={`bench-mark bench-mark--${decidedRight(row) ? 'ok' : 'err'}`}>
          {row.answered ? 'Respondeu' : 'Recusou'}
        </span>
        <span className="bench-q__text">{row.question}</span>
        <span className="bench-q__rank mono">{rankText(row)}</span>
      </summary>
      <div className="bench-q__body">
        {row.expected_ref && <p><em>Esperado</em>{row.expected_note_id} · {row.expected_ref}</p>}
        {row.answer && <p className="bench-q__answer"><em>Resposta</em>{row.answer}</p>}
        {!row.answer && row.answered && <p><em>Resposta</em>Esta rodada não guardou o texto da resposta.</p>}
        {row.discard_reason && <p><em>IA descartada</em>{discardText(row.discard_reason)}</p>}
        {row.retrieved.length > 0 && (
          <p>
            <em>Trechos achados</em>
            {row.retrieved.slice(0, 3).map((hit) => `${hit.rank}. ${hit.note_id}`).join(' · ')}
          </p>
        )}
      </div>
    </details>
  </li>
);

/** Cada pergunta da comparação, com a decisão do chat, para conferir uma a uma. */
const BenchmarkQuestions = ({ queries }: { queries: Record<string, BenchmarkQueryRow[]> }) => {
  const strategies = STRATEGY_ORDER.filter((strategy) => queries[strategy]?.length);
  const [strategy, setStrategy] = useState(strategies.includes('hybrid') ? 'hybrid' : strategies[0]);
  const [filter, setFilter] = useState<Filter>('todas');
  const rows = useMemo(() => queries[strategy] ?? [], [queries, strategy]);
  const shown = useMemo(() => rows.filter((row) => matches(row, filter)), [rows, filter]);
  if (strategies.length === 0) return null;

  return (
    <section className="card" aria-label="Perguntas e respostas">
      <div className="card__head">
        <h2>Perguntas e respostas</h2>
        <span className="card__count">{shown.length} de {rows.length}</span>
      </div>
      <div className="bench-q__filters">
        <div className="bench-chips" role="group" aria-label="Estratégia">
          {strategies.map((id) => (
            <button key={id} type="button" className="bench-chip" aria-pressed={id === strategy} onClick={() => setStrategy(id)}>
              {nameOf(id).label}
            </button>
          ))}
        </div>
        <div className="bench-chips" role="group" aria-label="Filtrar perguntas">
          {FILTERS.map(({ id, label }) => (
            <button key={id} type="button" className="bench-chip" aria-pressed={id === filter} onClick={() => setFilter(id)}>
              {label} <span className="mono">{rows.filter((row) => matches(row, id)).length}</span>
            </button>
          ))}
        </div>
      </div>
      {shown.length > 0 ? (
        <ul className="bench-q__list">
          {shown.map((row) => <QuestionRow key={row.sample_id} row={row} />)}
        </ul>
      ) : (
        <p className="bench__caption">Nenhuma pergunta neste filtro.</p>
      )}
    </section>
  );
};

export default BenchmarkQuestions;
