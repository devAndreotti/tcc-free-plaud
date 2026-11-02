import { useCallback, useContext, useEffect, useState } from 'react';
import { Sk, SkLines } from './ui/Loading';
import { VaultsContext } from '../contexts/VaultsContextObject';
import { VaultGlyph } from './VaultGlyph';
import { bridge, type CorpusRoot, type IndexJobSnapshot } from '../services/bridge';
import type { SettingsTab } from './SettingsModal';
import { useQueueContext } from '../hooks/useQueueContext';
import Dropzone, { type DropzoneToast } from './Dropzone';
import ToastStack from './ToastStack';
import IgnoredFiles from './IgnoredFiles';
import QueueStage from './QueueStage';
import { FolderIcon, LoaderIcon, PlayIcon } from './Icons';
import { notifyCorpusChanged } from '../hooks/useCorpusHealth';
import { CORPUS_PROGRESS_EVENT } from '../lib/corpusEvents';

interface QueuePanelProps {
  onOpenSettings?: (tab?: SettingsTab) => void;
  /** Leva ao chat depois de indexar ("Perguntar à vault"). */
  onAsk?: () => void;
}

const isActiveJob = (snapshot: IndexJobSnapshot | null) => snapshot?.status === 'running';

const basename = (path: string) => path.split(/[\\/]/).findLast(Boolean) ?? path;

const notesLabel = (count: number) => `${count} ${count === 1 ? 'nota' : 'notas'}`;

interface CorpusRootsPanelProps {
  roots: CorpusRoot[];
  loading?: boolean;
  disabled: boolean;
  onReindex: (root: string) => void;
  onRemoved: () => void;
}

// Pastas indexadas no corpus único. Remover tira as notas do SQLite e do Chroma; não apaga arquivos do disco.
const CorpusRootsPanel = ({ roots, loading = false, disabled, onReindex, onRemoved }: CorpusRootsPanelProps) => {
  const [removing, setRemoving] = useState<string | null>(null);
  const [typed, setTyped] = useState('');
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState('');

  const cancelRemove = () => {
    setRemoving(null);
    setTyped('');
  };

  const confirmRemove = async (root: CorpusRoot) => {
    setBusy(true);
    setMessage('');
    try {
      const result = await bridge.removeCorpusRoot(root.root, typed);
      if (!result.ok) {
        setMessage(result.message ?? 'Não foi possível tirar a pasta do corpus.');
        return;
      }
      setMessage(`${basename(root.root)} saiu do corpus: ${notesLabel(result.removed_notes ?? 0)} removidas.`);
      cancelRemove();
      notifyCorpusChanged();
      onRemoved();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'Falha ao tirar a pasta do corpus.');
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="card queue__roots" aria-label="Pastas no corpus">
      <div className="card__head">
        <h2>
          Pastas no corpus {!loading && <span className="card__count">{roots.length}</span>}
        </h2>
      </div>
      {loading ? (
        <div className="load-wait load-row" aria-label="Carregando pastas" role="status"><Sk w={16} h={16} r={4} /><SkLines widths={['72%', '34%']} gap={6} /></div>
      ) : roots.length === 0 ? (
        <p className="queue__roots-empty">Nenhuma pasta indexada ainda.</p>
      ) : (
        <ul className="queue__root-list">
          {roots.map((root) => (
            <li key={root.root} className="queue__root">
              <div className="queue__root-info">
                <span className="queue__root-name">{basename(root.root)}</span>
                <code className="queue__root-path mono" title={root.root}>{root.root}</code>
              </div>
              <span className="queue__root-count mono">{notesLabel(root.notes_count)}</span>
              <div className="queue__root-actions">
                <button type="button" className="btn btn--sm" onClick={() => onReindex(root.root)} disabled={disabled || busy}>
                  Reindexar
                </button>
                <button
                  type="button"
                  className="btn btn--sm btn--ghost"
                  onClick={() => {
                    setRemoving(root.root);
                    setTyped('');
                  }}
                  disabled={disabled || busy}
                >
                  Remover
                </button>
              </div>
              {removing === root.root && (
                <div
                  className="queue__root-confirm"
                  role="alertdialog"
                  aria-label={`Remover ${basename(root.root)} do corpus`}
                  onKeyDown={(event) => {
                    if (event.key === 'Escape' && !busy) cancelRemove();
                  }}
                >
                  <p>
                    Remove as {notesLabel(root.notes_count)} desta pasta do SQLite e do Chroma. Os arquivos no disco não são apagados.
                  </p>
                  <label>
                    <span>Digite REMOVER para confirmar</span>
                    <input value={typed} onChange={(event) => setTyped(event.target.value)} className="mono" autoComplete="off" disabled={busy} autoFocus />
                  </label>
                  <div className="nd__confirm-actions">
                    <button type="button" className="btn btn--sm btn--ghost" onClick={cancelRemove} disabled={busy}>
                      Cancelar
                    </button>
                    <button
                      type="button"
                      className="btn btn--sm btn--danger"
                      onClick={() => void confirmRemove(root)}
                      disabled={typed !== 'REMOVER' || busy}
                    >
                      {busy && <LoaderIcon size={14} className="spin" />}
                      {busy ? 'Removendo…' : 'Remover do corpus'}
                    </button>
                  </div>
                </div>
              )}
            </li>
          ))}
        </ul>
      )}
      {message && <p className="queue__status" role="status">{message}</p>}
    </section>
  );
};

