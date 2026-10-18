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

import { type ReactNode, useCallback, useEffect, useRef } from 'react';
import { useIndexJob } from '../hooks/useIndexJob';
import { useVaultContext } from '../hooks/useVaultContext';
import { QueueContext } from './QueueContextObject';

// Compara caminhos de Windows ignorando barra final, separador e caixa.
const samePath = (a: string, b: string) => {
  const norm = (p: string) => p.trim().replace(/[\\/]+$/, '').replace(/\//g, '\\').toLowerCase();
  return norm(a) !== '' && norm(a) === norm(b);
};

/** Provedor: envolve a aplicação inteira em App.tsx (dentro do VaultProvider) */
export function QueueProvider({ children }: { children: ReactNode }) {
  const queue = useIndexJob();
  const { vaultPath, adoptVault, rescanVault } = useVaultContext();
  const { job, folderPath, startJob } = queue;
  const rescannedJobId = useRef<string | null>(null);

  // Sem vault configurado, a pasta indexada vira o vault. Escolha explícita em Configurações vence.
  const startJobAndAdopt = useCallback(async () => {
    const path = folderPath.trim();
    if (!vaultPath && path) await adoptVault(path);
    await startJob();
  }, [folderPath, vaultPath, adoptVault, startJob]);

  // Ao concluir um job na pasta do vault, reescaneia para o grafo refletir arquivos novos.
  // Uma vez por job_id: um job rápido pode chegar já terminal, sem nunca ser visto como running.
  useEffect(() => {
    if (!job || job.status === 'running' || rescannedJobId.current === job.job_id) return;
    rescannedJobId.current = job.job_id;
    if (samePath(job.source_path, vaultPath)) void rescanVault();
  }, [job, vaultPath, rescanVault]);

  return (
    <QueueContext.Provider value={{ ...queue, startJob: startJobAndAdopt }}>
      {children}
    </QueueContext.Provider>
  );
}
