import { useContext } from 'react';
import { VaultsContext, type VaultsState } from '../contexts/VaultsContextObject';

export function useVaults(): VaultsState {
  const ctx = useContext(VaultsContext);
  if (!ctx) {
    throw new Error('useVaults deve ser usado dentro de <VaultsProvider>');
  }
  return ctx;
}
