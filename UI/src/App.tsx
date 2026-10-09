import { useState, useRef, useEffect, useCallback } from 'react';
import './App.css';

import Header, { type Tab } from './components/Header';
import Sidebar, { type WorkspaceView } from './components/Sidebar';
import type { SettingsTab } from './components/SettingsModal';
import WelcomeScreen from './components/WelcomeScreen';
import MessageBubble, {
  TypingIndicator,
  type MessageData,
} from './components/MessageBubble';
import ChatInput from './components/ChatInput';
import GraphPanel from './components/GraphPanel';
import NotesPanel from './components/NotesPanel';
import BenchmarkPanel from './components/BenchmarkPanel';
import QueuePanel from './components/QueuePanel';
import { bridge, type AskStrategy } from './services/bridge';
import { VaultProvider } from './contexts/VaultContext';
import { QueueProvider } from './contexts/QueueContext';

// Gera ID único para mensagens e abas
const generateId = () =>
  `${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;

// Aba inicial da aplicação
const INITIAL_TAB: Tab = {
  id: generateId(),
  label: 'Nova Conversa',
  type: 'chat',
};

// Estado de conversa vazia para reutilização
const EMPTY_MESSAGES: MessageData[] = [];

function App() {
  // Gerenciamento de abas
  const [tabs, setTabs] = useState<Tab[]>([INITIAL_TAB]);
  const [activeTabId, setActiveTabId] = useState<string | null>(INITIAL_TAB.id);

  // Mensagens e estado de digitação isolados por aba: Record<tabId, ...>
  const [tabMessages, setTabMessages] = useState<Record<string, MessageData[]>>({
    [INITIAL_TAB.id]: [],
  });
  const [tabTyping, setTabTyping] = useState<Record<string, boolean>>({});

  const [isSettingsOpen, setIsSettingsOpen] = useState(false);
  const [settingsTab, setSettingsTab] = useState<SettingsTab | undefined>(undefined);
  const [healthKey, setHealthKey] = useState(0);
  const [isGraphPanelOpen, setIsGraphPanelOpen] = useState(false);
  const [workspaceView, setWorkspaceView] = useState<WorkspaceView>('chat');
  const [strategy, setStrategy] = useState<AskStrategy>('hybrid');

  const openSettings = useCallback((tab?: SettingsTab) => {
    setSettingsTab(tab);
    setIsSettingsOpen(true);
  }, []);

  const closeSettings = useCallback(() => {
    setIsSettingsOpen(false);
    setHealthKey((prev) => prev + 1);
  }, []);

  const navigate = useCallback((view: WorkspaceView) => {
    setWorkspaceView(view);
  }, []);

  const openQueueFromSettings = useCallback(() => {
    closeSettings();
    setWorkspaceView('queue');
  }, [closeSettings]);

  // Alterna a visibilidade do painel lateral de grafos
  const handleToggleGraphPanel = useCallback(() => {
    setIsGraphPanelOpen((prev) => !prev);
  }, []);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Mensagens e estado de digitação da aba ativa
  const activeMessages = activeTabId ? (tabMessages[activeTabId] ?? EMPTY_MESSAGES) : EMPTY_MESSAGES;
  const isTyping = activeTabId ? (tabTyping[activeTabId] ?? false) : false;

  // Mantém o scroll sempre no final da lista de mensagens da aba ativa
  const scrollToBottom = useCallback(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [activeMessages, isTyping, scrollToBottom]);

  // Seleciona uma aba pelo id
  const handleSelectTab = useCallback((id: string) => {
    setActiveTabId(id);
    setWorkspaceView('chat');
  }, []);

  // Fecha uma aba; limpa seu estado e ativa a vizinha
  const handleCloseTab = useCallback(
    (id: string) => {
      // Remove as mensagens da aba fechada
      setTabMessages((prev) => {
        const next = { ...prev };
        delete next[id];
        return next;
      });
      setTabTyping((prev) => {
        const next = { ...prev };
        delete next[id];
        return next;
      });

      setTabs((prev) => {
        if (prev.length === 1) {
          setActiveTabId(null);
          return [];
        }
        const idx = prev.findIndex((t) => t.id === id);
        const next = prev.filter((t) => t.id !== id);
        // Se a aba fechada era a ativa, ativa a vizinha
        if (id === activeTabId) {
          const newActive = next[Math.max(0, idx - 1)];
          setActiveTabId(newActive?.id ?? null);
        }
        return next;
      });
    },
    [activeTabId]
  );

  // Abre nova aba de chat com conversa própria e a torna ativa
  const handleNewTab = useCallback(() => {
    const newTab: Tab = {
      id: generateId(),
      label: 'Nova Conversa',
      type: 'chat',
    };
    // Inicializa a conversa vazia da nova aba
    setTabMessages((prev) => ({ ...prev, [newTab.id]: [] }));
    setTabs((prev) => [...prev, newTab]);
    setActiveTabId(newTab.id);
    setWorkspaceView('chat');
  }, []);

  const appendMessage = useCallback((tabId: string, message: MessageData) => {
    setTabMessages((prev) => ({ ...prev, [tabId]: [...(prev[tabId] ?? []), message] }));
  }, []);

  // Pergunta ao corpus e anexa a resposta (estruturada, quando o backend a devolve)
  const askInTab = useCallback(
    async (tabId: string, text: string, askStrategy: AskStrategy) => {
      setTabTyping((prev) => ({ ...prev, [tabId]: true }));
      try {
        const ask = await bridge.askCorpus(text, askStrategy);
        appendMessage(tabId, {
          id: `msg-${generateId()}`,
          role: 'assistant',
          content: ask.answer ?? '',
          timestamp: new Date(),
          ask,
        });
      } catch (error) {
        // Exibe erro como mensagem do assistente para não travar a UI
        appendMessage(tabId, {
          id: `msg-${generateId()}`,
          role: 'assistant',
          content: 'Ocorreu um erro ao processar sua mensagem. Tente novamente.',
          timestamp: new Date(),
        });
        console.error('[App] Erro ao chamar bridge.askCorpus:', error);
      } finally {
        setTabTyping((prev) => ({ ...prev, [tabId]: false }));
      }
    },
    [appendMessage]
  );

  // Envia mensagem na conversa da aba ativa
  const handleSendMessage = useCallback(
    async (text: string, attachment?: File) => {
      if (!activeTabId) return;
      if (!text.trim() && !attachment) return;

      appendMessage(activeTabId, {
        id: `msg-${generateId()}`,
        role: 'user',
        content: text || `[Arquivo: ${attachment?.name}]`,
        timestamp: new Date(),
      });
      // O nome da primeira pergunta vira o título da aba
      setTabs((prev) =>
        prev.map((tab) =>
          tab.id === activeTabId && tab.label === 'Nova Conversa' && text.trim()
            ? { ...tab, label: text.trim().length > 32 ? `${text.trim().slice(0, 32)}…` : text.trim() }
            : tab
        )
      );
      await askInTab(activeTabId, text, strategy);
    },
    [activeTabId, appendMessage, askInTab, strategy]
  );

  const handleRetry = useCallback(
    (query: string, retryStrategy: AskStrategy) => {
      if (activeTabId) void askInTab(activeTabId, query, retryStrategy);
    },
    [activeTabId, askInTab]
  );

  // Determina a aba ativa para renderizar a view correta
  const activeTab = tabs.find((t) => t.id === activeTabId) ?? null;
  const hasMessages = activeMessages.length > 0;

  return (
    <VaultProvider>
      <QueueProvider>
        {/* Layout raiz: sidebar à esquerda + coluna de conteúdo à direita */}
        <div className="app" id="app-root">
          {/* Barra lateral esquerda */}
          <Sidebar
            activeView={workspaceView}
            onNavigate={navigate}
            onOpenSettings={openSettings}
            healthKey={healthKey}
          />

          {/* Coluna de conteúdo principal (tab bar + view) */}
          <div className="app__content">
            {/* Barra de abas */}
            <Header
              tabs={tabs}
              activeTabId={workspaceView === 'chat' ? activeTabId : null}
              onSelectTab={handleSelectTab}
              onCloseTab={handleCloseTab}
              onNewTab={handleNewTab}
              isSettingsOpen={isSettingsOpen}
              settingsTab={settingsTab}
              onCloseSettings={closeSettings}
              onOpenQueue={openQueueFromSettings}
              isGraphPanelOpen={isGraphPanelOpen}
              onToggleGraphPanel={handleToggleGraphPanel}
            />

            {/* View ativa conforme a aba selecionada */}
            {workspaceView === 'notes' && <NotesPanel />}

            {workspaceView === 'benchmark' && <BenchmarkPanel />}

            {workspaceView === 'queue' && <QueuePanel onOpenSettings={openSettings} />}

            {workspaceView === 'chat' && activeTab?.type === 'chat' && (
              <main
                className="main"
                id={`tabpanel-${activeTab.id}`}
                role="tabpanel"
                aria-labelledby={`tab-${activeTab.id}`}
              >
                {/* Lista de mensagens da aba ativa, ou tela de boas-vindas */}
                {hasMessages ? (
                  <div
                    className="messages-area"
                    role="log"
                    aria-label="Histórico de mensagens"
                    aria-live="polite"
                  >
                    {activeMessages.map((message) => (
                      <MessageBubble key={message.id} message={message} onRetry={handleRetry} />
                    ))}

                    {/* Indicador de digitação da aba ativa */}
                    {isTyping && <TypingIndicator />}

                    {/* Âncora de scroll para o final */}
                    <div ref={messagesEndRef} aria-hidden="true" />
                  </div>
                ) : (
                  <WelcomeScreen />
                )}
              </main>
            )}

            {/* Estado vazio: nenhuma aba aberta */}
            {workspaceView === 'chat' && !activeTab && (
              <main className="main main--empty" id="main-content">
                <div className="empty-state">
                  <p className="empty-state__text">Nenhuma aba aberta.</p>
                </div>
              </main>
            )}

            {/* Input de mensagem (visível apenas com aba de chat ativa) */}
            {workspaceView === 'chat' && activeTab?.type === 'chat' && (
              <ChatInput
                onSendMessage={handleSendMessage}
                isLoading={isTyping}
                strategy={strategy}
                onStrategyChange={setStrategy}
              />
            )}
          </div>

          {/* Painel lateral de grafos — expande à direita do conteúdo */}
          <GraphPanel isOpen={isGraphPanelOpen} onToggle={handleToggleGraphPanel} />
        </div>
      </QueueProvider>
    </VaultProvider>
  );
}

export default App;
