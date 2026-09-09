/**
 * useIndexJob.ts
 * ──────────────────────────────────────────────────────────────
 * Hook que centraliza todo o estado do job de indexação da Fila:
 *   - Escolher pasta, iniciar/cancelar job, monitorar pasta
 *   - Fazer polling do job ativo até ele terminar
 *
 * Extraído de QueuePanel.tsx para viver num Context acima do
 * componente — assim o job (e o polling) sobrevive à troca de aba,
 * já que QueuePanel é desmontado quando o usuário navega para outra
 * view (ver App.tsx). O job real já roda desacoplado no backend
 * (thread daemon); este hook só garante que a UI não perca a
 * referência a ele.
 * ──────────────────────────────────────────────────────────────
 */

import { useCallback, useEffect, useState } from 'react';
import { bridge, type IndexJobSnapshot } from '../services/bridge';

export interface QueueState {
  folderPath: string;
  setFolderPath: (path: string) => void;
  job: IndexJobSnapshot | null;
  status: string;
  isBusy: boolean;
  watcherActive: boolean;
  chooseFolder: () => Promise<void>;
  startJob: () => Promise<void>;
  cancelJob: () => Promise<void>;
  toggleWatcher: () => Promise<void>;
}

export function useIndexJob(): QueueState {
  const [folderPath, setFolderPath] = useState('');
  const [job, setJob] = useState<IndexJobSnapshot | null>(null);
  const [status, setStatus] = useState('Pronto.');
  const [isBusy, setIsBusy] = useState(false);
  const [watcherActive, setWatcherActive] = useState(false);

  const refreshJob = useCallback(async (jobId: string) => {
    const latest = await bridge.getIndexJob(jobId);
    setJob(latest);
    setStatus(latest.message ?? `Job ${latest.status}.`);
  }, []);

  // Polling do job ativo — sobrevive à desmontagem de QueuePanel porque
  // este hook vive no QueueProvider, acima do ponto onde a view é trocada.
  useEffect(() => {
    const jobId = job?.job_id;
    if (!jobId || job.status !== 'running') return undefined;
    const interval = window.setInterval(() => {
      void refreshJob(jobId);
    }, 1000);
    return () => window.clearInterval(interval);
  }, [job, refreshJob]);

  const toggleWatcher = useCallback(async () => {
    if (watcherActive) {
      await bridge.stopWatcher();
      setWatcherActive(false);
      return;
    }
    if (!folderPath) return;
    const result = await bridge.startWatcher(folderPath);
    setWatcherActive(result.active);
  }, [watcherActive, folderPath]);

  const chooseFolder = useCallback(async () => {
    setIsBusy(true);
    try {
      const selected = await bridge.selectFolder();
      if (selected) setFolderPath(selected);
    } catch (error) {
      setStatus(error instanceof Error ? error.message : 'Falha ao escolher pasta.');
    } finally {
      setIsBusy(false);
    }
  }, []);

  const startJob = useCallback(async () => {
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
  }, [folderPath, refreshJob]);

  const cancelJob = useCallback(async () => {
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
  }, [job]);

  return {
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
  };
}
