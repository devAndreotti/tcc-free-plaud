import { afterEach, describe, expect, it } from 'vitest';
import { bridge, CONVERSATIONS_STORAGE_KEY, type SavedConversations } from './bridge';

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

describe('loadConversations (mock sem PyWebView)', () => {
  afterEach(() => {
    window.localStorage.removeItem(CONVERSATIONS_STORAGE_KEY);
    delete (window as unknown as { pywebview?: unknown }).pywebview;
  });

  it('devolve null quando não há conversas salvas no localStorage', async () => {
    expect(await bridge.loadConversations()).toBeNull();
  });

  it('devolve as conversas salvas no localStorage quando não há PyWebView', async () => {
    window.localStorage.setItem(CONVERSATIONS_STORAGE_KEY, JSON.stringify(SAVED));

    expect(await bridge.loadConversations()).toEqual(SAVED);
  });
});
