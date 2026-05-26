import { useState, useRef, useEffect, useCallback } from 'react';
import './App.css';

import Header, { type Tab } from './components/Header';
import Sidebar from './components/Sidebar';
import WelcomeScreen from './components/WelcomeScreen';
import MessageBubble, {
  TypingIndicator,
  type MessageData,
} from './components/MessageBubble';
import ChatInput from './components/ChatInput';
import GraphPanel from './components/GraphPanel';
import NotesPanel from './components/NotesPanel';
import BenchmarkPanel from './components/BenchmarkPanel';
import { bridge } from './services/bridge';
import { VaultProvider } from './contexts/VaultContext';

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
type WorkspaceView = 'chat' | 'notes' | 'benchmark';

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
  const [isGraphPanelOpen, setIsGraphPanelOpen] = useState(false);
  const [workspaceView, setWorkspaceView] = useState<WorkspaceView>('chat');

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

  // Envia mensagem na conversa da aba ativa
  const handleSendMessage = useCallback(
    async (text: string, attachment?: File) => {
      if (!activeTabId) return;
      if (!text.trim() && !attachment) return;

      // Adiciona mensagem do usuário na aba ativa imediatamente
      const userMessage: MessageData = {
        id: `msg-${generateId()}`,
        role: 'user',
        content: text || `[Arquivo: ${attachment?.name}]`,
        timestamp: new Date(),
      };
      setTabMessages((prev) => ({
        ...prev,
        [activeTabId]: [...(prev[activeTabId] ?? []), userMessage],
      }));
      setTabTyping((prev) => ({ ...prev, [activeTabId]: true }));

      try {
        // Chama o backend Python via bridge (ou mock em dev)
        const response = await bridge.sendMessage(text, attachment?.name);

        const assistantMessage: MessageData = {
          id: `msg-${generateId()}`,
          role: 'assistant',
          content: response,
          timestamp: new Date(),
        };
        setTabMessages((prev) => ({
          ...prev,
          [activeTabId]: [...(prev[activeTabId] ?? []), assistantMessage],
        }));
      } catch (error) {
        // Exibe erro como mensagem do assistente para não travar a UI
        const errorMessage: MessageData = {
          id: `msg-${generateId()}`,
          role: 'assistant',
          content: 'Ocorreu um erro ao processar sua mensagem. Tente novamente.',
          timestamp: new Date(),
        };
        setTabMessages((prev) => ({
          ...prev,
          [activeTabId]: [...(prev[activeTabId] ?? []), errorMessage],
        }));
        console.error('[App] Erro ao chamar bridge.sendMessage:', error);
      } finally {
        setTabTyping((prev) => ({ ...prev, [activeTabId]: false }));
      }
    },
    [activeTabId]
  );

  // Determina a aba ativa para renderizar a view correta
  const activeTab = tabs.find((t) => t.id === activeTabId) ?? null;
  const hasMessages = activeMessages.length > 0;

  return (
    <VaultProvider>
      {/* Layout raiz: sidebar à esquerda + coluna de conteúdo à direita */}
      <div className="app" id="app-root">
        {/* Barra lateral esquerda */}
        <Sidebar
          onOpenSettings={() => setIsSettingsOpen(true)}
          onNewTab={handleNewTab}
          onOpenNotes={() => setWorkspaceView('notes')}
          onOpenBenchmark={() => setWorkspaceView('benchmark')}
          activeView={workspaceView}
        />

        {/* Coluna de conteúdo principal (tab bar + view) */}
        <div className="app__content">
          {/* Barra de abas */}
          <Header
            tabs={tabs}
            activeTabId={activeTabId}
            onSelectTab={handleSelectTab}
            onCloseTab={handleCloseTab}
            isSettingsOpen={isSettingsOpen}
            onCloseSettings={() => setIsSettingsOpen(false)}
            isGraphPanelOpen={isGraphPanelOpen}
            onToggleGraphPanel={handleToggleGraphPanel}
          />

          {/* View ativa conforme a aba selecionada */}
          {workspaceView === 'notes' && <NotesPanel />}

          {workspaceView === 'benchmark' && <BenchmarkPanel />}

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
                    <MessageBubble key={message.id} message={message} />
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
            <ChatInput onSendMessage={handleSendMessage} isLoading={isTyping} />
          )}
        </div>

        {/* Painel lateral de grafos — expande à direita do conteúdo */}
        <GraphPanel isOpen={isGraphPanelOpen} onToggle={handleToggleGraphPanel} />
      </div>
    </VaultProvider>
  );
}

export default App;
