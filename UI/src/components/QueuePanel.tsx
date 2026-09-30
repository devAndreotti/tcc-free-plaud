import { useCallback, useState } from 'react';
import type { IndexJobSnapshot } from '../services/bridge';
import type { SettingsTab } from './SettingsModal';
import { useQueueContext } from '../hooks/useQueueContext';
import Dropzone, { type DropzoneToast } from './Dropzone';
import ToastStack from './ToastStack';
import { FolderIcon, PlayIcon, XCircleIcon } from './Icons';

interface QueuePanelProps {
  onOpenSettings?: (tab?: SettingsTab) => void;
}

const isActiveJob = (snapshot: IndexJobSnapshot | null) => snapshot?.status === 'running';

const STEPS = [
  { label: 'Descoberta', phases: ['discovering'] },
  { label: 'Leitura', phases: ['loading', 'structuring'] },
  { label: 'Embedding', phases: ['warmup', 'embedding'] },
  { label: 'Gravação', phases: ['writing'] },
  { label: 'Commit', phases: ['committed'] },
];

const STATUS: Record<string, { label: string; tone: string }> = {
  running: { label: 'Em andamento', tone: 'accent' },
  success: { label: 'Concluído', tone: 'ok' },
  partial: { label: 'Parcial', tone: 'warn' },
  failed: { label: 'Falhou', tone: 'err' },
  cancelled: { label: 'Cancelado', tone: '' },
};

const num = (value: number, digits = 1) =>
  value.toLocaleString('pt-BR', { minimumFractionDigits: digits, maximumFractionDigits: digits });

const seconds = (ms: number) => `${num(ms / 1000)} s`;

const clock = (iso: string | null | undefined) => {
  if (!iso) return null;
  const date = new Date(iso);
  return Number.isNaN(date.getTime()) ? null : date.toLocaleTimeString('pt-BR');
};

const stepIndex = (snapshot: IndexJobSnapshot) => {
  const phase = snapshot.progress?.phase;
  if (snapshot.status === 'success' || snapshot.status === 'partial' || phase === 'finished') return STEPS.length;
  return STEPS.findIndex((step) => step.phases.includes(phase ?? ''));
};

