import { describe, expect, it } from 'vitest';
import { fromSavedConversations, toSavedConversations, type ConversationSnapshot } from './conversations';

const ask = {
  query: 'Qual broker?',
  status: 'answer' as const,
  no_answer: false,
  answer: 'Mosquitto.',
  claims: [],
  citations: [],
  limitations: [],
  reason_for_no_answer: null,
  latency_ms: 12,
};

const snapshot: ConversationSnapshot = {
  tabs: [
    { id: 'aba-1', label: 'Redes', type: 'chat', vaultId: 'obsidian' },
    { id: 'aba-2', label: 'Bolo', type: 'chat', vaultId: 'culinaria' },
  ],
  activeTabId: 'aba-2',
  tabMessages: {
    'aba-1': [
      { id: 'm1', role: 'user', content: 'Qual broker?', timestamp: new Date('2026-10-19T10:00:00.000Z') },
      { id: 'm2', role: 'assistant', content: 'Mosquitto.', timestamp: new Date('2026-10-19T10:00:02.000Z'), ask },
    ],
    'aba-2': [],
  },
};

describe('conversas salvas: ida e volta', () => {
  it('o que se salva volta igual, com a data de volta como Date e a resposta estruturada', () => {
    const saved = JSON.parse(JSON.stringify(toSavedConversations(snapshot)));

    expect(saved.tabMessages['aba-1'][1].timestamp).toBe('2026-10-19T10:00:02.000Z');
    expect(fromSavedConversations(saved)).toEqual(snapshot);
  });

  it('descarta o que não tem a forma esperada e volta à primeira aba se a ativa sumiu', () => {
    const restored = fromSavedConversations({
      tabs: [
        { id: 'aba-1', label: 'Redes', type: 'chat' },
        { id: 7, label: 'quebrada', type: 'chat' },
        { id: 'aba-g', label: 'Grafo', type: 'graph' },
      ],
      activeTabId: 'sumiu',
      tabMessages: {
        'aba-1': [
          { id: 'm1', role: 'user', content: 'oi', timestamp: '2026-10-19T10:00:00.000Z' },
          { id: 'm2', role: 'papel-estranho', content: 'x', timestamp: '2026-10-19T10:00:00.000Z' },
          'lixo',
          {
            id: 'm3',
            role: 'assistant',
            content: 'y',
            timestamp: '2026-10-19T10:00:01.000Z',
            ask: { claims: 'nao é lista', citations: [], limitations: [] },
          },
        ],
      },
    });

    expect(restored?.tabs.map((tab) => tab.id)).toEqual(['aba-1']);
    expect(restored?.activeTabId).toBe('aba-1');
    expect(restored?.tabMessages['aba-1'].map((message) => message.id)).toEqual(['m1', 'm3']);
    expect(restored?.tabMessages['aba-1'][1].ask).toBeUndefined();
  });

  it('sem nenhuma aba válida, ou com lixo no lugar, não restaura nada', () => {
    expect(fromSavedConversations({ tabs: [], activeTabId: null, tabMessages: {} })).toBeNull();
    expect(fromSavedConversations('lixo')).toBeNull();
    expect(fromSavedConversations(null)).toBeNull();
  });
});
