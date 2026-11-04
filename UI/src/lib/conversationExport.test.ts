import { describe, expect, it, vi } from 'vitest';
import { buildConversationExport, buildConversationMarkdown, conversationFileName, conversationTitle, printConversation } from './conversationExport';
import type { MessageData } from '../components/MessageBubble';
import type { AskResult } from '../services/bridge';

const citation = (chunk: string, path: string | null, start: number, end: number) => ({
  note_id: 'n1',
  note_version: 1,
  chunk_id: chunk,
  snippet: '',
  source_path: path,
  char_start: start,
  char_end: end,
});

const ask = {
  answer: 'Resposta curta.',
  claims: [{ text: 'Resposta curta.', citations: [citation('c1', 'notas/a.md', 0, 120)], support_level: 'direct' }],
  citations: [citation('c1', 'notas/a.md', 0, 120), citation('c2', null, 300, 340)],
  limitations: [],
} as unknown as AskResult;

const messages: MessageData[] = [
  { id: 'u1', role: 'user', content: 'Qual é o prazo?', timestamp: new Date() },
  { id: 'a1', role: 'assistant', content: 'Resposta curta.', timestamp: new Date(), ask },
];

describe('buildConversationMarkdown', () => {
  it('traz título, pergunta, resposta e fontes sem repetir trecho', () => {
    const md = buildConversationMarkdown({ title: 'Prazos', messages, exportedAt: new Date(2026, 10, 2, 9, 30) });
    expect(md.startsWith('# Prazos\n')).toBe(true);
    expect(md).toContain('## Pergunta\n\nQual é o prazo?');
    expect(md).toContain('## Resposta\n\nResposta curta.');
    expect(md).toContain('**Fontes:**\n\n1. notas/a.md (0–120)\n2. n1 (300–340)');
  });

  it('usa o texto da mensagem quando não há resposta estruturada', () => {
    const md = buildConversationMarkdown({
      title: '',
      messages: [{ id: 'e', role: 'assistant', content: 'Ocorreu um erro.', timestamp: new Date() }],
      exportedAt: new Date(),
    });
    expect(md).toContain('# Conversa');
    expect(md).toContain('## Resposta\n\nOcorreu um erro.');
    expect(md).not.toContain('Fontes');
  });
});

describe('caminho das fontes no arquivo', () => {
  const longa = { ...ask, claims: [], citations: [citation('c9', String.raw`C:\Users\alguem\Notas\Estudos\Redes\vlan.md`, 0, 10)] };
  const msgs = [{ id: 'a', role: 'assistant', content: '', timestamp: new Date(), ask: longa }] as unknown as MessageData[];
  const input = { title: 'T', messages: msgs, exportedAt: new Date('2026-11-04T12:00:00Z') };

  it.each(['md', 'txt', 'html', 'json'] as const)('%s não mostra a pasta do usuário', (format) => {
    const out = buildConversationExport(format, input);
    expect(out).toContain('Estudos/Redes/vlan.md');
    expect(out).not.toContain('alguem');
  });
});

describe('conversationTitle', () => {
  const msgs = (content: string) => [{ id: 'u', role: 'user', content, timestamp: new Date() }] as unknown as MessageData[];
  const pergunta = 'Quais são os estágios de refinamento do Lakehouse?';

  it('troca o rótulo cortado da aba pela pergunta inteira', () => {
    expect(conversationTitle(`${pergunta.slice(0, 32)}…`, msgs(pergunta))).toBe(pergunta);
  });

  it('aba renomeada fica com o nome que recebeu', () => {
    expect(conversationTitle('Lakehouse', msgs(pergunta))).toBe('Lakehouse');
    expect(conversationTitle('Outro assunto…', msgs(pergunta))).toBe('Outro assunto…');
  });
});

describe('printConversation', () => {
  it('o título da página vira o nome sugerido e volta depois da impressão', () => {
    const print = vi.spyOn(window, 'print').mockImplementation(() => {});
    document.title = 'Escólio';
    printConversation({ title: 'Redes: VLAN', messages: [], exportedAt: new Date() });
    expect(print).toHaveBeenCalled();
    expect(document.title).toBe('Redes- VLAN');
    expect(document.querySelector('.print-root')).not.toBeNull();
    window.dispatchEvent(new Event('afterprint'));
    expect(document.title).toBe('Escólio');
    expect(document.querySelector('.print-root')).toBeNull();
    print.mockRestore();
  });
});

describe('conversationFileName', () => {
  it('troca separadores de pasta e caracteres proibidos', () => {
    expect(conversationFileName('a/b\\c: d?')).toBe('a-b-c- d-.md');
  });

  it('usa um nome padrão quando o título fica vazio', () => {
    expect(conversationFileName('   ')).toBe('conversa.md');
  });
});
