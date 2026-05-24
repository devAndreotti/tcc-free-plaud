/**
 * VaultContext.tsx
 * ──────────────────────────────────────────────────────────────
 * Provedor de contexto global para o estado do Vault.
 *
 * Envolve o App inteiro para que SettingsModal e GraphView
 * compartilhem o mesmo estado sem prop-drilling.
 *
 * Uso:
 *   // Qualquer componente filho pode consumir:
 *   const { vaultPath, nodes, selectVault } = useVaultContext();
 * ──────────────────────────────────────────────────────────────
 */

import { createContext, useContext, type ReactNode } from 'react';
import { useVault, type VaultState } from '../hooks/useVault';

const VaultContext = createContext<VaultState | null>(null);

/** Provedor: envolve a aplicação inteira em App.tsx */
export function VaultProvider({ children }: { children: ReactNode }) {
  const vault = useVault();
  return (
    <VaultContext.Provider value={vault}>
      {children}
    </VaultContext.Provider>
  );
}

/** Hook consumidor: lança erro se usado fora do VaultProvider */
export function useVaultContext(): VaultState {
  const ctx = useContext(VaultContext);
  if (!ctx) {
    throw new Error('useVaultContext deve ser usado dentro de <VaultProvider>');
  }
  return ctx;
}
