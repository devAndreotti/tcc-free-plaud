import { useEffect, useState } from 'react';
import { bridge, type BenchmarkRunRow, type BenchmarkSuitePreview as Preview } from '../services/bridge';
import './BenchmarkRun.css';

const DEBOUNCE_MS = 300;

const seconds = (ms: number): string => {
  const total = Math.round(ms / 1000);
  return total >= 60 ? `${Math.floor(total / 60)} min ${String(total % 60).padStart(2, '0')} s` : `${total} s`;
};

interface BenchmarkSuitePreviewProps {
  path: string;
  runs: BenchmarkRunRow[];
  withAnswer: boolean;
}

/** O que a suite escolhida vai perguntar, antes de rodar, e quanto a última rodada igual levou. */
const BenchmarkSuitePreview = ({ path, runs, withAnswer }: BenchmarkSuitePreviewProps) => {
  const [preview, setPreview] = useState<Preview | null>(null);
  const [error, setError] = useState('');

  useEffect(() => {
    const trimmed = path.trim();
    let active = true;
    const timer = window.setTimeout(() => {
      if (!trimmed) {
        setPreview(null);
        setError('');
        return;
      }
      Promise.resolve(bridge.previewBenchmarkSuite?.(trimmed))
        .then((next) => {
          if (!active) return;
          setPreview(next ?? null);
          setError('');
        })
        .catch((reason: unknown) => {
          if (!active) return;
          setPreview(null);
          setError(reason instanceof Error ? reason.message : 'Não foi possível ler esta suite.');
        });
    }, DEBOUNCE_MS);
    return () => {
      active = false;
      window.clearTimeout(timer);
    };
  }, [path]);

  if (error) return <p className="queue__status" role="status">Não foi possível ler esta suite: {error}</p>;
  if (!preview) return null;

  const last = runs.find(
    (run) => run.suite_name === preview.suite_name && (run.answer_provider !== 'extractive') === withAnswer,
  );
  return (
    <details className="bench-preview">
      <summary>
        <b>{preview.suite_name}</b>
        <span className="mono">
          {preview.note_count} notas · {preview.positive_count} com resposta · {preview.negative_count} sem resposta
          {last?.duration_ms != null ? ` · a última rodada levou ${seconds(last.duration_ms)}` : ''}
        </span>
      </summary>
      <ol className="bench-preview__list">
        {preview.questions.map((question, index) => {
          const key = `${index}-${question.question}`;
          return (
            <li key={key}>
              {question.question}
              <small>{question.negative ? 'sem resposta nas notas' : question.note}</small>
            </li>
          );
        })}
      </ol>
    </details>
  );
};

export default BenchmarkSuitePreview;
