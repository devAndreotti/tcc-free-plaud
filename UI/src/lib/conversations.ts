/**
 * conversations.ts
 * Conversas salvas entre aberturas: converte o estado da tela (Date, abas em memória)
 * para o formato guardado pelo backend (timestamp em texto ISO) e de volta.
 * Na leitura, o que não tem a forma que a tela usa é descartado: um arquivo editado à mão
 * ou de outra versão não derruba a tela.
 */
import type { Tab } from '../components/Header';
import type { MessageData } from '../components/MessageBubble';
import type { SavedConversations, SavedMessage, SavedTab } from '../services/bridge';

/** O que se salva: abas, aba ativa e mensagens por aba (a digitação em andamento fica de fora). */
export interface ConversationSnapshot {
  tabs: Tab[];
  activeTabId: string | null;
  tabMessages: Record<string, MessageData[]>;
}

const toSavedTab = (tab: Tab): SavedTab => ({ id: tab.id, label: tab.label, type: tab.type, vaultId: tab.vaultId });

const toSavedMessage = (message: MessageData): SavedMessage => ({
  id: message.id,
  role: message.role,
  content: message.content,
  timestamp: message.timestamp.toISOString(),
  ask: message.ask,
});

export const toSavedConversations = ({ tabs, activeTabId, tabMessages }: ConversationSnapshot): SavedConversations => {
  const savedMessages: Record<string, SavedMessage[]> = {};
  for (const tab of tabs) savedMessages[tab.id] = (tabMessages[tab.id] ?? []).map(toSavedMessage);
  return { tabs: tabs.map(toSavedTab), activeTabId, tabMessages: savedMessages };
};

const isObject = (value: unknown): value is Record<string, unknown> => typeof value === 'object' && value !== null;

// Confere só o que a tela lê: texto onde ela mostra texto (noteTitle quebra sem caminho ou nota), listas onde ela percorre listas.
const isCitation = (value: unknown): boolean =>
  isObject(value) &&
  typeof value.note_id === 'string' &&
  typeof value.chunk_id === 'string' &&
  typeof value.snippet === 'string' &&
  (value.source_path === undefined || value.source_path === null || typeof value.source_path === 'string');

const isClaim = (value: unknown): boolean =>
  isObject(value) && typeof value.text === 'string' && Array.isArray(value.citations) && value.citations.every(isCitation);

const isAskResult = (value: unknown): boolean =>
  isObject(value) &&
  Array.isArray(value.claims) &&
  value.claims.every(isClaim) &&
  Array.isArray(value.citations) &&
  value.citations.every(isCitation) &&
  Array.isArray(value.limitations) &&
  value.limitations.every((item) => typeof item === 'string');

const toTab = (value: unknown): Tab | null => {
  if (!isObject(value) || value.type !== 'chat' || typeof value.id !== 'string' || typeof value.label !== 'string') return null;
  return { id: value.id, label: value.label, type: 'chat', vaultId: typeof value.vaultId === 'string' ? value.vaultId : undefined };
};

const toMessage = (value: unknown): MessageData | null => {
  if (!isObject(value) || typeof value.id !== 'string' || typeof value.content !== 'string') return null;
  if (value.role !== 'user' && value.role !== 'assistant') return null;
  const when = typeof value.timestamp === 'string' ? new Date(value.timestamp) : null;
  return {
    id: value.id,
    role: value.role,
    content: value.content,
    timestamp: when && !Number.isNaN(when.getTime()) ? when : new Date(),
    ask: isAskResult(value.ask) ? (value.ask as MessageData['ask']) : undefined,
  };
};

/** Lê o que o backend (ou o navegador) devolveu. Sem nenhuma aba válida, devolve null: o app começa do zero. */
export const fromSavedConversations = (saved: unknown): ConversationSnapshot | null => {
  if (!isObject(saved) || !Array.isArray(saved.tabs)) return null;
  const tabs = saved.tabs.map(toTab).filter((tab): tab is Tab => tab !== null);
  if (tabs.length === 0) return null;

  const savedMessages: Record<string, unknown> = isObject(saved.tabMessages) ? saved.tabMessages : {};
  const tabMessages: Record<string, MessageData[]> = {};
  for (const tab of tabs) {
    const list = savedMessages[tab.id];
    tabMessages[tab.id] = Array.isArray(list)
      ? list.map(toMessage).filter((message): message is MessageData => message !== null)
      : [];
  }

  const activeTabId =
    typeof saved.activeTabId === 'string' && tabs.some((tab) => tab.id === saved.activeTabId) ? saved.activeTabId : tabs[0].id;
  return { tabs, activeTabId, tabMessages };
};
