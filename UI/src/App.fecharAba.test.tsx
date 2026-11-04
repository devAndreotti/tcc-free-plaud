import { act, cleanup, render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeAll, describe, expect, it, vi } from 'vitest';
import App from './App';
import { bridge, type SavedConversations } from './services/bridge';

// Conversa salva de uma aba (uma pergunta e uma resposta), como conversations.json a guarda.
const SAVED: SavedConversations = {
  tabs: [{ id: 'aba-redes', label: 'Estudos de redes', type: 'chat', vaultId: 'obsidian' }],
  activeTabId: 'aba-redes',
  tabMessages: {
    'aba-redes': [
      { id: 'm1', role: 'user', content: 'Qual broker foi adotado?', timestamp: '2026-10-19T10:00:00.000Z' },
      { id: 'm2', role: 'assistant', content: 'O Mosquitto.', timestamp: '2026-10-19T10:00:02.000Z' },
    ],
  },
};

const waitForVault = () => screen.findByRole('button', { name: /Vault ativa: Obsidian/ });

describe('App: fechar com desfazer, exportar e buscar', () => {
  beforeAll(() => {
    vi.stubGlobal('ResizeObserver', class { observe() {} unobserve() {} disconnect() {} });
    vi.spyOn(HTMLCanvasElement.prototype, 'getContext').mockReturnValue(null);
    Element.prototype.scrollIntoView = vi.fn();
  });

  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
    vi.useRealTimers();
    void bridge.selectVault('obsidian');
  });

  it('fechar aba com mensagens e desfazer devolve as mensagens', async () => {
    const user = userEvent.setup();
    vi.spyOn(bridge, 'loadConversations').mockResolvedValue(SAVED);
    render(<App />);
    await waitForVault();
    expect(await screen.findByText('O Mosquitto.')).toBeTruthy();

    await user.click(screen.getByRole('button', { name: 'Fechar aba Estudos de redes' }));
    expect(screen.queryByText('O Mosquitto.')).toBeNull();
    expect(screen.getByText('Conversa fechada')).toBeTruthy();

    await user.click(screen.getByRole('button', { name: 'Desfazer' }));
    expect(await screen.findByText('O Mosquitto.')).toBeTruthy();
    const tabs = within(screen.getByRole('tablist', { name: 'Abas abertas' }));
    expect(tabs.getByText('Estudos de redes')).toBeTruthy();
    expect(screen.queryByText('Conversa fechada')).toBeNull();
  });

  it('aba sem mensagens fecha sem aviso', async () => {
    const user = userEvent.setup();
    vi.spyOn(bridge, 'loadConversations').mockResolvedValue(null);
    render(<App />);
    await waitForVault();

    await user.click(screen.getByRole('button', { name: 'Fechar aba Nova Conversa' }));
    expect(screen.queryByText('Conversa fechada')).toBeNull();
  });

  it('exporta a conversa ativa e mostra o aviso de sucesso', async () => {
    const user = userEvent.setup();
    vi.spyOn(bridge, 'loadConversations').mockResolvedValue(SAVED);
    const save = vi.spyOn(bridge, 'saveTextFile').mockResolvedValue('C:/tmp/Estudos de redes.md');
    render(<App />);
    await waitForVault();
    await screen.findByText('O Mosquitto.');

    await user.click(screen.getByRole('button', { name: 'Exportar conversa' }));
    await user.click(screen.getByRole('button', { name: /Markdown/ }));
    await waitFor(() => expect(save).toHaveBeenCalledTimes(1));
    expect(save.mock.calls[0][0]).toBe('Estudos de redes.md');
    expect(save.mock.calls[0][1]).toContain('## Pergunta\n\nQual broker foi adotado?');
    expect(await screen.findByText('Conversa exportada')).toBeTruthy();
  });

  it('busca no texto de todas as abas e leva à aba', async () => {
    const user = userEvent.setup();
    vi.spyOn(bridge, 'loadConversations').mockResolvedValue(SAVED);
    render(<App />);
    await waitForVault();
    await screen.findByText('O Mosquitto.');

    await user.click(screen.getByRole('button', { name: 'Buscar nas conversas' }));
    await user.type(screen.getByRole('searchbox', { name: 'Termo da busca' }), 'mosquitto');
    const popover = screen.getByRole('dialog', { name: 'Buscar nas conversas' });
    const hit = await within(popover).findByRole('button', { name: /Estudos de redes/ });
    await user.click(hit);
    expect(screen.queryByRole('dialog', { name: 'Buscar nas conversas' })).toBeNull();
  });

  it('mostra a mensagem quando nada é encontrado', async () => {
    const user = userEvent.setup();
    vi.spyOn(bridge, 'loadConversations').mockResolvedValue(SAVED);
    render(<App />);
    await waitForVault();
    await screen.findByText('O Mosquitto.');

    await user.click(screen.getByRole('button', { name: 'Buscar nas conversas' }));
    await user.type(screen.getByRole('searchbox', { name: 'Termo da busca' }), 'zzzz');
    expect(screen.getByText('Nada encontrado nas conversas abertas.')).toBeTruthy();
    await act(async () => {});
    await user.keyboard('{Escape}');
    expect(screen.queryByRole('dialog', { name: 'Buscar nas conversas' })).toBeNull();
  });
});