const JobCard = ({ job, onCancel, busy, onOpenSettings }: {
  job: IndexJobSnapshot;
  onCancel: () => void;
  busy: boolean;
  onOpenSettings?: QueuePanelProps['onOpenSettings'];
}) => {
  const progress = job.progress;
  const total = progress?.total_found ?? job.result?.total_found ?? 0;
  const processed = progress?.processed_count ?? 0;
  const percent = total > 0 ? Math.min(100, (processed / total) * 100) : 0;
  const running = isActiveJob(job);
  const status = STATUS[job.status] ?? { label: job.status, tone: '' };
  const current = stepIndex(job);

  const counts = [
    { key: 'indexed', label: 'indexadas', value: progress?.indexed_count ?? job.result?.indexed_count ?? 0, color: 'var(--accent-blue)' },
    { key: 'unchanged', label: 'inalteradas', value: progress?.unchanged_count ?? job.result?.unchanged_count ?? 0, color: 'color-mix(in srgb, var(--accent-blue-light) 38%, transparent)' },
    { key: 'failed', label: 'com falha', value: progress?.failed_count ?? job.result?.failed_count ?? 0, color: 'var(--err)' },
    { key: 'skipped', label: 'ignoradas', value: progress?.skipped_count ?? job.result?.skipped_count ?? 0, color: 'var(--text-muted)' },
  ];

  const timing = progress
    ? [
        { label: 'warmup', ms: progress.warmup_ms, color: 'var(--text-muted)' },
        { label: 'embedding', ms: progress.embedding_ms, color: 'var(--accent-blue)' },
        { label: 'gravação', ms: progress.writing_ms, color: 'color-mix(in srgb, var(--accent-blue) 55%, var(--text-muted))' },
      ].filter((t) => t.ms > 0)
    : [];
  const timingTotal = timing.reduce((sum, t) => sum + t.ms, 0);
  const started = clock(job.started_at);

  return (
    <article className="card job" aria-label="Job atual">
      <div className="job__top">
        <span className={`pill${status.tone ? ` pill--${status.tone}` : ''}`}>
          <span className="pill__dot" />
          {status.label}
        </span>
        <code className="job__path">{job.source_path}</code>
        <span className="job__when">
          {started && `iniciado ${started} · `}job <span className="mono">{job.job_id}</span>
        </span>
        {running && (
          <button type="button" className="btn btn--sm job__cancel" onClick={onCancel} disabled={busy || job.cancel_requested}>
            {job.cancel_requested ? 'Cancelando…' : 'Cancelar'}
          </button>
        )}
      </div>

      <ol className="job__steps" aria-label="Etapas">
        {STEPS.map((step, i) => {
          const state = i < current ? 'done' : i === current && running ? 'active' : 'todo';
          return (
            <li key={step.label} className={`job__step job__step--${state}`} aria-current={state === 'active' ? 'step' : undefined}>
              <span className="job__step-dot" aria-hidden="true" />
              <b>{step.label}</b>
              {state === 'active' && step.label === 'Embedding' && progress && progress.batch_total > 0 && (
                <span className="mono">lote {progress.batch_index} de {progress.batch_total}</span>
              )}
              {state === 'done' && i === 0 && total > 0 && <span className="mono">{total} arquivos</span>}
            </li>
          );
        })}
      </ol>

      <div className="job__progress">
        <div className="job__big">
          {processed.toLocaleString('pt-BR')}
          <span>de {total.toLocaleString('pt-BR')} arquivos</span>
        </div>
        <span className="job__pct mono">{Math.round(percent)}%</span>
      </div>
      <div
        className={`job__bar${running && percent === 0 ? ' job__bar--indeterminate' : ''}`}
        role="progressbar"
        aria-label="Progresso do job"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={Math.round(percent)}
      >
        {total > 0 &&
          counts.map((c) => (
            <i key={c.key} style={{ width: `${(c.value / total) * 100}%`, background: c.color }} />
          ))}
      </div>
      <div className="job__legend">
        {counts.map((c) => (
          <span key={c.key}>
            <i style={{ background: c.color }} />
            {c.label} <b className="mono">{c.value.toLocaleString('pt-BR')}</b>
          </span>
        ))}
      </div>

      {running && progress?.current_path && (
        <div className="job__current mono">
          <span className="msg__spinner" aria-hidden="true" />
          {progress.current_path}
        </div>
      )}
      {!running && (job.message || progress?.message) && <p className="job__message">{job.message ?? progress?.message}</p>}

      <dl className="job__kpis">
        <div>
          <dt>Arquivos por segundo</dt>
          <dd className="mono">{num(job.files_per_second)}</dd>
        </div>
        <div>
          <dt>Chunks por segundo</dt>
          <dd className="mono">{num(job.chunks_per_second)}</dd>
        </div>
        <div>
          <dt>Tempo restante</dt>
          <dd className="mono">{running && job.eta_seconds != null ? `~${job.eta_seconds} s` : '—'}</dd>
        </div>
        <div>
          <dt>Modo de commit</dt>
          <dd className="mono job__commit">
            {progress
              ? progress.commit_mode_requested === progress.commit_mode_resolved || !progress.commit_mode_resolved
                ? progress.commit_mode_requested || '—'
                : `${progress.commit_mode_requested} → ${progress.commit_mode_resolved}`
              : '—'}
          </dd>
        </div>
      </dl>

      {timingTotal > 0 && (
        <div className="job__timing">
          <div className="job__timing-label">
            <span>Tempo por etapa</span>
            <span className="mono">{seconds(progress?.elapsed_ms ?? timingTotal)}</span>
          </div>
          <div className="job__tbar" role="img" aria-label={timing.map((t) => `${t.label} ${seconds(t.ms)}`).join(', ')}>
            {timing.map((t) => (
              <i key={t.label} style={{ width: `${(t.ms / timingTotal) * 100}%`, background: t.color }} />
            ))}
          </div>
          <div className="job__legend">
            {timing.map((t) => (
              <span key={t.label}>
                <i style={{ background: t.color }} />
                {t.label} <b className="mono">{seconds(t.ms)}</b>
              </span>
            ))}
          </div>
        </div>
      )}

      {job.last_errors.length > 0 && (
        <section className="job__errors" aria-label="Falhas por arquivo">
          <h2>
            Falhas neste job <span className="card__count">{job.last_errors.length}</span>
          </h2>
          {job.last_errors.map((error) => (
            <article key={`${error.source_path}-${error.message}`} className="job__error" role="alert">
              <XCircleIcon size={15} />
              <div className="job__error-body">
                <span className="job__error-path mono">{error.source_path}</span>
                <p>{error.message}</p>
                {error.error_code && <span className="job__error-code mono">{error.error_code}</span>}
              </div>
              {error.error_code === 'AUDIO_MODEL_NOT_READY' && onOpenSettings && (
                <button type="button" className="link-btn" onClick={() => onOpenSettings('voz')}>
                  Abrir Voz
                </button>
              )}
            </article>
          ))}
        </section>
      )}
    </article>
  );
};

