import type { BenchmarkJobState } from '../services/bridge';
import { nameOf } from './benchmarkFormat';
import './BenchmarkRun.css';

const clock = (ms: number): string => {
  const total = Math.max(0, Math.round(ms / 1000));
  const minutes = Math.floor(total / 60);
  return minutes > 0 ? `${minutes} min ${String(total % 60).padStart(2, '0')} s` : `${total} s`;
};

const stageOf = (job: BenchmarkJobState): string => {
  const strategy = job.strategy ? nameOf(job.strategy).label : null;
  if (job.phase === 'corpus') return strategy ? `Fazendo as perguntas · ${strategy}` : 'Fazendo as perguntas';
  return strategy ? `Lendo as notas · ${strategy}` : 'Lendo as notas';
};

// A previsão só aparece com alguma amostra: no começo o modelo ainda está carregando e ela mentiria.
const etaOf = (job: BenchmarkJobState): string | null => {
  if (job.done < Math.max(5, job.total * 0.05) || job.done >= job.total) return null;
  return `faltam cerca de ${clock((job.elapsed_ms / job.done) * (job.total - job.done))}`;
};

interface BenchmarkProgressProps {
  job: BenchmarkJobState;
  onCancel: () => void;
}

/** O que está rodando agora: barra, pergunta atual, últimas decisões e como cancelar. */
const BenchmarkProgress = ({ job, onCancel }: BenchmarkProgressProps) => {
  const percent = Math.min(100, Math.round((job.done / Math.max(job.total, 1)) * 100));
  const eta = etaOf(job);
  return (
    <section className="card bench-run" aria-label="Progresso da comparação">
      <div className="card__head">
        <h2>Rodando {job.suite_name}</h2>
        <button type="button" className="btn" onClick={onCancel}>Cancelar</button>
      </div>
      <div
        className="bench-run__track"
        role="progressbar"
        aria-label="Progresso da comparação"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={percent}
      >
        <span className="bench-run__fill" style={{ width: `${percent}%` }} />
      </div>
      <p className="bench-run__stage">
        <b>{stageOf(job)}</b>
        <span className="mono">
          {job.done} de {job.total} · {clock(job.elapsed_ms)}{eta ? ` · ${eta}` : ''}
        </span>
      </p>
      {job.question && <p className="bench-run__question">{job.question}</p>}
      {job.recent.length > 1 && (
        <ul className="bench-run__recent" aria-label="Últimas perguntas">
          {job.recent.slice(1, 5).map((item, index) => {
            const right = item.negative ? !item.answered : item.answered;
            return (
              <li key={`${item.strategy}-${index}-${item.question}`}>
                <span className={`bench-mark bench-mark--${right ? 'ok' : 'err'}`}>{item.answered ? 'Respondeu' : 'Recusou'}</span>
                <span className="bench-run__recent-text">{item.question}</span>
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
};

export default BenchmarkProgress;
