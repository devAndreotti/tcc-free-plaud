import { useMemo, useState } from 'react';
import { bridge, type BenchmarkCompareResult, type BenchmarkStrategySummary } from '../services/bridge';
import { CopyIcon, FolderIcon, RefreshIcon } from './Icons';

const STRATEGY_ORDER = ['lexical', 'vector', 'hybrid'];

const STRATEGY_NAME: Record<string, { label: string; lower: string; sub: string }> = {
  lexical: { label: 'Lexical', lower: 'lexical', sub: 'FTS5' },
  vector: { label: 'Vetorial', lower: 'vetorial', sub: 'embeddings' },
  hybrid: { label: 'Híbrida', lower: 'híbrida', sub: 'RRF' },
};

type Metric = 'mrr' | 'recall_at_3' | 'recall_at_5' | 'recall_at_10';
const METRICS: { key: Metric; label: string }[] = [
  { key: 'mrr', label: 'MRR' },
  { key: 'recall_at_3', label: 'Recall@3' },
  { key: 'recall_at_5', label: 'Recall@5' },
  { key: 'recall_at_10', label: 'Recall@10' },
];

const nameOf = (strategy: string) => STRATEGY_NAME[strategy] ?? { label: strategy, lower: strategy, sub: '' };
const fmt3 = (v: number) => v.toLocaleString('pt-BR', { minimumFractionDigits: 3, maximumFractionDigits: 3 });
const pct = (v: number) => (v * 100).toLocaleString('pt-BR', { maximumFractionDigits: 1 });
const ms = (v: number) => `${v.toLocaleString('pt-BR', { maximumFractionDigits: 1 })} ms`;

/** A frase que responde "qual estratégia usar": maior Recall@5, desempate por MRR e depois pela latência. */
function thesis(summaries: BenchmarkStrategySummary[]): string | null {
  if (summaries.length === 0) return null;
  const ranked = [...summaries].sort(
    (a, b) => b.recall_at_5 - a.recall_at_5 || b.mrr - a.mrr || a.avg_query_latency_ms - b.avg_query_latency_ms
  );
  const best = ranked[0];
  const worst = ranked[ranked.length - 1];
  const tied = ranked.filter((s) => s.recall_at_5 === best.recall_at_5);
  if (tied.length > 1) {
    // Empate no Recall@5: dizer quem empata e o que decidiu, em vez de anunciar uma vencedora.
    const names = tied.map((s) => nameOf(s.strategy).lower);
    const who =
      tied.length === ranked.length
        ? `As ${ranked.length === 3 ? 'três' : ranked.length} estratégias`
        : `A ${names.slice(0, -1).join(', a ')} e a ${names[names.length - 1]}`;
    const why =
      best.mrr > tied[1].mrr
        ? `pelo MRR (${fmt3(best.mrr)})`
        : `pela latência (${ms(best.avg_query_latency_ms)} por consulta, com o mesmo MRR)`;
    const gap =
      tied.length < ranked.length
        ? `, ${((best.recall_at_5 - worst.recall_at_5) * 100).toLocaleString('pt-BR', { maximumFractionDigits: 1 })} pontos acima da ${nameOf(worst.strategy).lower}`
        : '';
    return `${who} trazem a fonte certa entre os 5 primeiros trechos em ${pct(best.recall_at_5)}% das perguntas${gap}; a ${nameOf(best.strategy).lower} desempata ${why}.`;
  }
  const head = `A ${nameOf(best.strategy).lower} traz a fonte certa entre os 5 primeiros trechos em ${pct(best.recall_at_5)}% das perguntas`;
  if (ranked.length === 1) return `${head}.`;
  const diff = (best.recall_at_5 - worst.recall_at_5) * 100;
  const latency = best.avg_query_latency_ms - worst.avg_query_latency_ms;
  const cost =
    latency > 0
      ? `e custa ${ms(latency)} a mais por consulta`
      : `e ainda responde ${ms(-latency)} mais rápido por consulta`;
  return `${head}, ${diff.toLocaleString('pt-BR', { maximumFractionDigits: 1 })} pontos acima da ${nameOf(worst.strategy).lower}, ${cost}.`;
}

