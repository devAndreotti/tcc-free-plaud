/**
 * conversationSearch.ts
 * Busca nas mensagens das abas abertas, sem diferenciar maiúscula nem acento.
 * A busca acha o termo no texto dobrado e devolve o trecho do texto original; por isso
 * cada caractere é dobrado à parte e guarda de onde veio.
 */

export interface SearchableTab {
  id: string;
  label: string;
}

export interface SearchableMessage {
  id: string;
  content: string;
}

export interface SearchHit {
  tabId: string;
  tabLabel: string;
  messageId: string;
  snippet: string;
}

const MAX_HITS = 50;
const CONTEXT_BEFORE = 40;
const CONTEXT_AFTER = 60;

/** Texto sem acento e em minúscula, com o índice original de cada caractere dobrado. */
const fold = (text: string): { folded: string; origin: number[] } => {
  let folded = '';
  const origin: number[] = [];
  let index = 0;
  for (const char of text) {
    const part = char.normalize('NFD').replace(/\p{M}/gu, '').toLowerCase();
    for (let i = 0; i < part.length; i += 1) origin.push(index);
    folded += part;
    index += char.length;
  }
  origin.push(text.length);
  return { folded, origin };
};

/** Trecho em volta do termo, com espaços juntos e reticências quando corta o texto. */
const snippetAround = (text: string, start: number, end: number): string => {
  const from = Math.max(0, start - CONTEXT_BEFORE);
  const to = Math.min(text.length, end + CONTEXT_AFTER);
  const body = text.slice(from, to).replace(/\s+/g, ' ').trim();
  return `${from > 0 ? '…' : ''}${body}${to < text.length ? '…' : ''}`;
};

/** Uma ocorrência por mensagem, nas abas na ordem em que aparecem. Termo vazio não acha nada. */
export const searchConversations = (
  tabs: SearchableTab[],
  tabMessages: Record<string, SearchableMessage[]>,
  query: string,
): SearchHit[] => {
  const needle = fold(query.trim()).folded;
  if (needle === '') return [];
  const hits: SearchHit[] = [];
  for (const tab of tabs) {
    for (const message of tabMessages[tab.id] ?? []) {
      const { folded, origin } = fold(message.content);
      const at = folded.indexOf(needle);
      if (at < 0) continue;
      const start = origin[at];
      const end = origin[at + needle.length] ?? message.content.length;
      hits.push({ tabId: tab.id, tabLabel: tab.label, messageId: message.id, snippet: snippetAround(message.content, start, end) });
      if (hits.length >= MAX_HITS) return hits;
    }
  }
  return hits;
};
