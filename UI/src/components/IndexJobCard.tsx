import { useEffect, useRef, useState } from 'react';
import type { IndexJobSnapshot } from '../services/bridge';
import type { SettingsTab } from './SettingsModal';
import JobFailures from './JobFailures';
import { Glyph, type GlyphName } from './ui/Glyph';

// Etapas do job, na ordem das fases que o backend emite (corpus/models.py::CorpusIndexProgress.phase).
const STEPS: { label: string; phases: string[]; icon: GlyphName }[] = [
  { label: 'Descoberta', phases: ['discovering'], icon: 'search' },
  { label: 'Leitura', phases: ['loading', 'structuring'], icon: 'notes' },
  { label: 'Modelo de busca semântica', phases: ['warmup', 'embedding'], icon: 'graph' },
  { label: 'Gravação', phases: ['writing'], icon: 'db' },
  { label: 'Commit', phases: ['committed'], icon: 'check' },
];

const STATUS: Record<string, { label: string; tone: string }> = {
  running: { label: 'Em andamento', tone: 'accent' },
  success: { label: 'Concluído', tone: 'ok' },
  partial: { label: 'Parcial', tone: 'warn' },
  failed: { label: 'Falhou', tone: 'err' },
  cancelled: { label: 'Cancelado', tone: '' },
};

const FILE_STATUS: Record<string, { label: string; tone: string }> = {
  success: { label: 'indexada', tone: 'accent' },
  unchanged: { label: 'inalterada', tone: '' },
  failed: { label: 'com falha', tone: 'err' },
  cancelled: { label: 'cancelada', tone: '' },
};

const num = (value: number, digits = 1) => value.toLocaleString('pt-BR', { minimumFractionDigits: digits, maximumFractionDigits: digits });
const seconds = (ms: number) => `${num(ms / 1000)} s`;
const clock = (iso: string | null | undefined) => {
  if (!iso) return null;
  const date = new Date(iso);
  return Number.isNaN(date.getTime()) ? null : date.toLocaleTimeString('pt-BR');
};
const basename = (path: string) => path.split(/[\\/]/).findLast(Boolean) ?? path;
const relative = (path: string, root: string) => {
  const clean = (value: string) => value.replace(/[\\/]+$/, '');
  return path.toLowerCase().startsWith(clean(root).toLowerCase()) ? path.slice(clean(root).length).replace(/^[\\/]/, '') : basename(path);
};

const stepIndex = (job: IndexJobSnapshot) => {
  const phase = job.progress?.phase;
  if (job.status === 'success' || job.status === 'partial' || phase === 'finished') return STEPS.length;
  return STEPS.findIndex((step) => step.phases.includes(phase ?? ''));
};

const commitModeText = (progress: IndexJobSnapshot['progress']) => {
  if (!progress) return '—';
  const { commit_mode_requested: requested, commit_mode_resolved: resolved } = progress;
  if (requested === resolved || !resolved) return requested || '—';
  return `${requested} → ${resolved}`;
};

/** Linha de tendência das taxas reais lidas a cada atualização do job. */
const Sparkline = ({ values }: { values: number[] }) => {
  if (values.length < 2) return <svg className="job__spark" viewBox="0 0 160 34" aria-hidden="true" />;
  const max = Math.max(...values) || 1;
  const points = values.map((v, i) => `${Math.round((i * 160) / (values.length - 1))},${Math.round(31 - (v / max) * 27)}`).join(' ');
  return (
    <svg className="job__spark" viewBox="0 0 160 34" preserveAspectRatio="none" aria-hidden="true">
      <polyline points={points} fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinejoin="round" strokeLinecap="round" />
    </svg>
  );
};

/** Guarda as taxas de um job enquanto ele roda (zera quando o job muda). */
const useRateHistory = (job: IndexJobSnapshot) => {
  const [history, setHistory] = useState<{ id: string; files: number[]; chunks: number[] }>({ id: job.job_id, files: [], chunks: [] });
  const last = useRef('');
  useEffect(() => {
    const stamp = `${job.job_id}:${job.progress?.processed_count ?? 0}:${job.progress?.elapsed_ms ?? 0}`;
    if (job.status !== 'running' || stamp === last.current) return;
    last.current = stamp;
    setHistory((prev) => {
      const base = prev.id === job.job_id ? prev : { id: job.job_id, files: [], chunks: [] };
      return { id: job.job_id, files: [...base.files, job.files_per_second].slice(-30), chunks: [...base.chunks, job.chunks_per_second].slice(-30) };
    });
  }, [job]);
  return history.id === job.job_id ? history : { files: [], chunks: [] };
};

interface IndexJobCardProps {
  job: IndexJobSnapshot;
  onCancel: () => void;
  onClose?: () => void;
  onAsk?: () => void;
  busy: boolean;
  onOpenSettings?: (tab?: SettingsTab) => void;
  onIgnoredChanged: () => void;
}

