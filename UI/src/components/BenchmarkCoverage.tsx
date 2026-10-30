import type { BenchmarkCoverage, BenchmarkCoverageGroup } from '../services/bridge';
import { barWidth, fmt3, isFiniteNumber } from './benchmarkFormat';

/** Taxa de perguntas (0 a 1). Contagem inválida, grupo sem perguntas ou taxa fora de [0, 1] viram "sem valor". */
const coverageRate = (count: number, n: number): number | undefined => {
  if (!isFiniteNumber(count) || !isFiniteNumber(n) || n <= 0) return undefined;
  const rate = count / n;
  return rate >= 0 && rate <= 1 ? rate : undefined;
};

const questionsText = (n: number) => (n === 1 ? '1 pergunta' : `${n} perguntas`);

const CoverageRow = ({ label, tone, value }: { label: string; tone: 'one' | 'union'; value?: number }) => (
  <div className="bench__cov-row">
    <span>{label}</span>
    <div className="bench__track bench__track--thin" aria-hidden="true">
      {value !== undefined && <div className={`bench__fill bench__fill--${tone}`} style={{ width: barWidth(value) }} />}
    </div>
    <span className={`bench__val${value === undefined ? ' bench__val--muted' : ''}`}>
      {value === undefined ? '—' : fmt3(value)}
    </span>
  </div>
);

const CoverageGroup = ({ group }: { group: BenchmarkCoverageGroup }) => {
  const n = isFiniteNumber(group.n) && group.n > 0 ? group.n : 0;
  const one = coverageRate(group.single_chunk, n);
  const union = coverageRate(group.across_chunks, n);
  const hint = [questionsText(n), group.hint].filter(Boolean).join(' · ');
  const label = group.label || group.id;
  const description = n === 0
    ? `${label}: sem perguntas neste grupo`
    : `${label}: num trecho ${one === undefined ? 'não medido' : fmt3(one)}, entre trechos ${union === undefined ? 'não medido' : fmt3(union)}, ${questionsText(n)}`;
  return (
    <div className="bench__cov-group">
      <div className="bench__cov-head">
        <span className="bench__cov-name">{label}</span>
        <span className="bench__cov-hint">{hint}</span>
      </div>
      <div className="bench__cov-bars" role="img" aria-label={description}>
        <CoverageRow label="Num trecho" tone="one" value={one} />
        <CoverageRow label="Entre trechos" tone="union" value={union} />
      </div>
    </div>
  );
};

interface Props {
  coverage: BenchmarkCoverage;
}

const BenchmarkCoverageSection = ({ coverage }: Props) => {
  const groups = Array.isArray(coverage.groups) ? coverage.groups : [];
  if (groups.length === 0) return null;
  const k = coverage.k;
  const depth = isFiniteNumber(k) && k > 0 ? `nos ${k} primeiros trechos` : 'nos primeiros trechos';

  return (
    <section className="card bench__coverage" aria-label="Cobertura por tipo de pergunta">
      <div className="bench__head">
        <div>
          <h2>Cobertura por tipo de pergunta</h2>
          <p className="bench__head-sub">
            Termos esperados presentes {depth}. A régua antiga exige tudo num trecho só.
          </p>
        </div>
      </div>
      <div className="bench__cov-list">
        {groups.map((group, index) => (
          <CoverageGroup key={`${group.id}-${index}`} group={group} />
        ))}
      </div>
    </section>
  );
};

export default BenchmarkCoverageSection;
