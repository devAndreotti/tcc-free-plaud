/**
 * VaultsContext.tsx
 * Vault ativa e lista de vaults. Trocar de vault avisa o app inteiro
 * (evento escolio:corpus-changed e `version`), para o grafo, a saúde e as telas recarregarem.
 */
import { useCallback, useEffect, useMemo, useState, type ReactNode } from 'react';
import {
  bridge,
  type VaultColor,
  type VaultIconId,
  type VaultList,
  type VaultMutationResult,
  type VaultPatch,
} from '../services/bridge';
import { VAULT_SWITCHED_EVENT, VaultsContext, type VaultsState } from './VaultsContextObject';

export const CORPUS_CHANGED_EVENT = 'escolio:corpus-changed';

const EMPTY_LIST: VaultList = { active: '', vaults: [] };

const failed = (err: unknown): VaultMutationResult => ({
  ok: false,
  message: err instanceof Error ? err.message : 'Operação indisponível.',
});

export function VaultsProvider({ children }: Readonly<{ children: ReactNode }>) {
  const [list, setList] = useState<VaultList>(EMPTY_LIST);
  const [version, setVersion] = useState(0);

  const refresh = useCallback(async () => {
    try {
      setList(await bridge.listVaults());
    } catch (err) {
      console.error('[vaults] Erro ao listar vaults:', err);
    }
  }, []);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- carga inicial da lista de vaults.
    void refresh();
  }, [refresh]);

  const announceSwitch = useCallback(() => {
    setVersion((prev) => prev + 1);
    window.dispatchEvent(new Event(CORPUS_CHANGED_EVENT));
  }, []);

  const select = useCallback(
    async (vaultId: string): Promise<VaultMutationResult> => {
      let result: VaultMutationResult;
      try {
        result = await bridge.selectVault(vaultId);
      } catch (err) {
        return failed(err);
      }
      if (result.ok) {
        window.dispatchEvent(new Event(VAULT_SWITCHED_EVENT));
        await refresh();
        announceSwitch();
      }
      return result;
    },
    [refresh, announceSwitch]
  );

  const create = useCallback(
    async (name: string, icon: VaultIconId, color: VaultColor): Promise<VaultMutationResult> => {
      let result: VaultMutationResult;
      try {
        result = await bridge.createVault(name, icon, color, []);
      } catch (err) {
        return failed(err);
      }
      if (!result.ok || !result.vault) return result;
      // A vault nova vira a ativa.
      const switched = await select(result.vault.id);
      return switched.ok ? result : switched;
    },
    [select]
  );

  const update = useCallback(
    async (vaultId: string, patch: VaultPatch): Promise<VaultMutationResult> => {
      let result: VaultMutationResult;
      try {
        result = await bridge.updateVault(vaultId, patch);
      } catch (err) {
        return failed(err);
      }
      if (result.ok) await refresh();
      return result;
    },
    [refresh]
  );

  const remove = useCallback(
    async (vaultId: string, confirm: string): Promise<VaultMutationResult> => {
      const wasActive = list.active === vaultId;
      let result: VaultMutationResult;
      try {
        result = await bridge.deleteVault(vaultId, confirm);
      } catch (err) {
        return failed(err);
      }
      if (result.ok) {
        await refresh();
        if (wasActive) announceSwitch();
      }
      return result;
    },
    [list.active, refresh, announceSwitch]
  );

  const value = useMemo<VaultsState>(
    () => ({
      vaults: list.vaults,
      active: list.vaults.find((vault) => vault.id === list.active) ?? null,
      version,
      refresh,
      select,
      create,
      update,
      remove,
    }),
    [list, version, refresh, select, create, update, remove]
  );

  return <VaultsContext.Provider value={value}>{children}</VaultsContext.Provider>;
}
