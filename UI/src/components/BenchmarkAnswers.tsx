import { useState } from 'react';
import type { BenchmarkAnswerMetrics, BenchmarkStrategySummary } from '../services/bridge';
import { discardText } from '../lib/discardReasons';
import { STRATEGY_ORDER, barWidth, isFiniteNumber, nameOf, pct } from './benchmarkFormat';
import { Segmented } from './ui/Controls';
import { GlyphBadge } from './ui/Glyph';

// Este motivo também conta as perguntas sem resposta no corpus: lá, a IA dizer isso é o certo.
const REASON_HINT: Record<string, string> = {
  generated_no_answer_sentinel: 'Inclui as perguntas sem resposta no corpus, em que dizer isso é o certo.',
  generated_generic_no_answer: 'Inclui as perguntas sem resposta no corpus, em que dizer isso é o certo.',
};

const seconds = (value: number) => `${(value / 1000).toLocaleString('pt-BR', { minimumFractionDigits: 1, maximumFractionDigits: 1 })} s`;

/** Só com IA o resumo traz taxa de aceite; a passada extrativa também tem answer_metrics, com taxa nula. */
const metricsOf = (summary: BenchmarkStrategySummary | undefined): BenchmarkAnswerMetrics | null => {
  const metrics = summary?.answer_metrics;
  return metrics && isFiniteNumber(metrics.accepted_rate) ? metrics : null;
};

interface Props {
  summaries: Record<string, BenchmarkStrategySummary>;
  /** Modelo das Fontes de IA quando a comparação rodou. */
  model?: string | null;
}

/** Resposta da IA nas perguntas do corpus: quantas passaram na conferência e por que as outras foram descartadas. */
const BenchmarkAnswers = ({ summaries, model }: Props) => {
  const strategies = STRATEGY_ORDER.filter((strategy) => metricsOf(summaries[strategy]));
  const [chosen, setChosen] = useState('hybrid');
  const strategy = strategies.includes(chosen) ? chosen : strategies[0];
  const metrics = metricsOf(summaries[strategy]);
  if (!metrics) return null;

  const reasons = Object.entries(metrics.discard_reasons).sort(([, a], [, b]) => b - a);
  const top = reasons[0]?.[1] ?? 0;

  return (
    <section className="card bench__answers" aria-label="Resposta da IA">
      <div className="bench__answers-head">
        <GlyphBadge name="stars" size={32} />
        <div className="bench__answers-title">
          <h2>Resposta da IA</h2>
          <p className="bench__head-sub">
            {model ? `${model} · ` : ''}respostas aceitas pela conferência com os trechos e por que as outras foram descartadas.
          </p>
        </div>
        {strategies.length > 1 && (
          <Segmented
            label="Estratégia da resposta da IA"
            options={strategies.map((value) => ({ value, label: nameOf(value).label }))}
            value={strategy}
            onChange={setChosen}
          />
        )}
      </div>

      <dl className="bench__answers-kpis">
        <div>
          <dt>Aceitas</dt>
          <dd className="mono">{metrics.accepted_count} de {metrics.answer_count}</dd>
          <span>{pct(metrics.accepted_rate ?? 0)}% das respostas</span>
        </div>
        <div>
          <dt>Pergunta inteira · p50</dt>
          <dd className="mono">{seconds(metrics.question_p50_ms)}</dd>
          <span>busca + IA + conferência</span>
        </div>
        <div>
          <dt>p95</dt>
          <dd className="mono">{seconds(metrics.question_p95_ms)}</dd>
          <span>as 5% mais lentas</span>
        </div>
      </dl>

      <div className="bench__answers-reasons">
        <h3>Motivos de descarte</h3>
        {reasons.length === 0 ? (
          <p className="bench__head-sub">Nenhuma resposta da IA foi descartada nesta estratégia.</p>
        ) : (
          <ul>
            {reasons.map(([code, count]) => (
              <li key={code} className="bench__reason">
                <div className="bench__reason-text">
                  <span>{discardText(code)}</span>
                  <code className="mono">{code}</code>
                  {REASON_HINT[code] && <small>{REASON_HINT[code]}</small>}
                </div>
                <div className="bench__track bench__track--thin" aria-hidden="true">
                  <div className="bench__fill bench__fill--warn" style={{ width: barWidth(top > 0 ? count / top : 0) }} />
                </div>
                <b className="mono">{count}</b>
              </li>
            ))}
          </ul>
        )}
      </div>
    </section>
  );
};

export default BenchmarkAnswers;