const RecallChart = ({ summaries }: { summaries: BenchmarkStrategySummary[] }) => {
  const L = 40, R = 452, T = 16, B = 206, H = B - T;
  const y = (v: number) => B - Math.max(0, Math.min(1, v)) * H;
  const gw = (R - L) / Math.max(1, summaries.length);
  const bw = 24, gap = 6, inner = bw * 3 + gap * 2;
  const series: { key: Metric; token: string; k: string }[] = [
    { key: 'recall_at_3', token: 'var(--series-1)', k: '3' },
    { key: 'recall_at_5', token: 'var(--series-2)', k: '5' },
    { key: 'recall_at_10', token: 'var(--series-3)', k: '10' },
  ];
  return (
    <div className="bench__chart">
      <div className="bench__chart-legend">
        {series.map((s) => (
          <span key={s.k}><i style={{ background: s.token }} />k = {s.k}</span>
        ))}
      </div>
      <svg viewBox="0 0 460 250" role="img" aria-label={`Recall@3, @5 e @10 por estratégia: ${summaries.map((s) => `${nameOf(s.strategy).label} ${pct(s.recall_at_10)}% em k=10`).join('; ')}`}>
        {[0, 0.25, 0.5, 0.75, 1].map((t) => (
          <g key={t}>
            <line x1={L} x2={R} y1={y(t)} y2={y(t)} style={{ stroke: t === 0 ? 'var(--border-color)' : 'var(--border-color-subtle)' }} />
            <text x={L - 8} y={y(t) + 3.5} textAnchor="end" className="bench__axis">{String(t).replace('.', ',')}</text>
          </g>
        ))}
        {summaries.map((s, i) => {
          const gx = L + i * gw + (gw - inner) / 2;
          return (
            <g key={s.strategy}>
              {series.map((serie, j) => {
                const v = s[serie.key];
                const x = gx + j * (bw + gap);
                return (
                  <g key={serie.k}>
                    <rect x={x} y={y(v)} width={bw} height={B - y(v)} rx={3} style={{ fill: serie.token }}>
                      <title>{`${nameOf(s.strategy).label} · Recall@${serie.k} ${fmt3(v)}`}</title>
                    </rect>
                    {serie.key === 'recall_at_10' && (
                      <text x={x + bw / 2} y={y(v) - 6} textAnchor="middle" className="bench__value">{fmt3(v)}</text>
                    )}
                  </g>
                );
              })}
              <text x={L + i * gw + gw / 2} y={B + 24} textAnchor="middle" className="bench__group">{nameOf(s.strategy).label}</text>
            </g>
          );
        })}
      </svg>
    </div>
  );
};

const CopyPath = ({ format, path }: { format: string; path: string }) => {
  const [copied, setCopied] = useState(false);
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(path);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1600);
    } catch {
      setCopied(false);
    }
  };
  return (
    <div className="bench__report">
      <span className="bench__fmt mono">{format}</span>
      <code>{path}</code>
      <button type="button" className="btn-icon" aria-label={`Copiar caminho do ${format}`} onClick={copy}>
        {copied ? <span className="bench__copied">copiado</span> : <CopyIcon size={15} />}
      </button>
    </div>
  );
};

