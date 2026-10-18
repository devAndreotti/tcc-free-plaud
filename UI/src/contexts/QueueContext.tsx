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

import { type ReactNode, useCallback, useEffect, useMemo, useRef } from 'react';
import { type QueueState, useIndexJob } from '../hooks/useIndexJob';
import { useVaultContext } from '../hooks/useVaultContext';
import { QueueContext } from './QueueContextObject';

// Normaliza caminho de Windows: sem espaço nas pontas, barra única, caixa baixa, sem barra final.
const normPath = (p: string) => {
  let s = p.trim().replaceAll('/', '\\').toLowerCase();
  while (s.endsWith('\\')) s = s.slice(0, -1);
  return s;
};

// Compara caminhos de Windows ignorando barra final, separador e caixa.
const samePath = (a: string, b: string) => {
  const na = normPath(a);
  return na !== '' && na === normPath(b);
};

/** Provedor: envolve a aplicação inteira em App.tsx (dentro do VaultProvider) */
export function QueueProvider({ children }: Readonly<{ children: ReactNode }>) {
  const queue = useIndexJob();
  const { vaultPath, adoptVault, rescanVault } = useVaultContext();
  const { job, folderPath, setFolderPath, status, isBusy, watcherActive, chooseFolder, startJob, cancelJob, toggleWatcher } = queue;
  const rescannedJobId = useRef<string | null>(null);

  // Sem vault configurado, a pasta indexada vira o vault. Escolha explícita em Configurações vence.
  const startJobAndAdopt = useCallback(async (path?: string) => {
    const target = (typeof path === 'string' ? path : folderPath).trim();
    if (!vaultPath && target) await adoptVault(target);
    await startJob(target);
  }, [folderPath, vaultPath, adoptVault, startJob]);

  // Ao concluir um job na pasta do vault, reescaneia para o grafo refletir arquivos novos.
  // Uma vez por job_id: um job rápido pode chegar já terminal, sem nunca ser visto como running.
  useEffect(() => {
    if (!job || job.status === 'running' || rescannedJobId.current === job.job_id) return;
    rescannedJobId.current = job.job_id;
    if (samePath(job.source_path, vaultPath)) void rescanVault();
  }, [job, vaultPath, rescanVault]);

  // useIndexJob devolve um objeto novo a cada render: o value só muda quando um campo muda
  const value = useMemo<QueueState>(() => ({
    folderPath, setFolderPath, job, status, isBusy, watcherActive,
    chooseFolder, startJob: startJobAndAdopt, cancelJob, toggleWatcher,
  }), [folderPath, setFolderPath, job, status, isBusy, watcherActive, chooseFolder, startJobAndAdopt, cancelJob, toggleWatcher]);

  return (
    <QueueContext.Provider value={value}>
      {children}
    </QueueContext.Provider>
  );
}
