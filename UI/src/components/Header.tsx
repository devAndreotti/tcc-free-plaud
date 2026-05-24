import { XIcon } from './Icons';
import SettingsModal from './SettingsModal';

// Dados de uma aba aberta
export interface Tab {
  id: string;
  label: string;
  type: 'chat' | 'graph';
}

// Props do componente de cabeçalho/barra de abas
interface HeaderProps {
  tabs: Tab[];
  activeTabId: string | null;
  onSelectTab: (id: string) => void;
  onCloseTab: (id: string) => void;
  isSettingsOpen: boolean;
  onCloseSettings: () => void;
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

// Ícone de grafo/rede para o botão fixo
const GraphIcon = () => (
  <svg
    xmlns="http://www.w3.org/2000/svg"
    width={14}
    height={14}
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="2"
    strokeLinecap="round"
    strokeLinejoin="round"
    aria-hidden="true"
  >
    <circle cx="18" cy="5" r="3" />
    <circle cx="6" cy="12" r="3" />
    <circle cx="18" cy="19" r="3" />
    <line x1="8.59" y1="13.51" x2="15.42" y2="17.49" />
    <line x1="15.41" y1="6.51" x2="8.59" y2="10.49" />
  </svg>
);

// Cabeçalho da aplicação — barra de abas ao estilo editor/browser
const Header = ({
  tabs,
  activeTabId,
  onSelectTab,
  onCloseTab,
  isSettingsOpen,
  onCloseSettings,
  isGraphPanelOpen,
  onToggleGraphPanel,
}: HeaderProps) => {
  return (
    <>
      <header className="header" role="banner" aria-label="Barra de abas">
        {/* Lista de abas abertas */}
        <div className="tab-bar" role="tablist" aria-label="Abas abertas">
          {tabs.map((tab) => {
            const isActive = tab.id === activeTabId;
            return (
              <div
                key={tab.id}
                id={`tab-${tab.id}`}
                className={`tab ${isActive ? 'tab--active' : ''}`}
                role="tab"
                aria-selected={isActive}
                aria-controls={`tabpanel-${tab.id}`}
                onClick={() => onSelectTab(tab.id)}
              >
                {/* Ícone da aba conforme o tipo */}
                <span className="tab__icon" aria-hidden="true">
                  <ChatTabIcon />
                </span>

                {/* Label da aba */}
                <span className="tab__label">{tab.label}</span>

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
            <GraphIcon />
            <span>Grafos</span>
          </button>
        )}
      </header>

      {/* Modal de configurações (fora do header para z-index correto) */}
      <SettingsModal
        isOpen={isSettingsOpen}
        onClose={onCloseSettings}
      />
    </>
  );
};

export default Header;
