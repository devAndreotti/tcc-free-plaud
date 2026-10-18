/**
 * QueueContext.tsx
 * ──────────────────────────────────────────────────────────────
 * Provedor de contexto global para o estado do job de indexação.
 *
 * Envolve o App inteiro para que o job (e seu polling) sobrevivam
 * à desmontagem de QueuePanel quando o usuário troca de aba.
 *
 * Uso:
 *   const { job, startJob, cancelJob } = useQueueContext();
 * ──────────────────────────────────────────────────────────────
 */

import { type ReactNode, useMemo } from 'react';
import { type QueueState, useIndexJob } from '../hooks/useIndexJob';
import { QueueContext } from './QueueContextObject';

/** Provedor: envolve a aplicação inteira em App.tsx. A fila indexa na vault ativa (o backend decide). */
export function QueueProvider({ children }: Readonly<{ children: ReactNode }>) {
  const queue = useIndexJob();
  const { job, folderPath, setFolderPath, status, isBusy, watcherActive, chooseFolder, startJob, cancelJob, toggleWatcher } = queue;

  // useIndexJob devolve um objeto novo a cada render: o value só muda quando um campo muda
  const value = useMemo<QueueState>(() => ({
    folderPath, setFolderPath, job, status, isBusy, watcherActive,
    chooseFolder, startJob, cancelJob, toggleWatcher,
  }), [folderPath, setFolderPath, job, status, isBusy, watcherActive, chooseFolder, startJob, cancelJob, toggleWatcher]);

  return (
    <QueueContext.Provider value={value}>
      {children}
    </QueueContext.Provider>
  );
}
