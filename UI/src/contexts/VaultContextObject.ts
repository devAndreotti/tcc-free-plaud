import { createContext } from 'react';
import type { VaultState } from '../hooks/useVault';

export const VaultContext = createContext<VaultState | null>(null);
