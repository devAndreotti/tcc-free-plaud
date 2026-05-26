import { useCallback, useEffect, useMemo, useState } from 'react';
import { bridge, type IndexJobSnapshot } from '../services/bridge';

const isActiveJob = (snapshot: IndexJobSnapshot | null) => snapshot?.status === 'running';

const formatRate = (value: number, unit: string) => `${value.toFixed(2)} ${unit}`;

const QueuePanel = () => {
  const [folderPath, setFolderPath] = useState('');
  const [job, setJob] = useState<IndexJobSnapshot | null>(null);
  const [status, setStatus] = useState('Pronto.');
  const [isBusy, setIsBusy] = useState(false);

  const progressText = useMemo(() => {
    if (!job?.progress) return '0/0';
    return `${job.progress.processed_count}/${job.progress.total_found}`;
  }, [job]);

  const refreshJob = useCallback(async (jobId: string) => {
    const latest = await bridge.getIndexJob(jobId);
    setJob(latest);
    setStatus(latest.message ?? `Job ${latest.status}.`);
  }, []);

  useEffect(() => {
    const jobId = job?.job_id;
    if (!jobId || job.status !== 'running') return undefined;
    const interval = window.setInterval(() => {
      void refreshJob(jobId);
    }, 1000);
    return () => window.clearInterval(interval);
  }, [job, refreshJob]);

  const chooseFolder = async () => {
    setIsBusy(true);
    try {
      const selected = await bridge.selectFolder();
      if (selected) setFolderPath(selected);
    } catch (error) {
      setStatus(error instanceof Error ? error.message : 'Falha ao escolher pasta.');
    } finally {
      setIsBusy(false);
    }
  };

  const startJob = async () => {
    if (!folderPath.trim()) {
      setStatus('Escolha uma pasta para indexar.');
      return;
    }
    setIsBusy(true);
    setStatus('Criando job de indexação...');
    try {
      const created = await bridge.startIndexJob(folderPath.trim(), false);
      setJob(created);
      setStatus(created.message ?? 'Job criado.');
      if (created.status === 'running') {
        void refreshJob(created.job_id);
      }
    } catch (error) {
      setStatus(error instanceof Error ? error.message : 'Falha ao criar job.');
    } finally {
      setIsBusy(false);
    }
  };

  const cancelJob = async () => {
    if (!job) return;
    setIsBusy(true);
    setStatus('Solicitando cancelamento...');
    try {
      const cancelled = await bridge.cancelIndexJob(job.job_id);
      setJob(cancelled);
      setStatus(cancelled.message ?? 'Cancelamento solicitado.');
    } catch (error) {
      setStatus(error instanceof Error ? error.message : 'Falha ao cancelar job.');
    } finally {
      setIsBusy(false);
    }
  };

  return (
    <main className="main queue-panel" id="queue-panel">
      <section className="queue-panel__main" aria-label="Fila de indexação">
        <div className="queue-panel__toolbar">
          <div>
            <h1 className="queue-panel__title">Fila de indexação</h1>
            <p className="queue-panel__meta">Um job ativo por processo</p>
          </div>
          <div className="queue-panel__actions">
            <button type="button" className="queue-panel__button" onClick={chooseFolder} disabled={isBusy || isActiveJob(job)}>
              Escolher pasta
            </button>
            <button type="button" className="queue-panel__button" onClick={startJob} disabled={isBusy || isActiveJob(job)}>
              Indexar
            </button>
            <button type="button" className="queue-panel__button queue-panel__button--danger" onClick={cancelJob} disabled={isBusy || !isActiveJob(job)}>
              Cancelar
            </button>
          </div>
        </div>

        <label className="queue-panel__path">
          <span>Pasta</span>
          <input
            value={folderPath}
            onChange={(event) => setFolderPath(event.target.value)}
            placeholder="C:\\caminho\\vault"
            disabled={isActiveJob(job)}
          />
        </label>

        <div className="queue-panel__status" role="status">
          {status}
        </div>

        {job ? (
          <section className="queue-panel__job" aria-label="Job atual">
            <div className="queue-panel__job-head">
              <div>
                <span className="queue-panel__eyebrow">job_id</span>
                <code>{job.job_id}</code>
              </div>
              <strong className={`queue-panel__badge queue-panel__badge--${job.status}`}>{job.status}</strong>
            </div>

            <dl className="queue-panel__metrics">
              <div>
                <dt>fase</dt>
                <dd>{job.progress?.phase ?? job.status}</dd>
              </div>
              <div>
                <dt>progresso</dt>
                <dd>{progressText}</dd>
              </div>
              <div>
                <dt>arquivos/s</dt>
                <dd>{formatRate(job.files_per_second, 'arquivos/s')}</dd>
              </div>
              <div>
                <dt>chunks/s</dt>
                <dd>{formatRate(job.chunks_per_second, 'chunks/s')}</dd>
              </div>
              <div>
                <dt>ETA</dt>
                <dd>{job.eta_seconds == null ? '-' : `${job.eta_seconds}s`}</dd>
              </div>
            </dl>

            <div className="queue-panel__progress" aria-label="Progresso do job">
              <div
                className="queue-panel__progress-bar"
                style={{
                  width: `${job.progress && job.progress.total_found > 0
                    ? Math.min(100, (job.progress.processed_count / job.progress.total_found) * 100)
                    : 0}%`,
                }}
              />
            </div>

            <div className="queue-panel__details">
              <p>{job.progress?.message ?? job.message ?? 'Sem evento de progresso.'}</p>
              {job.progress?.current_path && <code>{job.progress.current_path}</code>}
            </div>

            <section className="queue-panel__errors" aria-label="Últimos erros por arquivo">
              <h2>Últimos erros</h2>
              {job.last_errors.length > 0 ? (
                job.last_errors.map((error) => (
                  <article key={`${error.source_path}-${error.message}`} className="queue-panel__error">
                    <code>{error.source_path}</code>
                    <p>{error.message}</p>
                  </article>
                ))
              ) : (
                <p>Nenhum erro registrado.</p>
              )}
            </section>
          </section>
        ) : (
          <div className="queue-panel__empty">Nenhum job iniciado nesta sessão.</div>
        )}
      </section>
    </main>
  );
};

export default QueuePanel;