const QueuePanel = ({ onOpenSettings, onAsk }: QueuePanelProps) => {
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

  const [roots, setRoots] = useState<CorpusRoot[]>([]);
  const [rootsVersion, setRootsVersion] = useState(0);
  const [rootsLoaded, setRootsLoaded] = useState(false);
  const [ignoredVersion, setIgnoredVersion] = useState(0);
  // Chave do job que acabou: muda quando um job termina e então recarrega as pastas.
  const finishedJob = job && job.status !== 'running' ? `${job.job_id}:${job.status}` : '';
  // Carrega ao montar, quando um job termina (pode ter criado ou trocado uma pasta) e após remover uma pasta.
  useEffect(() => {
    let active = true;
    bridge.listCorpusRoots().then(
      (list) => {
        if (active) { setRoots(list); setRootsLoaded(true); }
      },
      () => {
        if (active) { setRoots([]); setRootsLoaded(true); }
      },
    );
    return () => {
      active = false;
    };
  }, [rootsVersion, finishedJob]);

  // Cada lote gravado muda a contagem de notas das pastas; a lista acompanha sem esperar o fim do job.
  useEffect(() => {
    const onProgress = () => setRootsVersion((version) => version + 1);
    window.addEventListener(CORPUS_PROGRESS_EVENT, onProgress);
    return () => window.removeEventListener(CORPUS_PROGRESS_EVENT, onProgress);
  }, []);

  const reindexRoot = useCallback(
    (root: string) => {
      setFolderPath(root);
      void startJob(root);
    },
    [setFolderPath, startJob],
  );

  // Fila da vault ativa: o título mostra o ícone e o nome dela.
  const active = useContext(VaultsContext)?.active ?? null;
  // "Reindexar" do estado vazio: a pasta digitada ou a primeira do corpus.
  const reindexTarget = folderPath || roots[0]?.root || '';

  return (
    <main className="main queue" id="queue-panel">
      <header className="page-head">
        <div>
          <h1>
            {active ? (
              <>
                Fila · <VaultGlyph icon={active.icon} color={active.color} size={14} /> {active.name}
              </>
            ) : (
              'Fila de indexação'
            )}
          </h1>
          <p>Indexe quantas pastas quiser; elas ficam no mesmo corpus e o chat pode perguntar a uma só. Um job por vez.</p>
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
            <span>Monitorar pasta</span>
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
          <button type="button" className="btn btn--primary" onClick={() => startJob()} disabled={isBusy || running || !folderPath}>
            <PlayIcon size={14} />
            Indexar
          </button>
        </section>

        {status && <p className="queue__status" role="status">{status}</p>}

        <CorpusRootsPanel
          roots={roots}
          loading={!rootsLoaded}
          disabled={isBusy || running}
          onReindex={reindexRoot}
          onRemoved={() => setRootsVersion((version) => version + 1)}
        />

        <QueueStage
          job={job}
          busy={isBusy}
          canReindex={Boolean(reindexTarget)}
          reindexLabel={reindexTarget ? `Reindexar ${basename(reindexTarget)}` : 'Reindexar'}
          onReindex={() => reindexTarget && reindexRoot(reindexTarget)}
          onChooseFolder={chooseFolder}
          onCancel={cancelJob}
          onAsk={onAsk}
          onOpenSettings={onOpenSettings}
          onIgnoredChanged={() => setIgnoredVersion((version) => version + 1)}
        />

        <IgnoredFiles version={ignoredVersion} />

        <Dropzone watchDirectory={watcherActive ? folderPath : null} onToast={addToast} />
      </div>
      <ToastStack toasts={toasts} onDismiss={dismissToast} />
    </main>
  );
};

export default QueuePanel;
