import { useContext } from 'react';
import { VaultContext } from '../contexts/VaultContextObject';
import type { VaultState } from './useVault';

export function useVaultContext(): VaultState {
  const ctx = useContext(VaultContext);
  if (!ctx) {
    throw new Error('useVaultContext deve ser usado dentro de <VaultProvider>');
  }
  return ctx;
}
