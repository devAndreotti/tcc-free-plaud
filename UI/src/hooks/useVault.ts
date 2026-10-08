/**
 * useVault.ts
 * ──────────────────────────────────────────────────────────────
 * Hook que centraliza toda a lógica de estado do Vault:
 *   - Selecionar a pasta via diálogo nativo
 *   - Escanear arquivos .md recursivamente
 *   - Persistir o caminho entre sessões
 * ──────────────────────────────────────────────────────────────
 */

import { useState, useCallback, useEffect } from 'react';
import { bridge } from '../services/bridge';

/** Metadados de um arquivo Markdown encontrado no Vault */
export interface MarkdownNode {
  id: string;
  name: string;         // nome sem extensão .md
  path: string;         // caminho relativo à raiz do vault
  size: number;         // tamanho em bytes
  modified: string;     // data de modificação em formato ISO 8601
}

export interface VaultState {
  vaultPath: string;
  nodes: MarkdownNode[];
  isScanning: boolean;
  lastScanAt: Date | null;
  /** Abre o diálogo de seleção, salva o path e escaneia automaticamente */
  selectVault: () => Promise<void>;
  /** Escaneia novamente sem alterar o path atual */
  rescanVault: () => Promise<void>;
  /** Limpa o vault e os nós */
  clearVault: () => void;
}

export function useVault(): VaultState {
  const [vaultPath, setVaultPath] = useState<string>('');
  const [nodes, setNodes] = useState<MarkdownNode[]>([]);
  const [isScanning, setIsScanning] = useState(false);
  const [lastScanAt, setLastScanAt] = useState<Date | null>(null);

  /** Executa a varredura de arquivos .md em um caminho específico */
  const runScan = useCallback(async (path: string) => {
    if (!path) return;
    setIsScanning(true);
    try {
      const result = await bridge.scanVault(path);
      setNodes(result);
      setLastScanAt(new Date());
    } catch (err) {
      console.error('[useVault] Erro ao escanear vault:', err);
      setNodes([]);
    } finally {
      setIsScanning(false);
    }
  }, []);

  // Restaura o caminho salvo ao iniciar o app
  useEffect(() => {
    bridge.loadVaultPath().then((savedPath) => {
      if (savedPath) {
        setVaultPath(savedPath);
        // Escaneia automaticamente ao restaurar o vault salvo
        runScan(savedPath);
      }
    });
  }, [runScan]);

  /** Abre o diálogo nativo, salva o path e dispara a varredura */
  const selectVault = useCallback(async () => {
    const selected = await bridge.selectFolder();
    if (!selected) return;

    setVaultPath(selected);
    await bridge.saveVaultPath(selected);
    await runScan(selected);
  }, [runScan]);

  /** Reescaneia sem mudar o path */
  const rescanVault = useCallback(async () => {
    await runScan(vaultPath);
  }, [vaultPath, runScan]);

  /** Remove vault e nós do estado */
  const clearVault = useCallback(() => {
    setVaultPath('');
    setNodes([]);
    setLastScanAt(null);
    bridge.saveVaultPath('');
  }, []);

  return {
    vaultPath,
    nodes,
    isScanning,
    lastScanAt,
    selectVault,
    rescanVault,
    clearVault,
  };
}
