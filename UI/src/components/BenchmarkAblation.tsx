import type { BenchmarkMrrInterval, BenchmarkReranked, BenchmarkStrategySummary } from '../services/bridge';
import {
  STRATEGY_ORDER,
  barWidth,
  clamp01,
  fmt3,
  intervalText,
  isFiniteNumber,
  nameOf,
  validInterval,
} from './benchmarkFormat';

type Interval = BenchmarkMrrInterval | undefined;

interface AblationRow {
  strategy: string;
  base?: number;
  baseCi?: Interval;
  rr?: number;
  rrCi?: Interval;
}

const mrrOf = (summary: BenchmarkStrategySummary | undefined): number | undefined =>
  summary && isFiniteNumber(summary.mrr) ? summary.mrr : undefined;

const intervalOf = (ci: Record<string, BenchmarkMrrInterval> | undefined, strategy: string): Interval => {
  const found = ci?.[strategy];
  return found && validInterval(found.mrr_lower, found.mrr_upper) ? found : undefined;
};

/** Uma linha por estratégia que tenha MRR com e/ou sem reranker. Sem nenhuma, a lista fica vazia. */
function ablationRows(
  baseline: Record<string, BenchmarkStrategySummary>,
  reranked: BenchmarkReranked,
  baselineCi?: Record<string, BenchmarkMrrInterval>
): AblationRow[] {
  const rrSummaries = reranked.summaries ?? {};
  return STRATEGY_ORDER.map((strategy) => ({
    strategy,
    base: mrrOf(baseline[strategy]),
    baseCi: intervalOf(baselineCi, strategy),
    rr: mrrOf(rrSummaries[strategy]),
    rrCi: intervalOf(reranked.ci, strategy),
  })).filter((row) => row.base !== undefined || row.rr !== undefined);
}

const describeValue = (value: number | undefined, ci: Interval) => {
  if (value === undefined) return 'não medido';
  const interval = ci ? `, IC 95% ${intervalText(ci.mrr_lower, ci.mrr_upper)}` : '';
  return `${fmt3(value)}${interval}`;
};

const Bar = ({ tone, value, ci }: { tone: 'base' | 'rr'; value?: number; ci?: Interval }) => {
  if (value === undefined) {
    return (
      <div className="bench__abl-bar">
        <div className="bench__abl-placeholder">não medido</div>
        <span className="bench__val bench__val--muted">—</span>
      </div>
    );
  }
  const lower = ci ? clamp01(ci.mrr_lower) : 0;
  const upper = ci ? clamp01(ci.mrr_upper) : 0;
  return (
    <div className="bench__abl-bar">
      <div className="bench__track" aria-hidden="true">
        <div className={`bench__fill bench__fill--${tone}`} style={{ width: barWidth(value) }} />
        {ci && (
          <div
            className={`bench__whisker bench__whisker--${tone}`}
            style={{ left: barWidth(lower), width: barWidth(upper - lower) }}
          />
        )}
      </div>
      <span className="bench__val">
        {fmt3(value)}
        {ci && <span className="bench__ci">IC {intervalText(ci.mrr_lower, ci.mrr_upper)}</span>}
      </span>
    </div>
  );
};

interface Props {
  /** Linha base: a mesma que o reranker foi comparado (corpus, quando existir). */
  baseline: Record<string, BenchmarkStrategySummary>;
  baselineCi?: Record<string, BenchmarkMrrInterval>;
  reranked: BenchmarkReranked;
}

const BenchmarkAblation = ({ baseline, baselineCi, reranked }: Props) => {
  const rows = ablationRows(baseline, reranked, baselineCi);
  if (rows.length === 0) return null;
  const model = reranked.model?.trim() || 'reranker';

  return (
    <section className="card bench__ablation" aria-label="Ablação do ranking">
      <div className="bench__head">
        <div>
          <h2>Ablação do ranking · MRR</h2>
          <p className="bench__head-sub">RRF sozinho contra RRF + cross-encoder. Traço fino: intervalo de confiança de 95%.</p>
        </div>
        <div className="bench__legend">
          <span><i style={{ background: 'var(--series-2)' }} />Sem reranker</span>
          <span><i style={{ background: 'var(--series-3)' }} />+ {model}</span>
        </div>
      </div>
      <div className="bench__abl-list">
        {rows.map((row) => {
          const name = nameOf(row.strategy);
          const label = `${name.label}: MRR sem reranker ${describeValue(row.base, row.baseCi)}; com ${model} ${describeValue(row.rr, row.rrCi)}`;
          return (
            <div className="bench__abl-row" key={row.strategy}>
              <div className="bench__abl-name">
                <b>{name.label}</b>
                <span>{name.sub}</span>
              </div>
              <div className="bench__abl-bars" role="img" aria-label={label}>
                <Bar tone="base" value={row.base} ci={row.baseCi} />
                <Bar tone="rr" value={row.rr} ci={row.rrCi} />
              </div>
            </div>
          );
        })}
      </div>
      <p className="bench__caption">
        Cada linha compara a mesma estratégia sem e com o reranker, na escala de 0 a 1. O traço sobre a barra e o IC
        abaixo do valor mostram o intervalo de confiança de 95%.
      </p>
    </section>
  );
};

export default BenchmarkAblation;
