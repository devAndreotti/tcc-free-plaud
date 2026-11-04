import { useEffect } from 'react';
import type { BenchmarkCompareResult, BenchmarkRunRow, BenchmarkStrategySummary } from '../services/bridge';
import { decidedRight, foundNote, isNegative, otherModeRun, withAi } from '../lib/benchmarkView';
import { STRATEGY_ORDER, fmt3, ms, nameOf, pct } from './benchmarkFormat';
import './BenchmarkRun.css';

export const Hint = ({ term, text, right }: { term: string; text: string; right?: boolean }) => (
  <button type="button" className={`dica${right ? ' dica--dir' : ''}`} aria-label={`O que é ${term}: ${text}`}>
    ?<span className="dica__t" role="tooltip">{text}</span>
  </button>
);

const onePlace = (value: number) => (value * 100).toFixed(1).replace('.', ',');

interface SummaryNumbers {
  found: number;
  positives: number;
  right: number;
  total: number;
  hybrid: BenchmarkStrategySummary | undefined;
  accuracy: number | null;
  other: BenchmarkRunRow | null;
  ai: boolean;
}

const numbersOf = (result: BenchmarkCompareResult, runs: BenchmarkRunRow[]): SummaryNumbers => {
  const rows = result.corpus?.queries?.hybrid ?? [];
  const positives = rows.filter((row) => !isNegative(row));
  const hybrid = result.corpus?.summaries.hybrid ?? result.summaries.hybrid;
  return {
    found: positives.filter(foundNote).length,
    positives: positives.length,
    right: rows.filter(decidedRight).length,
    total: rows.length,
    hybrid,
    accuracy: hybrid?.abstention?.accuracy ?? null,
    other: otherModeRun(runs, result),
    ai: withAi(result.answer_provider),
  };
};

const StatTile = ({ label, hint, value, sub }: { label: string; hint: React.ReactNode; value: string; sub: string }) => (
  <div className="bench-stat">
    <span className="bench-stat__label">{label}{hint}</span>
    <b className="mono">{value}</b>
    <span className="bench-stat__sub">{sub}</span>
  </div>
);

const DecisionBar = ({ label, total, right, wrong, rightText, wrongText }: { label: string; total: number; right: number; wrong: number; rightText: string; wrongText: string }) => (
  <div className="bench-dec">
    <div className="bench-dec__head"><b>{label}</b><span>{total} perguntas</span></div>
    <div className="bench-dec__bar mono">
      {right > 0 && <span className="bench-dec__ok" style={{ width: `${(right / total) * 100}%` }}>{right} {rightText}</span>}
      {wrong > 0 && <span className="bench-dec__err" style={{ width: `${(wrong / total) * 100}%` }}>{wrong} {wrongText}</span>}
    </div>
  </div>
);

interface BenchmarkSummaryProps {
  result: BenchmarkCompareResult;
  runs: BenchmarkRunRow[];
  onOpenRun: (comparisonId: string) => void;
}

