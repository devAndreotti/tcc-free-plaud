import { useState } from 'react';
import type { Vault } from '../services/bridge';
import { VaultGlyph } from './VaultGlyph';
import './NoChatsScreen.css';

export interface RecentChat {
  id: string;
  label: string;
  vaultName: string | null;
}

interface NoChatsScreenProps {
  vaults: Vault[];
  recent: RecentChat[];
  onNewChat: (vaultId: string) => void;
  onReopen: (chatId: string) => void;
  onOpenQueue: () => void;
}

const SEARCH_FROM = 7;

const fmt = (value: number) => value.toLocaleString('pt-BR');

// A arte segue a cor de destaque: tudo nela vem dos tokens do tema.
const Art = () => (
  <svg className="nochats__art" width="264" height="150" viewBox="0 0 300 170" fill="none" aria-hidden="true">
    <circle className="nochats__halo" cx="150" cy="86" r="70" />
    <circle className="nochats__orbit" cx="150" cy="86" r="70" strokeDasharray="3 8" />
    <g className="nochats__float nochats__float--1">
      <rect className="nochats__tab" x="20" y="30" width="78" height="46" rx="10" />
      <rect className="nochats__line-strong" x="31" y="42" width="38" height="5" rx="2.5" />
      <rect className="nochats__line" x="31" y="54" width="56" height="5" rx="2.5" />
      <path className="nochats__stroke" d="M84 38l6 6m0-6l-6 6" strokeWidth="1.5" strokeLinecap="round" />
    </g>
    <g className="nochats__float nochats__float--2">
      <rect className="nochats__tab" x="206" y="24" width="72" height="40" rx="10" />
      <rect className="nochats__line" x="217" y="35" width="50" height="5" rx="2.5" />
      <rect className="nochats__line-strong" x="217" y="46" width="30" height="5" rx="2.5" />
    </g>
    <g className="nochats__float nochats__float--3">
      <rect className="nochats__tab" x="212" y="106" width="66" height="38" rx="10" />
      <rect className="nochats__line-strong" x="223" y="117" width="34" height="5" rx="2.5" />
      <rect className="nochats__line" x="223" y="128" width="44" height="5" rx="2.5" />
    </g>
    <path
      className="nochats__bubble"
      d="M122 58h56a11 11 0 0 1 11 11v30a11 11 0 0 1-11 11h-36l-17 14v-14h-3a11 11 0 0 1-11-11V69a11 11 0 0 1 11-11z"
      strokeWidth="1.75"
      strokeDasharray="6 4"
    />
    <path className="nochats__stroke" d="M150 72v24M138 84h24" strokeWidth="2.25" strokeLinecap="round" />
  </svg>
);

// Todas as abas fechadas: escolher em qual vault abrir uma conversa ou voltar a uma recente.
const NoChatsScreen = ({ vaults, recent, onNewChat, onReopen, onOpenQueue }: NoChatsScreenProps) => {
  const [query, setQuery] = useState('');
  const hasNotes = vaults.some((vault) => (vault.note_count ?? 0) > 0);
  const term = query.trim().toLowerCase();
  const shown = term ? vaults.filter((vault) => vault.name.toLowerCase().includes(term)) : vaults;

  return (
    <main className="main main--empty nochats" id="main-content">
      <Art />
      <h1 className="nochats__title">Você fechou todos os chats</h1>
      <p className="nochats__lede">
        {hasNotes || vaults.length === 0
          ? 'Escolha uma vault para abrir uma conversa nova. Cada vault responde só com as notas dela.'
          : 'Sua vault ainda está vazia. Indexe uma pasta para começar a perguntar.'}
      </p>

      {vaults.length >= SEARCH_FROM && (
        <input
          id="nochats-search"
          className="nochats__search"
          aria-label="Buscar vault"
          placeholder="Buscar vault"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
        />
      )}

      {shown.length > 0 ? (
        <ul className={`nochats__vaults${shown.length === 1 ? ' nochats__vaults--one' : ''}`} aria-label="Vaults">
          {shown.map((vault) => {
            const notes = vault.note_count ?? 0;
            return (
              <li key={vault.id}>
                <button
                  type="button"
                  className="nochats__vault"
                  onClick={() => (notes > 0 ? onNewChat(vault.id) : onOpenQueue())}
                >
                  <span className="nochats__glyph"><VaultGlyph icon={vault.icon} color={vault.color} size={20} /></span>
                  <span className="nochats__vault-text">
                    <b>{vault.name}</b>
                    <span className="mono">{notes > 0 ? `${fmt(notes)} ${notes === 1 ? 'nota' : 'notas'}` : 'nenhuma nota ainda'}</span>
                  </span>
                  <span className="nochats__cta">{notes > 0 ? 'Nova conversa' : 'Indexar uma pasta'}</span>
                </button>
              </li>
            );
          })}
        </ul>
      ) : (
        vaults.length > 0 && <p className="nochats__none" role="status">Nenhuma vault com esse nome.</p>
      )}

      {recent.length > 0 && (
        <section className="nochats__recent" aria-label="Conversas recentes">
          <h2>Conversas recentes</h2>
          <ul>
            {recent.map((chat) => (
              <li key={chat.id}>
                <button type="button" className="nochats__chat" onClick={() => onReopen(chat.id)}>
                  <span>{chat.label}</span>
                  {chat.vaultName && <small>{chat.vaultName}</small>}
                </button>
              </li>
            ))}
          </ul>
        </section>
      )}

      <p className="nochats__hint">
        <kbd>Ctrl</kbd>+<kbd>T</kbd> abre uma conversa na vault ativa
        <span aria-hidden="true">·</span>
        <button type="button" className="nochats__link" onClick={onOpenQueue}>Indexar outra pasta</button>
      </p>
    </main>
  );
};

export default NoChatsScreen;
