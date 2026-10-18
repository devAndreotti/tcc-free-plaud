import { createContext } from 'react';
import type { Vault, VaultColor, VaultIconId, VaultMutationResult, VaultPatch } from '../services/bridge';

export interface VaultsState {
  vaults: Vault[];
  active: Vault | null;
  /** Sobe a cada troca de vault: telas com estado próprio remontam por ele. */
  version: number;
  refresh: () => Promise<void>;
  select: (vaultId: string) => Promise<VaultMutationResult>;
  create: (name: string, icon: VaultIconId, color: VaultColor) => Promise<VaultMutationResult>;
  update: (vaultId: string, patch: VaultPatch) => Promise<VaultMutationResult>;
  remove: (vaultId: string, confirm: string) => Promise<VaultMutationResult>;
}

export const VaultsContext = createContext<VaultsState | null>(null);
