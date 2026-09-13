import { useCallback, useMemo, useState } from 'react';
import type { IndexJobSnapshot } from '../services/bridge';
import { useQueueContext } from '../hooks/useQueueContext';
import Dropzone, { type DropzoneToast } from './Dropzone';
import ToastStack from './ToastStack';
import { AlertTriangleIcon, ClockIcon, EyeIcon, FileIcon, FolderIcon, GraphIcon, PlayIcon, QueueIcon, StopIcon, ZapIcon } from './Icons';

const isActiveJob = (snapshot: IndexJobSnapshot | null) => snapshot?.status === 'running';

const formatRate = (value: number, unit: string) => `${value.toFixed(2)} ${unit}`;

const getProgressPercent = (snapshot: IndexJobSnapshot | null) => {
  const progress = snapshot?.progress;
  if (!progress || progress.total_found <= 0) return 0;
  return Math.min(100, (progress.processed_count / progress.total_found) * 100);
};

const QueuePanel = () => {
  // Estado do job vive no QueueContext (acima deste componente), então
  // sobrevive à desmontagem de QueuePanel ao trocar de aba.
  const {
    folderPath,
    setFolderPath,
    job,
    status,
    isBusy,
    watcherActive,
    chooseFolder,
    startJob,
    cancelJob,
    toggleWatcher,
  } = useQueueContext();

  // Toasts são feedback efêmero de UI; não precisam sobreviver ao unmount.
  const [toasts, setToasts] = useState<DropzoneToast[]>([]);

  const progressText = useMemo(() => {
    if (!job?.progress) return '0/0';
    return `${job.progress.processed_count}/${job.progress.total_found}`;
  }, [job]);
  const progressPercent = getProgressPercent(job);

  const dismissToast = useCallback((id: string) => {
    setToasts((prev) => prev.filter((toast) => toast.id !== id));
  }, []);

  const addToast = useCallback((toast: DropzoneToast) => {
    setToasts((prev) => [...prev, toast]);
  }, []);

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
              <FolderIcon size={16} /><span>Escolher pasta</span>
            </button>
            <button type="button" className="queue-panel__button" onClick={startJob} disabled={isBusy || isActiveJob(job)}>
              <PlayIcon size={16} /><span>Indexar</span>
            </button>
            <button type="button" className="queue-panel__button queue-panel__button--danger" onClick={cancelJob} disabled={isBusy || !isActiveJob(job)}>
              <StopIcon size={16} /><span>Cancelar</span>
            </button>
            <button type="button" className="queue-panel__button" onClick={toggleWatcher} disabled={!folderPath && !watcherActive}>
              <EyeIcon size={16} /><span>{watcherActive ? 'Parar monitoramento' : 'Monitorar pasta'}</span>
            </button>
          </div>
        </div>

        <Dropzone watchDirectory={watcherActive ? folderPath : null} onToast={addToast} />

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
              <div className="queue-panel__metric-card">
                <QueueIcon size={16} className="queue-panel__metric-icon" />
                <dt>fase</dt>
                <dd>{job.progress?.phase ?? job.status}</dd>
              </div>
              <div className="queue-panel__metric-card">
                <FileIcon size={16} className="queue-panel__metric-icon" />
                <dt>progresso</dt>
                <dd>{progressText}</dd>
              </div>
              <div className="queue-panel__metric-card">
                <ZapIcon size={16} className="queue-panel__metric-icon" />
                <dt>arquivos/s</dt>
                <dd>{formatRate(job.files_per_second, 'arquivos/s')}</dd>
              </div>
              <div className="queue-panel__metric-card">
                <GraphIcon size={16} className="queue-panel__metric-icon" />
                <dt>chunks/s</dt>
                <dd>{formatRate(job.chunks_per_second, 'chunks/s')}</dd>
              </div>
              <div className="queue-panel__metric-card">
                <ClockIcon size={16} className="queue-panel__metric-icon" />
                <dt>ETA</dt>
                <dd>{job.eta_seconds == null ? '-' : `${job.eta_seconds}s`}</dd>
              </div>
            </dl>

            <div className="queue-panel__progress-row">
              <div
                className="queue-panel__progress"
                role="progressbar"
                aria-label="Progresso do job"
                aria-valuemin={0}
                aria-valuemax={100}
                aria-valuenow={Math.round(progressPercent)}
              >
                {isActiveJob(job) && progressPercent === 0 ? (
                  <div className="queue-panel__progress-bar queue-panel__progress-bar--indeterminate" />
                ) : (
                  <div
                    className="queue-panel__progress-bar"
                    style={{
                      width: `${progressPercent}%`,
                    }}
                  />
                )}
              </div>
              <span className="queue-panel__progress-label">{Math.round(progressPercent)}%</span>
            </div>

            <div className="queue-panel__details">
              <p>{job.progress?.message ?? job.message ?? 'Sem evento de progresso.'}</p>
              {job.progress?.current_path && <code>{job.progress.current_path}</code>}
            </div>

            <section className="queue-panel__errors" aria-label="Últimos erros por arquivo">
              <h2>Últimos erros</h2>
              {job.last_errors.length > 0 ? (
                job.last_errors.map((error) => (
                  <article key={`${error.source_path}-${error.message}`} className="queue-panel__error" role="alert">
                    <AlertTriangleIcon size={16} />
                    <div className="queue-panel__error-body">
                      <span className="queue-panel__error-path">{error.source_path}</span>
                      <p>{error.message}</p>
                    </div>
                  </article>
                ))
              ) : (
                <p>Nenhum erro registrado.</p>
              )}
            </section>
          </section>
        ) : isBusy ? (
          <div className="queue-panel__empty queue-panel__empty--busy">
            <div className="queue-panel__progress" role="status" aria-label="Preparando indexação">
              <div className="queue-panel__progress-bar queue-panel__progress-bar--indeterminate" />
            </div>
            <p>Preparando job de indexação…</p>
          </div>
        ) : (
          <div className="queue-panel__empty">Nenhum job iniciado nesta sessão.</div>
        )}
      </section>
      <ToastStack toasts={toasts} onDismiss={dismissToast} />
    </main>
  );
};

export default QueuePanel;