const IndexJobCard = ({ job, onCancel, onClose, onAsk, busy, onOpenSettings, onIgnoredChanged }: IndexJobCardProps) => {
  const progress = job.progress;
  const total = progress?.total_found ?? job.result?.total_found ?? 0;
  const processed = progress?.processed_count ?? 0;
  const percent = total > 0 ? Math.min(100, (processed / total) * 100) : 0;
  const running = job.status === 'running';
  const finished = job.status === 'success' || job.status === 'partial';
  const status = STATUS[job.status] ?? { label: job.status, tone: '' };
  const current = stepIndex(job);
  const history = useRateHistory(job);
  const started = clock(job.started_at);
  const recent = progress?.recent_files ?? [];

  const counts = [
    { key: 'indexed', label: 'indexadas', value: progress?.indexed_count ?? job.result?.indexed_count ?? 0, color: 'var(--accent-blue)' },
    { key: 'unchanged', label: 'inalteradas', value: progress?.unchanged_count ?? job.result?.unchanged_count ?? 0, color: 'color-mix(in srgb, var(--accent-blue-light) 38%, transparent)' },
    { key: 'failed', label: 'com falha', value: progress?.failed_count ?? job.result?.failed_count ?? 0, color: 'var(--err)' },
    { key: 'skipped', label: 'puladas', value: progress?.skipped_count ?? job.result?.skipped_count ?? 0, color: 'var(--text-muted)' },
    { key: 'removed', label: 'removidas', value: job.result?.removed_count ?? 0, color: 'var(--text-muted)' },
  ];

  const timing = progress
    ? [
        { label: 'warmup', ms: progress.warmup_ms, color: 'var(--text-muted)' },
        { label: 'modelo de busca semântica', ms: progress.embedding_ms, color: 'var(--accent-blue)' },
        { label: 'gravação', ms: progress.writing_ms, color: 'color-mix(in srgb, var(--accent-blue) 55%, var(--text-muted))' },
      ].filter((t) => t.ms > 0)
    : [];
  const timingTotal = timing.reduce((sum, t) => sum + t.ms, 0);

  return (
    <article className={`job job--${running ? 'running' : finished ? 'done' : 'idle'}`} aria-label="Job atual">
      <div className="job__top">
        <span key={job.status} className={`pill pop${status.tone ? ` pill--${status.tone}` : ''}`}>
          <span className={`pill__dot${running ? ' ui-pulse' : ''}`} />
          {status.label}
        </span>
        <code className="job__path">{job.source_path}</code>
        <span className="job__when">
          {started && `iniciado ${started} · `}job <span className="mono">{job.job_id}</span>
        </span>
        {running ? (
          <button type="button" className="btn btn--sm job__cancel ui-press" onClick={onCancel} disabled={busy || job.cancel_requested}>
            <Glyph name="x" size={14} />
            {job.cancel_requested ? 'Cancelando…' : 'Cancelar'}
          </button>
        ) : (
          onClose && (
            <button type="button" className="btn btn--sm job__cancel ui-press" onClick={onClose}>
              <Glyph name="x" size={14} />
              Fechar
            </button>
          )
        )}
      </div>

      <ol className="job__steps" aria-label="Etapas">
        {STEPS.map((step, i) => {
          const state = i < current ? 'done' : i === current && running ? 'active' : 'todo';
          return (
            <li
              key={step.label}
              className={`job__step job__step--${state}`}
              aria-current={state === 'active' ? 'step' : undefined}
              style={{ animationDelay: `${120 + i * 90}ms` }}
            >
              {i > 0 && <span className={`job__rail${i <= current ? ' job__rail--done' : ''}${i === current && running ? ' ui-flow' : ''}`} aria-hidden="true" />}
              <span className="job__station" aria-hidden="true">
                {state === 'active' && <span className="job__orbit ui-spin ui-spin--slow" />}
                <Glyph name={step.icon} size={19} strokeWidth={1.8} />
              </span>
              <b>{step.label}</b>
              {state === 'active' && i === 2 && progress && progress.batch_total > 0 && (
                <span className="mono">lote {progress.batch_index} de {progress.batch_total}</span>
              )}
              {state === 'done' && i === 0 && total > 0 && <span className="mono">{total} arquivos</span>}
              {state === 'todo' && running && <span className="mono">aguardando</span>}
            </li>
          );
        })}
      </ol>

      <div className="job__progress">
        <div className="job__big">
          <span key={processed} className="bump">{processed.toLocaleString('pt-BR')}</span>{' '}
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
        {total > 0 && counts.map((c) => <i key={c.key} style={{ width: `${(c.value / total) * 100}%`, background: c.color }} />)}
        {running && percent > 0 && <span className="job__bar-stripes ui-stripes" style={{ width: `${percent}%` }} aria-hidden="true" />}
      </div>
      <div className="job__legend">
        {counts.map((c) => (
          <span key={c.key}>
            <i style={{ background: c.color }} />
            {c.label} <b className="mono">{c.value.toLocaleString('pt-BR')}</b>
          </span>
        ))}
      </div>

      <div className={`ui-collapse${finished ? ' ui-collapse--open' : ''}`}>
        <div>
          {finished && (
            <div className="job__done" role="status">
              <span className="job__done-badge">
                <span className="ui-ring" />
                <span className="ui-ring ui-ring--late" />
                <Glyph name="check" size={20} strokeWidth={2.4} />
              </span>
              <div className="job__done-text">
                <strong>{job.status === 'partial' ? 'Vault pronta, com arquivos a revisar' : 'Vault pronta para perguntas'}</strong>
                <span>
                  {counts[0].value.toLocaleString('pt-BR')} indexadas, {counts[1].value.toLocaleString('pt-BR')} inalteradas, {counts[2].value} com falha
                  {progress ? ` · ${seconds(progress.elapsed_ms)}` : ''}
                </span>
              </div>
              {onAsk && (
                <button type="button" className="btn btn--primary ui-press" onClick={onAsk}>
                  <Glyph name="stars" size={15} />
                  Perguntar à vault
                </button>
              )}
            </div>
          )}
        </div>
      </div>

      {!running && (job.message || progress?.message) && <p className="job__message">{job.message ?? progress?.message}</p>}

      <div className="job__live">
        <section className="job__feed" aria-label="Arquivos processados agora">
          <header>
            <Glyph name="notes" size={15} />
            Agora
            {running && progress?.current_path && (
              <span className="job__reading mono" title={progress.current_path}>
                <span className="msg__spinner" aria-hidden="true" />
                {relative(progress.current_path, job.source_path)}
              </span>
            )}
          </header>
          {recent.length === 0 ? (
            <p className="job__feed-empty">{running ? 'Os arquivos aparecem aqui assim que o primeiro terminar.' : 'Nenhum arquivo processado neste job.'}</p>
          ) : (
            <ul>
              {recent.slice(0, 6).map((file, i) => {
                const meta = FILE_STATUS[file.status] ?? { label: file.status, tone: '' };
                return (
                  <li key={file.source_path} className="job__feed-item" style={{ opacity: 1 - i * 0.12 }}>
                    <Glyph name="notes" size={14} />
                    <span className="job__feed-name mono" title={file.source_path}>{relative(file.source_path, job.source_path)}</span>
                    <span className={`job__feed-status${meta.tone ? ` job__feed-status--${meta.tone}` : ''}`}>{meta.label}</span>
                    <span className="job__feed-chunks mono">{file.status === 'success' ? `${file.chunks} trechos` : file.status === 'unchanged' ? 'hash igual' : ''}</span>
                  </li>
                );
              })}
            </ul>
          )}
        </section>
        <dl className="job__kpis">
          <div>
            <dt><Glyph name="notes" size={14} />Arquivos por segundo</dt>
            <dd className="mono">{num(job.files_per_second)}</dd>
            <Sparkline values={history.files} />
          </div>
          <div>
            <dt><Glyph name="scissors" size={14} />Trechos por segundo</dt>
            <dd className="mono">{num(job.chunks_per_second)}</dd>
            <Sparkline values={history.chunks} />
          </div>
          <div>
            <dt><Glyph name="clock" size={14} />Tempo restante</dt>
            <dd className="mono">{running && job.eta_seconds != null ? `~${job.eta_seconds} s` : finished ? 'pronto' : '—'}</dd>
          </div>
          <div>
            <dt><Glyph name="db" size={14} />Modo de commit</dt>
            <dd className="mono job__commit">{commitModeText(progress)}</dd>
          </div>
        </dl>
      </div>

      {timingTotal > 0 && (
        <div className="job__timing">
          <div className="job__timing-label">
            <span>Tempo por etapa</span>
            <span className="mono">{seconds(progress?.elapsed_ms ?? timingTotal)}</span>
          </div>
          <div className="job__tbar" role="img" aria-label={timing.map((t) => `${t.label} ${seconds(t.ms)}`).join(', ')}>
            {timing.map((t) => <i key={t.label} style={{ width: `${(t.ms / timingTotal) * 100}%`, background: t.color }} />)}
          </div>
        </div>
      )}

      {/* Falhas agrupadas pelo motivo, com abrir, tentar de novo e ignorar; novo job, lista nova. */}
      <JobFailures key={job.job_id} errors={job.last_errors} rootPath={job.source_path} onOpenSettings={onOpenSettings} onIgnoredChanged={onIgnoredChanged} />
    </article>
  );
};

export default IndexJobCard;
