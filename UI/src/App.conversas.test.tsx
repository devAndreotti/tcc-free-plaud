import { act, cleanup, render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeAll, describe, expect, it, vi } from 'vitest';
import App from './App';
import { bridge, type SavedConversations } from './services/bridge';

type User = ReturnType<typeof userEvent.setup>;

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

const send = async (user: User, text: string) => {
  await user.type(await screen.findByRole('textbox', { name: 'Campo de mensagem' }), text);
  await user.click(screen.getByRole('button', { name: 'Enviar mensagem' }));
};

const tabNamed = (label: string) =>
  within(screen.getByRole('tablist', { name: 'Abas abertas' })).getByText(label).closest('[role="tab"]') as HTMLElement;

// Carga que só termina quando o teste manda: simula o backend ainda respondendo.
const pendingLoad = () => {
  let finish: (value: SavedConversations | null) => void = () => {};
  vi.spyOn(bridge, 'loadConversations').mockReturnValue(
    new Promise<SavedConversations | null>((resolve) => {
      finish = resolve;
    })
  );
  return (value: SavedConversations | null) => act(async () => finish(value));
};

describe('App: conversas salvas entre aberturas', () => {
  beforeAll(() => {
    // jsdom não tem ResizeObserver nem canvas (mesmo ajuste de App.vault.test.tsx).
    vi.stubGlobal('ResizeObserver', class { observe() {} unobserve() {} disconnect() {} });
    vi.spyOn(HTMLCanvasElement.prototype, 'getContext').mockReturnValue(null);
    Element.prototype.scrollIntoView = vi.fn();
  });

  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
    void bridge.selectVault('obsidian');
  });

  it('restaura a aba salva com o rótulo e as mensagens', async () => {
    vi.spyOn(bridge, 'loadConversations').mockResolvedValue(SAVED);
    render(<App />);

    expect(await screen.findByText('Estudos de redes')).toBeTruthy();
    const history = await screen.findByRole('log', { name: 'Histórico de mensagens' });
    expect(await within(history).findByText('Qual broker foi adotado?')).toBeTruthy();
    expect(await within(history).findByText('O Mosquitto.')).toBeTruthy();
    expect(screen.getAllByRole('tab')).toHaveLength(1);
  });

  it('carga que chega com a vault já conhecida: abas de vault que sumiu não voltam', async () => {
    const finishLoad = pendingLoad();
    render(<App />);
    await waitForVault();

    await finishLoad({
      tabs: [
        { id: 'aba-obsidian', label: 'Da Obsidian', type: 'chat', vaultId: 'obsidian' },
        { id: 'aba-sumida', label: 'Da vault sumida', type: 'chat', vaultId: 'vault-sumida' },
      ],
      activeTabId: 'aba-sumida',
      tabMessages: {
        'aba-obsidian': [],
        'aba-sumida': [{ id: 'm1', role: 'user', content: 'Pergunta antiga', timestamp: '2026-10-19T10:00:00.000Z' }],
      },
    });

    expect(await screen.findByText('Da Obsidian')).toBeTruthy();
    expect(screen.queryByText('Da vault sumida')).toBeNull();
    expect(screen.queryByText('Pergunta antiga')).toBeNull();
    expect(screen.getAllByRole('tab')).toHaveLength(1);
  });

  it('pergunta enviada antes da carga não some, e a conversa salva entra junto', async () => {
    const finishLoad = pendingLoad();
    const user = userEvent.setup();
    render(<App />);
    await waitForVault();
    await send(user, 'Pergunta antes da carga');

    await finishLoad(SAVED);

    expect(await screen.findByText('Estudos de redes')).toBeTruthy();
    expect(tabNamed('Pergunta antes da carga')).toBeTruthy();
    expect(within(screen.getByRole('log', { name: 'Histórico de mensagens' })).getByText('Pergunta antes da carga')).toBeTruthy();
  });

  it('não grava antes de a carga terminar; depois grava o que está na tela', async () => {
    const finishLoad = pendingLoad();
    const saveSpy = vi.spyOn(bridge, 'saveConversations').mockResolvedValue({ ok: true });
    const user = userEvent.setup();
    render(<App />);
    await send(user, 'Pergunta sem carga');

    await new Promise((resolve) => setTimeout(resolve, 600));
    expect(saveSpy).not.toHaveBeenCalled();

    await finishLoad(null);
    await waitFor(() => expect(saveSpy).toHaveBeenCalled());
    expect(saveSpy.mock.lastCall?.[0].tabs[0].label).toBe('Pergunta sem carga');
  });

  it('enviar uma mensagem dispara saveConversations com o texto e a data em ISO', async () => {
    const saveSpy = vi.spyOn(bridge, 'saveConversations').mockResolvedValue({ ok: true });
    const user = userEvent.setup();
    render(<App />);
    await waitForVault();
    await send(user, 'Quais notas falam de VLAN?');

    const savedMessages = () => saveSpy.mock.calls.flatMap(([payload]) => Object.values(payload.tabMessages).flat());
    await waitFor(() => expect(savedMessages().map((message) => message.content)).toContain('Quais notas falam de VLAN?'));
    expect(savedMessages().every((message) => typeof message.timestamp === 'string')).toBe(true);
  });
});
