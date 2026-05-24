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

import { type ReactNode } from 'react';
import { useVault } from '../hooks/useVault';
import { VaultContext } from './VaultContextObject';

/** Provedor: envolve a aplicação inteira em App.tsx */
export function VaultProvider({ children }: { children: ReactNode }) {
  const vault = useVault();
  return (
    <VaultContext.Provider value={vault}>
      {children}
    </VaultContext.Provider>
  );
}
