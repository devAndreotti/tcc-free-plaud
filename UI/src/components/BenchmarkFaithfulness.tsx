import type { BenchmarkFaithfulness } from '../services/bridge';
import { barWidth, clamp01, fmt2, fmt3, isFiniteNumber, validInterval } from './benchmarkFormat';

const count = (v: unknown) => (isFiniteNumber(v) ? v.toLocaleString('pt-BR') : '—');

interface Props {
  faithfulness: BenchmarkFaithfulness;
  /** Profundidade da recuperação (corpus.retrieval_depth), para a nota sobre chunks fora do topo. */
  depth?: number;
}

const BenchmarkFaithfulnessSection = ({ faithfulness: f, depth }: Props) => {
  const score = isFiniteNumber(f.score) && f.score >= 0 && f.score <= 1 ? f.score : undefined;
  const hasInterval = validInterval(f.ci_lower, f.ci_upper);
  const intervalLabel = hasInterval ? `IC 95% [${fmt2(f.ci_lower)} – ${fmt2(f.ci_upper)}]` : 'intervalo indisponível';
  const judge = typeof f.judge_model === 'string' && f.judge_model.trim() ? f.judge_model.trim() : '—';
  const depthNote = isFiniteNumber(depth) && depth > 0
    ? ` Um chunk citado fora dos ${depth} primeiros conta como não suportado.`
    : '';
  const scoreText = score === undefined ? '—' : fmt3(score);

  return (
    <section className="card bench__faith" aria-label="Faithfulness">
      <div className="bench__head">
        <div>
          <h2>Faithfulness</h2>
          <p className="bench__head-sub">
            Afirmações da resposta que o trecho citado sustenta, julgadas por um modelo forte, offline.
          </p>
        </div>
      </div>
      <div className="bench__faith-value">
        <span className="bench__faith-big">{scoreText}</span>
        <span className="bench__faith-ci">{intervalLabel}</span>
      </div>
      <div className="bench__track bench__track--faith" role="img" aria-label={`Faithfulness ${scoreText}, ${intervalLabel}`}>
        {score !== undefined && <div className="bench__fill bench__fill--ok" style={{ width: barWidth(clamp01(score)) }} />}
      </div>
      <dl className="bench__faith-list">
        <div><dt>Afirmações avaliadas</dt><dd className="mono">{count(f.claims)}</dd></div>
        <div><dt>Veredito ilegível</dt><dd className="mono">{count(f.unparsed)}</dd></div>
        <div><dt>Juiz</dt><dd className="mono">{judge}</dd></div>
      </dl>
      <p className="bench__caption bench__caption--flat">
        Mede suporte no trecho citado, não verdade no mundo.{depthNote}
      </p>
    </section>
  );
};

export default BenchmarkFaithfulnessSection;
