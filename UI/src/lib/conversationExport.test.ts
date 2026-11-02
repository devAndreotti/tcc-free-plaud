import { describe, expect, it } from 'vitest';
import { buildConversationMarkdown, conversationFileName } from './conversationExport';
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

describe('conversationFileName', () => {
  it('troca separadores de pasta e caracteres proibidos', () => {
    expect(conversationFileName('a/b\\c: d?')).toBe('a-b-c- d-.md');
  });

  it('usa um nome padrão quando o título fica vazio', () => {
    expect(conversationFileName('   ')).toBe('conversa.md');
  });
});
