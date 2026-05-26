import { useMemo, useState } from 'react';
import { bridge, type BenchmarkCompareResult } from '../services/bridge';

const STRATEGY_ORDER = ['lexical', 'vector', 'hybrid'];

const formatMetric = (value: number | undefined) =>
  typeof value === 'number' ? value.toFixed(3) : '-';

const formatLatency = (value: number | undefined) =>
  typeof value === 'number' ? `${value.toFixed(1)} ms` : '-';

const BenchmarkPanel = () => {
  const [suitePath, setSuitePath] = useState('');
  const [result, setResult] = useState<BenchmarkCompareResult | null>(null);
  const [isRunning, setIsRunning] = useState(false);
  const [status, setStatus] = useState('Selecione uma suite.json para comparar lexical, vector e hybrid.');

  const summaries = useMemo(() => {
    if (!result) return [];
    return STRATEGY_ORDER
      .filter((strategy) => result.summaries[strategy])
      .map((strategy) => result.summaries[strategy]);
  }, [result]);

  const handleSelectSuite = async () => {
    try {
      const selected = await bridge.selectBenchmarkSuite();
      if (selected) {
        setSuitePath(selected);
        setStatus('Suite selecionada.');
      }
    } catch (error) {
      setStatus(error instanceof Error ? error.message : 'Falha ao selecionar suite.');
    }
  };

  const handleRun = async () => {
    const resolvedSuite = suitePath.trim();
    if (!resolvedSuite) {
      setStatus('Informe o caminho da suite.json.');
      return;
    }
    setIsRunning(true);
    setStatus('Rodando benchmark compare...');
    try {
      const nextResult = await bridge.runBenchmarkCompare(resolvedSuite);
      setResult(nextResult);
      setStatus(`Benchmark ${nextResult.comparison_id} finalizado.`);
    } catch (error) {
      setResult(null);
      setStatus(error instanceof Error ? error.message : 'Falha ao rodar benchmark.');
    } finally {
      setIsRunning(false);
    }
  };

  return (
    <main className="main benchmark-panel" id="benchmark-panel">
      <section className="benchmark-panel__header" aria-label="Benchmark">
        <div>
          <h1 className="benchmark-panel__title">Benchmark</h1>
          <p className="benchmark-panel__meta">Compare estratégias e exporte resultados reproduzíveis.</p>
        </div>
        <div className="benchmark-panel__actions">
          <button
            type="button"
            className="benchmark-panel__button"
            onClick={handleSelectSuite}
            disabled={isRunning}
          >
            Selecionar suite
          </button>
          <button
            type="button"
            className="benchmark-panel__button benchmark-panel__button--primary"
            onClick={handleRun}
            disabled={isRunning}
          >
            Rodar compare
          </button>
        </div>
      </section>

      <section className="benchmark-panel__input" aria-label="Suite">
        <label htmlFor="benchmark-suite-path">suite.json</label>
        <input
          id="benchmark-suite-path"
          value={suitePath}
          onChange={(event) => setSuitePath(event.target.value)}
          placeholder="D:\\Dev\\Repos\\Own\\tcc-free-plaud\\data\\datasets\\suite.json"
        />
      </section>

      <section className="benchmark-panel__results" aria-label="Resultados">
        {result ? (
          <>
            <div className="benchmark-panel__summary">
              <div>
                <span>comparison_id</span>
                <strong>{result.comparison_id}</strong>
              </div>
              <div>
                <span>suite</span>
                <strong>{result.suite_name}</strong>
              </div>
            </div>

            <div className="benchmark-panel__table-wrap">
              <table className="benchmark-panel__table">
                <thead>
                  <tr>
                    <th>estratégia</th>
                    <th>casos</th>
                    <th>queries</th>
                    <th>MRR</th>
                    <th>Recall@3</th>
                    <th>latência média</th>
                  </tr>
                </thead>
                <tbody>
                  {summaries.map((summary) => (
                    <tr key={summary.strategy}>
                      <td>{summary.strategy}</td>
                      <td>{summary.case_count}</td>
                      <td>{summary.query_count}</td>
                      <td>{formatMetric(summary.mrr)}</td>
                      <td>{formatMetric(summary.recall_at_3)}</td>
                      <td>{formatLatency(summary.avg_query_latency_ms)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div className="benchmark-panel__exports">
              <div>
                <span>JSON</span>
                <code>{result.json_report_path}</code>
              </div>
              <div>
                <span>CSV</span>
                <code>{result.csv_report_path}</code>
              </div>
            </div>

            {result.settings_snapshot && (
              <dl className="benchmark-panel__snapshot">
                <div>
                  <dt>embedding_model</dt>
                  <dd>{result.settings_snapshot.embedding_model}</dd>
                </div>
                <div>
                  <dt>embedding_device</dt>
                  <dd>{result.settings_snapshot.embedding_device}</dd>
                </div>
                <div>
                  <dt>default_ask_strategy</dt>
                  <dd>{result.settings_snapshot.default_ask_strategy}</dd>
                </div>
                <div>
                  <dt>retrieval_top_k</dt>
                  <dd>{result.settings_snapshot.retrieval_top_k}</dd>
                </div>
                <div>
                  <dt>chunk</dt>
                  <dd>
                    {result.settings_snapshot.default_chunk_size}/
                    {result.settings_snapshot.default_chunk_overlap}
                  </dd>
                </div>
                <div>
                  <dt>answer_provider</dt>
                  <dd>{result.settings_snapshot.answer_provider}</dd>
                </div>
              </dl>
            )}
          </>
        ) : (
          <div className="benchmark-panel__empty">Nenhum benchmark executado nesta sessão.</div>
        )}
      </section>

      <div className="benchmark-panel__status" role="status">
        {status}
      </div>
    </main>
  );
};

export default BenchmarkPanel;