const QueuePanel = ({ onOpenSettings }: QueuePanelProps) => {
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

  const dismissToast = useCallback((id: string) => {
    setToasts((prev) => prev.filter((toast) => toast.id !== id));
  }, []);

  const addToast = useCallback((toast: DropzoneToast) => {
    setToasts((prev) => [...prev, toast]);
  }, []);

  const running = isActiveJob(job);

  return (
    <main className="main queue" id="queue-panel">
      <header className="page-head">
        <div>
          <h1>Fila de indexação</h1>
          <p>O que está sendo lido, vetorizado e gravado no corpus. Um job por vez.</p>
        </div>
        <div className="page-head__actions">
          <label className="switch" title={!folderPath && !watcherActive ? 'Escolha uma pasta primeiro' : undefined}>
            <input
              type="checkbox"
              checked={watcherActive}
              onChange={toggleWatcher}
              disabled={!folderPath && !watcherActive}
            />
            <span className="switch__track" aria-hidden="true" />
            Monitorar pasta
          </label>
        </div>
      </header>

      <div className="page-scroll">
        <section className="card queue__source" aria-label="Pasta a indexar">
          <label className="queue__field">
            <span>Pasta</span>
            <input
              value={folderPath}
              onChange={(event) => setFolderPath(event.target.value)}
              placeholder="C:\caminho\do\vault"
              disabled={running}
              className="mono"
            />
          </label>
          <button type="button" className="btn" onClick={chooseFolder} disabled={isBusy || running}>
            <FolderIcon size={15} />
            Escolher pasta
          </button>
          <button type="button" className="btn btn--primary" onClick={startJob} disabled={isBusy || running || !folderPath}>
            <PlayIcon size={14} />
            Indexar
          </button>
        </section>

        {status && <p className="queue__status" role="status">{status}</p>}

        {job ? (
          <JobCard job={job} onCancel={cancelJob} busy={isBusy} onOpenSettings={onOpenSettings} />
        ) : isBusy ? (
          <div className="card queue__empty">
            <div className="job__bar job__bar--indeterminate" role="status" aria-label="Preparando indexação" />
            <p>Preparando o job de indexação…</p>
          </div>
        ) : (
          <div className="card queue__empty">
            <p><b>Nenhum job nesta sessão.</b></p>
            <p>Escolha a pasta do vault e clique em Indexar. Notas que não mudaram desde a última vez são puladas pelo hash.</p>
          </div>
        )}

        <Dropzone watchDirectory={watcherActive ? folderPath : null} onToast={addToast} />
      </div>
      <ToastStack toasts={toasts} onDismiss={dismissToast} />
    </main>
  );
};

export default QueuePanel;
