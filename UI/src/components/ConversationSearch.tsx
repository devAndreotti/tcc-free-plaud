import { useEffect, useMemo, useRef, useState } from 'react';
import { searchConversations } from '../lib/conversationSearch';
import type { MessageData } from './MessageBubble';
import type { Tab } from './Header';

interface ConversationSearchProps {
  tabs: Tab[];
  tabMessages: Record<string, MessageData[]>;
  onSelectTab: (id: string) => void;
}

const POPOVER_ID = 'conversation-search-popover';

const SearchIcon = () => (
  <svg xmlns="http://www.w3.org/2000/svg" width={14} height={14} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <circle cx="11" cy="11" r="7" />
    <path d="m20 20-3.5-3.5" />
  </svg>
);

/** Botão de busca no cabeçalho e o popover com o campo e os resultados (texto de todas as abas abertas). */
const ConversationSearch = ({ tabs, tabMessages, onSelectTab }: ConversationSearchProps) => {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState('');
  const rootRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const hits = useMemo(() => searchConversations(tabs, tabMessages, query), [tabs, tabMessages, query]);

  // Fora do popover e Escape fecham a busca; ao abrir, o foco vai para o campo.
  useEffect(() => {
    if (!open) return undefined;
    inputRef.current?.focus();
    const onPointerDown = (event: MouseEvent) => {
      if (!rootRef.current?.contains(event.target as Node)) setOpen(false);
    };
    document.addEventListener('mousedown', onPointerDown);
    return () => document.removeEventListener('mousedown', onPointerDown);
  }, [open]);

  const choose = (tabId: string) => {
    onSelectTab(tabId);
    setOpen(false);
  };

  return (
    <div className="conv-search" ref={rootRef} onKeyDown={(event) => event.key === 'Escape' && setOpen(false)}>
      <button
        type="button"
        className="header-action-btn conv-search__toggle"
        aria-label="Buscar nas conversas"
        title="Buscar nas conversas"
        aria-expanded={open}
        aria-controls={POPOVER_ID}
        onClick={() => setOpen((prev) => !prev)}
      >
        <SearchIcon />
      </button>

      {open && (
        <div id={POPOVER_ID} className="conv-search__popover" role="dialog" aria-label="Buscar nas conversas">
          <input
            ref={inputRef}
            type="search"
            className="conv-search__input"
            placeholder="Buscar nas conversas abertas"
            aria-label="Termo da busca"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
          />
          {query.trim() !== '' && hits.length === 0 && <p className="conv-search__empty">Nada encontrado nas conversas abertas.</p>}
          {hits.length > 0 && (
            <ul className="conv-search__results" aria-label="Resultados da busca">
              {hits.map((hit) => (
                <li key={`${hit.tabId}:${hit.messageId}`}>
                  <button type="button" className="conv-search__hit" onClick={() => choose(hit.tabId)}>
                    <span className="conv-search__tab">{hit.tabLabel}</span>
                    <span className="conv-search__snippet">{hit.snippet}</span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
};

export default ConversationSearch;
