import { useState } from 'react';
import { GraphIcon, PlusIcon, XIcon } from './Icons';
import SettingsModal, { type SettingsTab } from './SettingsModal';
import { VaultGlyph } from './VaultGlyph';
import type { Vault } from '../services/bridge';

// Dados de uma aba aberta
export interface Tab {
  id: string;
  label: string;
  type: 'chat' | 'graph';
  /** Vault da conversa ('' = aberta antes da lista de vaults chegar). */
  vaultId?: string;
}

// Props do componente de cabeçalho/barra de abas
interface HeaderProps {
  tabs: Tab[];
  activeTabId: string | null;
  onSelectTab: (id: string) => void;
  onCloseTab: (id: string) => void;
  onRenameTab: (id: string, label: string) => void;
  vaults: Vault[];
  onNewTab: () => void;
  isSettingsOpen: boolean;
  settingsTab?: SettingsTab;
  onCloseSettings: () => void;
  onOpenQueue: () => void;
  isGraphPanelOpen: boolean;
  onToggleGraphPanel: () => void;
}

// Ícone de mensagem de chat para a aba
const ChatTabIcon = () => (
  <svg
    xmlns="http://www.w3.org/2000/svg"
    width={13}
    height={13}
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="2"
    strokeLinecap="round"
    strokeLinejoin="round"
    aria-hidden="true"
  >
    <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
  </svg>
);

// Cabeçalho da aplicação — barra de abas ao estilo editor/browser
const Header = ({
  tabs,
  activeTabId,
  onSelectTab,
  onCloseTab,
  onRenameTab,
  vaults,
  onNewTab,
  isSettingsOpen,
  settingsTab,
  onCloseSettings,
  onOpenQueue,
  isGraphPanelOpen,
  onToggleGraphPanel,
}: HeaderProps) => {
  // Aba em edição do nome (duplo clique): Enter ou sair do campo salva, Esc cancela.
  const [editing, setEditing] = useState<{ id: string; draft: string } | null>(null);
  const commitRename = () => {
    if (editing?.draft.trim()) onRenameTab(editing.id, editing.draft.trim());
    setEditing(null);
  };

  return (
    <>
      <header className="header" role="banner" aria-label="Barra de abas">
        {/* Lista de abas abertas */}
        <div className="tab-bar" role="tablist" aria-label="Abas abertas">
          {tabs.map((tab) => {
            const isActive = tab.id === activeTabId;
            const vault = vaults.find((item) => item.id === tab.vaultId);
            return (
              <div
                key={tab.id}
                id={`tab-${tab.id}`}
                className={`tab ${isActive ? 'tab--active' : ''}`}
                role="tab"
                aria-selected={isActive}
                aria-controls={`tabpanel-${tab.id}`}
                title={vault ? `${tab.label} · ${vault.name}` : tab.label}
                onClick={() => onSelectTab(tab.id)}
                onDoubleClick={() => setEditing({ id: tab.id, draft: tab.label })}
              >
                {/* Ícone e cor da vault da conversa */}
                <span className="tab__icon" aria-hidden="true">
                  {vault ? <VaultGlyph icon={vault.icon} color={vault.color} size={12} /> : <ChatTabIcon />}
                </span>

                {/* Label da aba; duplo clique renomeia */}
                {editing?.id === tab.id ? (
                  <input
                    className="tab__rename"
                    aria-label="Nome da conversa"
                    value={editing.draft}
                    maxLength={60}
                    autoFocus
                    onClick={(e) => e.stopPropagation()}
                    onChange={(e) => setEditing({ id: tab.id, draft: e.target.value })}
                    onBlur={commitRename}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter') commitRename();
                      if (e.key === 'Escape') setEditing(null);
                    }}
                  />
                ) : (
                  <span className="tab__label">{tab.label}</span>
                )}

                {/* Botão de fechar */}
                <button
                  type="button"
                  className="tab__close"
                  aria-label={`Fechar aba ${tab.label}`}
                  onClick={(e) => {
                    e.stopPropagation(); // evita selecionar ao fechar
                    onCloseTab(tab.id);
                  }}
                >
                  <XIcon size={10} />
                </button>
              </div>
            );
          })}
        </div>

        <button
          type="button"
          id="btn-new-tab"
          className="tab-bar__new"
          aria-label="Nova conversa"
          title="Nova conversa"
          onClick={onNewTab}
        >
          <PlusIcon size={15} />
        </button>

        {/* Área vazia após as abas — droppable / espaço livre */}
        <div className="tab-bar__spacer" aria-hidden="true" />

        {/* Botão fixo de Grafos — visível apenas com o painel fechado */}
        {!isGraphPanelOpen && (
          <button
            type="button"
            id="btn-grafos"
            className="header-action-btn"
            aria-label="Abrir painel de grafos"
            aria-expanded={false}
            aria-controls="graph-panel"
            onClick={onToggleGraphPanel}
          >
            <GraphIcon size={14} />
            <span>Grafos</span>
          </button>
        )}
      </header>

      {/* Modal de configurações (fora do header para z-index correto) */}
      <SettingsModal
        isOpen={isSettingsOpen}
        onClose={onCloseSettings}
        initialTab={settingsTab}
        onOpenQueue={onOpenQueue}
      />
    </>
  );
};

export default Header;