/** O que a rodada mostra: a conclusão, os quatro números, as três buscas e as decisões do chat. */
const BenchmarkSummary = ({ result, runs, onOpenRun }: BenchmarkSummaryProps) => {
  const n = numbersOf(result, runs);
  const corpus = result.corpus;
  if (!corpus?.queries?.hybrid?.length || !n.hybrid) return null;
  const rows = corpus.queries.hybrid;
  const positives = rows.filter((row) => !isNegative(row));
  const negatives = rows.filter(isNegative);
  const answeredPos = positives.filter((row) => row.answered).length;
  const answeredNeg = negatives.filter((row) => row.answered).length;
  const strategies = STRATEGY_ORDER.map((id) => corpus.summaries[id]).filter(Boolean);
  const accuracy = n.accuracy == null ? '' : `${pct(n.accuracy)}%`;
  const otherAccuracy = n.other?.accuracy == null ? null : `${pct(n.other.accuracy)}%`;
  const switchTo = (ai: boolean) => {
    if (ai !== n.ai && n.other) onOpenRun(n.other.comparison_id);
  };
  const noOther = n.other ? undefined : 'Rode esta suíte no outro modo para comparar.';

  return (
    <>
      <div className="bench-lead">
        <p className="bench__thesis">
          A híbrida achou a nota certa em {n.found} de {n.positives} perguntas. Saber quando recusar é mais difícil: {n.ai ? 'com IA' : 'sem IA'}, decidiu certo em {accuracy} das vezes.
        </p>
        <div className="bench-chips" role="group" aria-label="Com ou sem IA">
          <button type="button" className="bench-chip" aria-pressed={!n.ai} disabled={n.ai && !n.other} title={n.ai ? noOther : undefined} onClick={() => switchTo(false)}>Sem IA</button>
          <button type="button" className="bench-chip" aria-pressed={n.ai} disabled={!n.ai && !n.other} title={!n.ai ? noOther : undefined} onClick={() => switchTo(true)}>Com IA</button>
        </div>
      </div>

      <div className="bench-stats">
        <StatTile
          label="Achou a nota certa (top 3)"
          hint={<Hint term="Recall@3" text="Em quantas perguntas a nota certa apareceu entre os 3 primeiros trechos." />}
          value={`${n.found} de ${n.positives}`}
          sub={`Recall@3: ${onePlace(n.hybrid.recall_at_3)}%`}
        />
        <StatTile
          label="Primeiro acerto (MRR)"
          hint={<Hint term="MRR" text="Quanto mais perto do topo vem o primeiro trecho certo. 1 é sempre em primeiro lugar; 0,5 é em média em segundo." />}
          value={fmt3(n.hybrid.mrr)}
          sub={n.hybrid.mrr_ci ? `95%: ${fmt3(n.hybrid.mrr_ci[0])} a ${fmt3(n.hybrid.mrr_ci[1])}` : 'híbrida'}
        />
        <StatTile
          label="Decidiu certo"
          hint={<Hint term="decisão certa" text="Responder o que está nas notas e recusar o que não está. É o que mais pesa num assistente de notas." />}
          value={`${n.right} de ${n.total}`}
          sub={`${n.ai ? 'com IA' : 'sem IA'}: ${accuracy}${otherAccuracy ? ` · ${n.ai ? 'sem IA' : 'com IA'}: ${otherAccuracy}` : ''}`}
        />
        <StatTile
          label="Busca por pergunta"
          hint={<Hint term="p95" text="Tempo médio para achar os trechos, sem a IA escrever. O p95 é o limite de 95% das buscas." right />}
          value={ms(n.hybrid.avg_query_latency_ms)}
          sub={n.hybrid.p95_query_latency_ms != null ? `p95: ${ms(n.hybrid.p95_query_latency_ms)}` : 'média da híbrida'}
        />
      </div>

      <div className="bench-pair">
        <section className="card" aria-label="As três buscas">
          <div className="card__head"><h2>As três buscas</h2><span className="card__count">latência média</span></div>
          <div className="bench-strats">
            {strategies.map((strategy) => (
              <div key={strategy.strategy} className={`bench-strat bench-strat--${strategy.strategy}`}>
                <span className="bench-strat__name"><b>{nameOf(strategy.strategy).label}</b><small>{nameOf(strategy.strategy).sub}</small></span>
                <span className="bench-strat__bars">
                  <span className="bench-strat__row">Recall@3<span className="bench-strat__track"><span className="bench-strat__fill" style={{ width: `${strategy.recall_at_3 * 100}%` }} /></span><b className="mono">{onePlace(strategy.recall_at_3)}%</b></span>
                  <span className="bench-strat__row">MRR<span className="bench-strat__line">
                    {strategy.mrr_ci && <span className="bench-strat__ci" title="Intervalo de 95%" style={{ left: `${strategy.mrr_ci[0] * 100}%`, width: `${(strategy.mrr_ci[1] - strategy.mrr_ci[0]) * 100}%` }} />}
                    <span className="bench-strat__dot" style={{ left: `${strategy.mrr * 100}%` }} />
                  </span><b className="mono">{fmt3(strategy.mrr)}</b></span>
                </span>
                <span className="bench-strat__lat mono">{ms(strategy.avg_query_latency_ms)}</span>
              </div>
            ))}
          </div>
          <p className="bench__caption">A faixa no MRR é o intervalo de 95%. Faixas que se sobrepõem não separam as buscas.</p>
        </section>

        <section className="card" aria-label="Responder ou recusar">
          <div className="card__head"><h2>Responder ou recusar</h2><span className="card__count">{n.ai ? `híbrida com ${result.answer_model ?? 'IA'}` : 'híbrida, sem IA'}</span></div>
          <div className="bench-decs">
            <DecisionBar label="Tinham resposta" total={positives.length} right={answeredPos} wrong={positives.length - answeredPos} rightText="respondeu" wrongText="recusou" />
            <DecisionBar label="Não tinham resposta" total={negatives.length} right={negatives.length - answeredNeg} wrong={answeredNeg} rightText="recusou" wrongText="respondeu" />
          </div>
          <p className="bench__caption">Verde é a decisão certa e vermelho é a errada.</p>
        </section>
      </div>
    </>
  );
};

