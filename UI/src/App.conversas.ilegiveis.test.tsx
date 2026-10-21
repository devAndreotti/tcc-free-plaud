import { act, cleanup, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeAll, describe, expect, it, vi } from 'vitest';
import App from './App';
import { bridge, type SavedConversations } from './services/bridge';

// Conversa salva de uma aba, no formato que conversations.json guarda (igual ao App.conversas.test.tsx).
const SAVED: SavedConversations = {
  tabs: [{ id: 'aba-redes', label: 'Estudos de redes', type: 'chat', vaultId: 'obsidian' }],
  activeTabId: 'aba-redes',
  tabMessages: {
    'aba-redes': [{ id: 'm1', role: 'user', content: 'Qual broker foi adotado?', timestamp: '2026-10-19T10:00:00.000Z' }],
  },
};

// Carga que só falha quando o teste manda: simula o arquivo de conversas que não pode ser lido.
const pendingLoadFailure = () => {
  let fail: (error: Error) => void = () => {};
  vi.spyOn(bridge, 'loadConversations').mockReturnValue(
    new Promise<SavedConversations | null>((_resolve, reject) => {
      fail = reject;
    })
  );
  return (error: Error) => act(async () => fail(error));
};

describe('App: conversas salvas ilegíveis', () => {
  beforeAll(() => {
    // jsdom não tem ResizeObserver nem canvas (mesmo ajuste de App.conversas.test.tsx).
    vi.stubGlobal('ResizeObserver', class { observe() {} unobserve() {} disconnect() {} });
    vi.spyOn(HTMLCanvasElement.prototype, 'getContext').mockReturnValue(null);
    Element.prototype.scrollIntoView = vi.fn();
  });

  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
    void bridge.selectVault('obsidian');
  });

  it('carga das conversas que falha com a tela aberta mostra o aviso de conversas ilegíveis', async () => {
    const falharCarga = pendingLoadFailure();
    const erro = vi.spyOn(console, 'error').mockImplementation(() => {});
    render(<App />);

    const falha = new Error('conversations.json corrompido');
    await falharCarga(falha);

    const aviso = await screen.findByRole('status');
    expect(aviso.textContent).toContain('Não foi possível ler as conversas salvas');
    expect(erro).toHaveBeenCalledWith(expect.stringContaining('Não foi possível carregar as conversas salvas'), falha);
  });

  it('carga que falha depois de a tela fechar só registra o erro no console', async () => {
    const falharCarga = pendingLoadFailure();
    const erro = vi.spyOn(console, 'error').mockImplementation(() => {});
    const { unmount } = render(<App />);
    unmount();

    const falha = new Error('conversations.json corrompido');
    await falharCarga(falha);

    await waitFor(() =>
      expect(erro).toHaveBeenCalledWith(expect.stringContaining('Não foi possível carregar as conversas salvas'), falha)
    );
  });

  it('carga que termina bem não mostra o aviso de conversas ilegíveis', async () => {
    vi.spyOn(bridge, 'loadConversations').mockResolvedValue(SAVED);
    render(<App />);

    expect(await screen.findByText('Estudos de redes')).toBeTruthy();
    expect(screen.queryByText(/Não foi possível ler as conversas salvas/)).toBeNull();
  });
});
