import { useMemo, useState } from 'react';
import type { BenchmarkRunRow } from '../services/bridge';
import { fmt3, pct } from './benchmarkFormat';
import './BenchmarkRun.css';

const whenText = (iso: string | null): string => {
  if (!iso) return '—';
  const date = new Date(iso);
  return Number.isNaN(date.getTime())
    ? '—'
    : date.toLocaleString('pt-BR', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' });
};

const durationText = (ms: number | null): string => {
  if (ms == null) return '—';
  const seconds = Math.round(ms / 1000);
  return seconds >= 60 ? `${Math.floor(seconds / 60)} min ${String(seconds % 60).padStart(2, '0')} s` : `${seconds} s`;
};

const modeText = (run: BenchmarkRunRow): string =>
  run.answer_provider === 'extractive' ? 'Sem IA' : run.answer_model ?? 'Com IA';

const percentOf = (value: number | null): string => (value == null ? '—' : `${pct(value)}%`);

type Metric = 'mrr' | 'recall_at_3' | 'accuracy' | 'answered_positive_rate' | 'abstention_recall';
const COMPARED: { key: Metric; label: string; percent: boolean }[] = [
  { key: 'mrr', label: 'MRR', percent: false },
  { key: 'recall_at_3', label: 'Recall@3', percent: false },
  { key: 'accuracy', label: 'Decisão certa', percent: true },
  { key: 'answered_positive_rate', label: 'Responde quando há resposta', percent: true },
  { key: 'abstention_recall', label: 'Se abstém quando não há', percent: true },
];

const SideBySide = ({ first, second }: { first: BenchmarkRunRow; second: BenchmarkRunRow }) => (
  <div className="bench__table-wrap bench-compare" role="group" aria-label="Comparação entre rodadas">
    <table className="data-table">
      <thead>
        <tr>
          <th>Híbrida</th>
          <th className="num">{first.suite_name} <small>{modeText(first)}</small></th>
          <th className="num">{second.suite_name} <small>{modeText(second)}</small></th>
          <th className="num">Diferença</th>
        </tr>
      </thead>
      <tbody>
        {COMPARED.map(({ key, label, percent }) => {
          const a = first[key];
          const b = second[key];
          const delta = a != null && b != null ? b - a : null;
          const sign = delta != null && delta > 0 ? '+' : '';
          return (
            <tr key={key}>
              <td><b>{label}</b></td>
              <td className="num">{percent ? percentOf(a) : a == null ? '—' : fmt3(a)}</td>
              <td className="num">{percent ? percentOf(b) : b == null ? '—' : fmt3(b)}</td>
              <td className="num">
                {delta == null ? '—' : percent ? `${sign}${pct(delta)} p.p.` : `${sign}${fmt3(delta)}`}
              </td>
            </tr>
          );
        })}
      </tbody>
    </table>
  </div>
);

interface BenchmarkHistoryProps {
  runs: BenchmarkRunRow[];
  currentId?: string;
  onOpen: (comparisonId: string) => void;
}

/** Rodadas já gravadas: reabrir sem rodar de novo e comparar duas lado a lado (calibrado e cego, por exemplo). */
const BenchmarkHistory = ({ runs, currentId, onOpen }: BenchmarkHistoryProps) => {
  const [selected, setSelected] = useState<string[]>([]);
  const toggle = (id: string) =>
    setSelected((current) => (current.includes(id) ? current.filter((item) => item !== id) : [...current.slice(-1), id]));
  const pair = useMemo(
    () => selected.map((id) => runs.find((run) => run.comparison_id === id)).filter((run): run is BenchmarkRunRow => Boolean(run)),
    [selected, runs],
  );
  if (runs.length === 0) return null;

  return (
    <section className="card" aria-label="Rodadas anteriores">
      <div className="card__head">
        <h2>Rodadas anteriores</h2>
        <span className="card__count">marque duas para comparar</span>
      </div>
      {pair.length === 2 && <SideBySide first={pair[0]} second={pair[1]} />}
      <div className="bench__table-wrap bench-history">
        <table className="data-table">
          <thead>
            <tr>
              <th aria-label="Comparar" />
              <th>Suíte</th>
              <th>Quando</th>
              <th>Modo</th>
              <th className="num">MRR</th>
              <th className="num">Recall@3</th>
              <th className="num">Decisão certa</th>
              <th className="num">Duração</th>
              <th aria-label="Abrir" />
            </tr>
          </thead>
          <tbody>
            {runs.map((run) => (
              <tr key={run.comparison_id} className={run.comparison_id === currentId ? 'is-current' : undefined}>
                <td>
                  <input
                    type="checkbox"
                    aria-label={`Comparar ${run.suite_name} de ${whenText(run.started_at)}`}
                    checked={selected.includes(run.comparison_id)}
                    onChange={() => toggle(run.comparison_id)}
                  />
                </td>
                <td><b>{run.suite_name}</b></td>
                <td className="mono">{whenText(run.started_at)}</td>
                <td>{modeText(run)}</td>
                <td className="num">{run.mrr == null ? '—' : fmt3(run.mrr)}</td>
                <td className="num">{run.recall_at_3 == null ? '—' : fmt3(run.recall_at_3)}</td>
                <td className="num">{percentOf(run.accuracy)}</td>
                <td className="num">{durationText(run.duration_ms)}</td>
                <td>
                  <button
                    type="button"
                    className="btn bench-history__open"
                    aria-label={`Abrir ${run.suite_name} de ${whenText(run.started_at)}`}
                    disabled={run.comparison_id === currentId}
                    onClick={() => onOpen(run.comparison_id)}
                  >
                    Abrir
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
};

export default BenchmarkHistory;