interface BenchmarkPresentProps {
  result: BenchmarkCompareResult;
  runs: BenchmarkRunRow[];
  onClose: () => void;
}

/** Só a conclusão e os números principais, em letra grande, para gravar ou mostrar à banca. Esc fecha. */
export const BenchmarkPresent = ({ result, runs, onClose }: BenchmarkPresentProps) => {
  const n = numbersOf(result, runs);
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onClose]);
  const suites = [...new Set(runs.map((run) => run.suite_name ?? ''))].filter(Boolean).slice(0, 2);
  const accuracyOf = (suite: string, ai: boolean) => runs.find((run) => run.suite_name === suite && withAi(run.answer_provider) === ai)?.accuracy ?? null;

  return (
    <div className="bench-present" role="dialog" aria-modal="true" aria-label="Modo apresentação">
      <header className="bench-present__head">
        <span className="mono">Escólio · Benchmark · {result.suite_name}</span>
        <button type="button" className="btn" onClick={onClose} autoFocus>Sair</button>
      </header>
      <h1>O algoritmo acha a nota certa em {n.found} de {n.positives} perguntas. O difícil é saber quando não responder.</h1>
      <div className="bench-present__nums">
        <div><span>Achou a nota certa</span><b className="mono">{n.found} de {n.positives}</b><small>{n.hybrid ? `MRR ${fmt3(n.hybrid.mrr)}` : ''}</small></div>
        <div><span>Decidiu certo</span><b className="mono">{n.accuracy == null ? '—' : `${pct(n.accuracy)}%`}</b><small>{n.right} de {n.total} decisões, {n.ai ? 'com IA' : 'sem IA'}</small></div>
        <div><span>Busca por pergunta</span><b className="mono">{n.hybrid ? ms(n.hybrid.avg_query_latency_ms) : '—'}</b><small>média da busca híbrida</small></div>
      </div>
      {suites.length > 0 && (
        <section className="bench-present__bars" aria-label="Decisões certas por suíte">
          {suites.map((suite) => (
            <div key={suite} className="bench-present__suite">
              <b>{suite}</b>
              {[false, true].map((ai) => {
                const value = accuracyOf(suite, ai);
                return value == null ? null : (
                  <div key={String(ai)} className="bench-present__row mono"><span className={ai ? 'is-ai' : ''} style={{ width: `${value * 75}%` }} />{ai ? 'com IA' : 'sem IA'} {pct(value)}%</div>
                );
              })}
            </div>
          ))}
        </section>
      )}
    </div>
  );
};

export default BenchmarkSummary;
