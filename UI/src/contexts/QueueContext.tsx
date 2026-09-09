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

import { type ReactNode } from 'react';
import { useIndexJob } from '../hooks/useIndexJob';
import { QueueContext } from './QueueContextObject';

/** Provedor: envolve a aplicação inteira em App.tsx */
export function QueueProvider({ children }: { children: ReactNode }) {
  const queue = useIndexJob();
  return (
    <QueueContext.Provider value={queue}>
      {children}
    </QueueContext.Provider>
  );
}
