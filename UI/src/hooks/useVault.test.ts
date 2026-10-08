import { act, renderHook, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { useVault } from './useVault';

const bridgeMock = vi.hoisted(() => ({
  loadVaultPath: vi.fn(),
  saveVaultPath: vi.fn(),
  scanVault: vi.fn(),
  selectFolder: vi.fn(),
}));

vi.mock('../services/bridge', () => ({
  bridge: bridgeMock,
}));

const node = { id: 'n1', name: 'nota', path: 'nota.md', size: 10, modified: '2026-01-01T00:00:00Z' };

describe('useVault', () => {
  beforeEach(() => {
    bridgeMock.loadVaultPath.mockResolvedValue('');
    bridgeMock.saveVaultPath.mockResolvedValue(true);
    bridgeMock.scanVault.mockResolvedValue([node]);
    vi.spyOn(console, 'error').mockImplementation(() => {});
  });

  afterEach(() => {
    vi.clearAllMocks();
    vi.restoreAllMocks();
  });

  it('restaura o caminho salvo e escaneia ao montar', async () => {
    bridgeMock.loadVaultPath.mockResolvedValue('C:/vault');

    const { result } = renderHook(() => useVault());

    await waitFor(() => expect(result.current.nodes).toEqual([node]));
    expect(result.current.vaultPath).toBe('C:/vault');
    expect(bridgeMock.scanVault).toHaveBeenCalledWith('C:/vault');
  });

  it('registra o erro quando não consegue ler o caminho salvo', async () => {
    bridgeMock.loadVaultPath.mockRejectedValue(new Error('sem bridge'));

    renderHook(() => useVault());

    await waitFor(() =>
      expect(console.error).toHaveBeenCalledWith('[useVault] Erro ao restaurar vault:', expect.any(Error))
    );
    expect(bridgeMock.scanVault).not.toHaveBeenCalled();
  });

  it('limpa o estado e registra o erro se não conseguir salvar o caminho vazio', async () => {
    bridgeMock.loadVaultPath.mockResolvedValue('C:/vault');
    bridgeMock.saveVaultPath.mockRejectedValue(new Error('disco cheio'));
    const { result } = renderHook(() => useVault());
    await waitFor(() => expect(result.current.nodes).toEqual([node]));

    act(() => result.current.clearVault());

    expect(result.current.vaultPath).toBe('');
    expect(result.current.nodes).toEqual([]);
    expect(bridgeMock.saveVaultPath).toHaveBeenCalledWith('');
    await waitFor(() =>
      expect(console.error).toHaveBeenCalledWith('[useVault] Erro ao limpar vault:', expect.any(Error))
    );
  });
});
