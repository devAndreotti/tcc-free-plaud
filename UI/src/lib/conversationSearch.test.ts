import { describe, expect, it } from 'vitest';
import { searchConversations } from './conversationSearch';

const tabs = [
  { id: 't1', label: 'Prazos' },
  { id: 't2', label: 'Compras' },
];
const tabMessages = {
  t1: [{ id: 'm1', content: 'A reunião de Ação fica para amanhã.' }],
  t2: [{ id: 'm2', content: 'Comprar café e pão.' }, { id: 'm3', content: 'Nada aqui.' }],
};

describe('searchConversations', () => {
  it('ignora maiúscula e acento', () => {
    const hits = searchConversations(tabs, tabMessages, 'acao');
    expect(hits).toHaveLength(1);
    expect(hits[0]).toMatchObject({ tabId: 't1', tabLabel: 'Prazos', messageId: 'm1' });
    expect(hits[0].snippet).toContain('Ação');
    expect(searchConversations(tabs, tabMessages, 'CAFÉ')[0].messageId).toBe('m2');
  });

  it('acha em todas as abas abertas e termo vazio não acha nada', () => {
    expect(searchConversations(tabs, tabMessages, 'a').map((h) => h.tabId)).toEqual(['t1', 't2', 't2']);
    expect(searchConversations(tabs, tabMessages, '   ')).toEqual([]);
  });

  it('não desloca o trecho quando o texto tem caractere que muda de tamanho ao dobrar', () => {
    const hits = searchConversations(tabs, { t1: [{ id: 'x', content: 'İstambul e café' }] }, 'cafe');
    expect(hits[0].snippet).toContain('café');
  });

  it('nada encontrado devolve lista vazia', () => {
    expect(searchConversations(tabs, tabMessages, 'inexistente')).toEqual([]);
  });
});