const BenchmarkPanel = () => {
  const [suitePath, setSuitePath] = useState('');
  const [result, setResult] = useState<BenchmarkCompareResult | null>(null);
  const [isRunning, setIsRunning] = useState(false);
  const [status, setStatus] = useState('');

  const summaries = useMemo(() => {
    if (!result?.summaries) return [];
    return STRATEGY_ORDER.filter((strategy) => result.summaries[strategy]).map((strategy) => result.summaries[strategy]);
  }, [result]);

  const best = useMemo(() => {
    const out: Partial<Record<Metric | 'latency', number>> = {};
    if (summaries.length < 2) return out;
    METRICS.forEach(({ key }) => { out[key] = Math.max(...summaries.map((s) => s[key])); });
    out.latency = Math.min(...summaries.map((s) => s.avg_query_latency_ms));
    return out;
  }, [summaries]);

  const sentence = useMemo(() => thesis(summaries), [summaries]);
  const questions = summaries[0]?.query_count;

  const handleSelectSuite = async () => {
    try {
      const selected = await bridge.selectBenchmarkSuite();
      if (selected) {
        setSuitePath(selected);
        setStatus('');
      }
    } catch (error) {
      setStatus(error instanceof Error ? error.message : 'Falha ao selecionar suite.');
    }
  };

  const handleRun = async () => {
    const resolvedSuite = suitePath.trim();
    if (!resolvedSuite) {
      setStatus('Escolha a suite.json antes de rodar.');
      return;
    }
    setIsRunning(true);
    setStatus('');
    try {
      const nextResult = await bridge.runBenchmarkCompare(resolvedSuite);
      setResult(nextResult);
      setStatus(`Comparação ${nextResult.comparison_id} concluída.`);
    } catch (error) {
      setResult(null);
      setStatus(error instanceof Error ? error.message : 'Falha ao rodar benchmark.');
    } finally {
      setIsRunning(false);
    }
  };

  const snap = result?.settings_snapshot;

  return (
    <main className="main bench" id="benchmark-panel">
      <header className="page-head">
        <div>
          <h1>Benchmark</h1>
          <p>O mesmo conjunto de perguntas contra as três estratégias de busca.</p>
        </div>
        <div className="page-head__actions">
          <button type="button" className="btn btn--primary" onClick={handleRun} disabled={isRunning || !suitePath.trim()}>
            <RefreshIcon size={14} />
            {isRunning ? 'Rodando…' : 'Rodar comparação'}
          </button>
        </div>
      </header>

      <div className="page-scroll">
        <section className="card queue__source" aria-label="Suite">
          <label className="queue__field">
            <span>suite.json</span>
            <input
              id="benchmark-suite-path"
              className="mono"
              value={suitePath}
              onChange={(event) => setSuitePath(event.target.value)}
              placeholder="data/datasets/suite.json"
            />
          </label>
          <button type="button" className="btn" onClick={handleSelectSuite} disabled={isRunning}>
            <FolderIcon size={15} />
            Selecionar suite
          </button>
        </section>

        {status && <p className="queue__status" role="status">{status}</p>}

        {result && summaries.length > 0 ? (
          <>
            {snap && (
              <div className="bench__snap" aria-label="Configuração usada">
                <span><em>embedding</em>{snap.embedding_model}</span>
                <span><em>device</em>{snap.embedding_device}</span>
                <span><em>top_k</em>{snap.retrieval_top_k}</span>
                <span><em>chunk</em>{snap.default_chunk_size} / {snap.default_chunk_overlap}</span>
                <span><em>resposta</em>{snap.answer_provider}</span>
                <span className="bench__id">
                  <b>{result.comparison_id}</b> · {result.suite_name}
                </span>
              </div>
            )}

            {sentence && <p className="bench__thesis">{sentence}</p>}

            <div className="bench__grid">
              <section className="card">
                <div className="card__head">
                  <h2>Resultado por estratégia</h2>
                  {questions != null && <span className="card__count">{questions} perguntas</span>}
                </div>
                <div className="bench__table-wrap">
                  <table className="data-table">
                    <thead>
                      <tr>
                        <th>Estratégia</th>
                        {METRICS.map((m) => <th key={m.key} className="num">{m.label}</th>)}
                        <th className="num">Latência média</th>
                      </tr>
                    </thead>
                    <tbody>
                      {summaries.map((s) => (
                        <tr key={s.strategy}>
                          <td>
                            <b>{nameOf(s.strategy).label}</b>
                            {nameOf(s.strategy).sub && <span className="bench__sub mono">{nameOf(s.strategy).sub}</span>}
                          </td>
                          {METRICS.map((m) => (
                            <td key={m.key} className="num">
                              {s[m.key] === best[m.key] ? <span className="bench__best">{fmt3(s[m.key])}</span> : fmt3(s[m.key])}
                            </td>
                          ))}
                          <td className="num">
                            {s.avg_query_latency_ms === best.latency
                              ? <span className="bench__best">{ms(s.avg_query_latency_ms)}</span>
                              : ms(s.avg_query_latency_ms)}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <p className="bench__caption">
                  Maior é melhor em MRR e Recall; menor é melhor em latência. Destaque = melhor da coluna.
                </p>
              </section>

              <section className="card">
                <div className="card__head">
                  <h2>Recall@k</h2>
                  <span className="card__count">fração das perguntas</span>
                </div>
                <RecallChart summaries={summaries} />
              </section>
            </div>

            <section className="card" aria-label="Relatórios">
              <div className="card__head"><h2>Relatórios desta comparação</h2></div>
              <CopyPath format="JSON" path={result.json_report_path} />
              <CopyPath format="CSV" path={result.csv_report_path} />
            </section>
          </>
        ) : isRunning ? (
          <div className="card queue__empty">
            <div className="job__bar job__bar--indeterminate" role="status" aria-label="Rodando comparação" />
            <p><b>Rodando lexical, vetorial e híbrida no mesmo conjunto de perguntas…</b></p>
            <p>Cada documento da suite é indexado num corpus temporário antes das perguntas. Leva cerca de meio minuto.</p>
          </div>
        ) : (
          <div className="card queue__empty">
            <p><b>Nenhum benchmark executado nesta sessão.</b></p>
            <p>
              Escolha uma suite.json com perguntas e as notas esperadas. A comparação roda lexical, vetorial e híbrida
              com o mesmo top-k e grava os relatórios em JSON e CSV.
            </p>
          </div>
        )}
      </div>
    </main>
  );
};

export default BenchmarkPanel;
