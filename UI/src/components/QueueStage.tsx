import { useState } from 'react';
import type { IndexJobSnapshot } from '../services/bridge';
import type { SettingsTab } from './SettingsModal';
import IndexJobCard from './IndexJobCard';
import { Glyph } from './ui/Glyph';
import './QueueStage.css';

/** Folhas saem da pasta e voam pela trilha até a pilha do índice; com launch, voam rápido (job começando). */
const QueueArt = ({ launch }: { launch: boolean }) => (
  <svg className={`queue-art${launch ? ' queue-art--launch' : ''}`} viewBox="0 0 380 190" fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" focusable="false">
    <path className="queue-art__trail" d="M110 120C160 40 230 40 280 104" strokeOpacity=".45" strokeWidth="1.6" />
    {[[40, 22, 0], [196, 16, 0.8], [356, 40, 1.6], [226, 176, 2.2], [14, 160, 1.2]].map(([x, y, d]) => (
      <circle key={`${x}-${y}`} className="queue-art__star" style={{ animationDelay: `${d}s` }} cx={x} cy={y} r="1.6" fill="currentColor" stroke="none" />
    ))}
    <g className="queue-art__folder">
      <path d="M24 92h30l8 9h52a6 6 0 0 1 6 6v58a6 6 0 0 1-6 6H24a6 6 0 0 1-6-6V98a6 6 0 0 1 6-6Z" fill="currentColor" fillOpacity=".08" strokeWidth="1.8" />
      <rect x="36" y="80" width="40" height="50" rx="4" fill="var(--bg-panel)" strokeOpacity=".5" strokeWidth="1.4" />
      <path d="M44 92h20M44 100h24M44 108h16" strokeOpacity=".4" strokeWidth="1.6" />
      <rect x="62" y="74" width="40" height="50" rx="4" fill="var(--bg-panel)" strokeOpacity=".7" strokeWidth="1.4" />
      <path d="M70 86h20M70 94h24M70 102h14" strokeOpacity=".55" strokeWidth="1.6" />
      <path d="M18 118h102v47a6 6 0 0 1-6 6H24a6 6 0 0 1-6-6Z" fill="var(--bg-panel)" strokeWidth="1.8" />
    </g>
    {[1, 2, 3].map((n) => (
      <g key={n} className={`queue-art__doc queue-art__doc--${n}`}>
        <rect x="96" y="104" width="26" height="32" rx="3" fill="var(--bg-panel)" strokeWidth="1.4" />
        <path d="M101 113h14M101 119h16M101 125h10" strokeOpacity=".6" strokeWidth="1.4" />
      </g>
    ))}
    <path d="M318 150l-46-20 46-20 46 20Z" fill="currentColor" fillOpacity=".1" strokeOpacity=".5" strokeWidth="1.6" />
    <path d="M318 136l-46-20 46-20 46 20Z" fill="currentColor" fillOpacity=".14" strokeOpacity=".7" strokeWidth="1.6" />
    <path className="queue-art__top" d="M318 122l-46-20 46-20 46 20Z" fill="currentColor" fillOpacity=".2" strokeWidth="1.8" />
    <circle className="queue-art__glow" cx="318" cy="102" r="30" strokeOpacity=".3" strokeWidth="1.2" />
  </svg>
);

interface QueueStageProps {
  job: IndexJobSnapshot | null;
  busy: boolean;
  canReindex: boolean;
  reindexLabel: string;
  onReindex: () => void;
  onChooseFolder: () => void;
  onCancel: () => void;
  onAsk?: () => void;
  onOpenSettings?: (tab?: SettingsTab) => void;
  onIgnoredChanged: () => void;
}

/**
 * Cartão da Fila que se transforma: sem job mostra a arte; quando um job começa, a parte vazia
 * recolhe enquanto a do job abre. "Fechar" num job terminado volta para a arte.
 */
const QueueStage = ({ job, busy, canReindex, reindexLabel, onReindex, onChooseFolder, onCancel, onAsk, onOpenSettings, onIgnoredChanged }: QueueStageProps) => {
  const [closedJob, setClosedJob] = useState<string | null>(null);
  const running = job?.status === 'running';
  const showJob = Boolean(job) && (running || job?.job_id !== closedJob);
  const starting = busy && !running;

  return (
    <section className={`card queue-stage${running ? ' queue-stage--running' : ''}${showJob && !running ? ' queue-stage--done' : ''}`} aria-label="Indexação">
      <div className={`ui-collapse${showJob ? '' : ' ui-collapse--open'}`}>
        <div>
          <div className="queue-empty">
            <div className="queue-empty__art">
              <QueueArt launch={starting} />
            </div>
            <div className="queue-empty__text">
              <h2>{starting ? 'Preparando o job de indexação…' : 'Nada indexando agora'}</h2>
              <p>
                <b>Nenhum job nesta sessão.</b> Escolha a pasta do vault e clique em Indexar. Notas que não mudaram desde a
                última vez são puladas pelo hash, então reindexar a vault inteira costuma ser rápido.
              </p>
              <div className="queue-empty__actions">
                {canReindex && (
                  <button type="button" className="btn btn--primary ui-press" onClick={onReindex} disabled={busy}>
                    <Glyph name="refresh" size={15} />
                    {reindexLabel}
                  </button>
                )}
                <button type="button" className="btn ui-press" onClick={onChooseFolder} disabled={busy} aria-label="Escolher outra pasta">
                  <Glyph name="folder" size={15} />
                  Escolher pasta
                </button>
              </div>
              <ul className="queue-empty__tips" aria-label="Dicas">
                <li><Glyph name="refresh" size={15} />Monitorar pasta reindexa sozinho ao salvar</li>
                <li><Glyph name="layers" size={15} />Um job por vez; os outros esperam</li>
                <li><Glyph name="notes" size={15} />Arraste PDFs e áudios aqui embaixo</li>
              </ul>
            </div>
          </div>
        </div>
      </div>
      <div className={`ui-collapse${showJob ? ' ui-collapse--open' : ''}`}>
        <div>
          {job && showJob && (
            <IndexJobCard
              job={job}
              busy={busy}
              onCancel={onCancel}
              onClose={() => setClosedJob(job.job_id)}
              onAsk={onAsk}
              onOpenSettings={onOpenSettings}
              onIgnoredChanged={onIgnoredChanged}
            />
          )}
        </div>
      </div>
    </section>
  );
};

export default QueueStage;
