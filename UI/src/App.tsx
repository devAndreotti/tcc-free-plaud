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
import { bridge, type AskStrategy, type CorpusRoot } from './services/bridge';
import { VaultsProvider } from './contexts/VaultsContext';
import { useVaults } from './hooks/useVaults';
import { QueueProvider } from './contexts/QueueContext';

// Gera ID único para mensagens e abas
const generateId = () =>
  `${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;

// Estado do chat de uma vault: abas, aba ativa e mensagens/digitação por aba.
interface ChatState {
  tabs: Tab[];
  activeTabId: string | null;
  tabMessages: Record<string, MessageData[]>;
  tabTyping: Record<string, boolean>;
}

// Conversa nova: uma aba "Nova Conversa" vazia.
const newChatState = (): ChatState => {
  const tab: Tab = { id: generateId(), label: 'Nova Conversa', type: 'chat' };
  return { tabs: [tab], activeTabId: tab.id, tabMessages: { [tab.id]: [] }, tabTyping: {} };
};

const EMPTY_CHAT: ChatState = { tabs: [], activeTabId: null, tabMessages: {}, tabTyping: {} };

const withoutKey = <T,>(record: Record<string, T>, key: string): Record<string, T> => {
  const next = { ...record };
  delete next[key];
  return next;
};

// Estado de conversa vazia para reutilização
const EMPTY_MESSAGES: MessageData[] = [];

// Última pasta escolhida no seletor de pasta do chat (null = todas).
const SOURCE_ROOT_STORAGE_KEY = 'escolio:chat:sourceRoot';

const readStoredSourceRoot = (): string | null => {
  try {
    return window.localStorage.getItem(SOURCE_ROOT_STORAGE_KEY);
  } catch {
    return null; // armazenamento indisponível: a escolha vale só nesta sessão
  }
};

function AppContent() {
  // Conversas por vault, em memória: cada vault tem suas abas e mensagens.
  const { active: activeVault, version: vaultVersion } = useVaults();
  const vaultKey = activeVault ? activeVault.id : '';
  const [chats, setChats] = useState<Record<string, ChatState>>(() => ({ '': newChatState() }));
  // Vault sem conversa ganha uma "Nova Conversa"; a aberta antes da lista de vaults chegar ('') fica com a primeira vault.
  // Ajustado na renderização (não em efeito): o chat nunca pisca vazio, então o campo de mensagem não remonta nem perde o texto.
  if (!chats[vaultKey]) {
    const adopted = vaultKey && chats[''] ? chats[''] : newChatState();
    setChats({ ...withoutKey(chats, ''), [vaultKey]: adopted });
  }
  const updateChat = useCallback((key: string, update: (chat: ChatState) => ChatState) => {
    setChats((prev) => (prev[key] ? { ...prev, [key]: update(prev[key]) } : prev));
  }, []);
  // Atualiza a conversa que contém a aba: a resposta cai na vault do envio, mesmo depois de trocar de vault.
  const updateTabChat = useCallback((tabId: string, update: (chat: ChatState) => ChatState) => {
    setChats((prev) => {
      const key = Object.keys(prev).find((k) => prev[k].tabs.some((tab) => tab.id === tabId));
      return key === undefined ? prev : { ...prev, [key]: update(prev[key]) };
    });
  }, []);
  const chat = chats[vaultKey] ?? EMPTY_CHAT;
  const { tabs, activeTabId, tabMessages, tabTyping } = chat;

  const [isSettingsOpen, setIsSettingsOpen] = useState(false);
  const [settingsTab, setSettingsTab] = useState<SettingsTab | undefined>(undefined);
  const [healthKey, setHealthKey] = useState(0);
  const [isGraphPanelOpen, setIsGraphPanelOpen] = useState(false);
  // Nota pedida pelo grafo; a tela Notas a abre ao montar. `at` muda a cada clique, então clicar de novo na mesma nota reabre.
  // Navegar pela sidebar limpa o pedido.
  const [pendingNote, setPendingNote] = useState<{ noteId: string; at: number } | null>(null);
  const [workspaceView, setWorkspaceView] = useState<WorkspaceView>('chat');
  const [strategy, setStrategy] = useState<AskStrategy>('hybrid');
  const [sourceRoot, setSourceRoot] = useState<string | null>(readStoredSourceRoot);
  const [corpusRoots, setCorpusRoots] = useState<CorpusRoot[]>([]);

  // Recarrega as pastas ao trocar de tela: uma indexação feita na Fila aparece no seletor ao voltar ao chat.
  useEffect(() => {
    let active = true;
    bridge
      .listCorpusRoots()
      .then((roots) => {
        if (active) setCorpusRoots(roots);
      })
      .catch(() => {
        if (active) setCorpusRoots([]);
      });
    return () => {
      active = false;
    };
  }, [workspaceView, vaultVersion]);

  const chooseSourceRoot = useCallback((root: string | null) => {
    setSourceRoot(root);
    try {
      if (root) window.localStorage.setItem(SOURCE_ROOT_STORAGE_KEY, root);
      else window.localStorage.removeItem(SOURCE_ROOT_STORAGE_KEY);
    } catch {
      // sem persistência: a escolha continua valendo nesta sessão
    }
  }, []);

  // Só vale com seletor visível (duas ou mais pastas) e se a pasta ainda estiver indexada.
  const activeSourceRoot =
    corpusRoots.length >= 2 && sourceRoot && corpusRoots.some((root) => root.root === sourceRoot) ? sourceRoot : null;

  const openSettings = useCallback((tab?: SettingsTab) => {
    setSettingsTab(tab);
    setIsSettingsOpen(true);
  }, []);

  const closeSettings = useCallback(() => {
    setIsSettingsOpen(false);
    setHealthKey((prev) => prev + 1);
  }, []);

  const navigate = useCallback((view: WorkspaceView) => {
    setPendingNote(null);
    setWorkspaceView(view);
  }, []);

  // Clique numa nota do grafo: vai para Notas e abre o detalhe dela
  const handleOpenNote = useCallback((noteId: string) => {
    setPendingNote((prev) => ({ noteId, at: (prev?.at ?? 0) + 1 }));
    setWorkspaceView('notes');
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
    updateChat(vaultKey, (c) => ({ ...c, activeTabId: id }));
    setWorkspaceView('chat');
  }, [updateChat, vaultKey]);

  // Fecha uma aba; limpa seu estado e ativa a vizinha
  const handleCloseTab = useCallback(
    (id: string) => {
      updateChat(vaultKey, (c) => {
        const tabMessages = withoutKey(c.tabMessages, id);
        const tabTyping = withoutKey(c.tabTyping, id);
        if (c.tabs.length === 1) return { ...c, tabs: [], activeTabId: null, tabMessages, tabTyping };
        const idx = c.tabs.findIndex((t) => t.id === id);
        const next = c.tabs.filter((t) => t.id !== id);
        // Se a aba fechada era a ativa, ativa a vizinha
        const newActive = id === c.activeTabId ? (next[Math.max(0, idx - 1)]?.id ?? null) : c.activeTabId;
        return { ...c, tabs: next, activeTabId: newActive, tabMessages, tabTyping };
      });
    },
    [updateChat, vaultKey]
  );

  // Abre nova aba de chat com conversa própria e a torna ativa
  const handleNewTab = useCallback(() => {
    const newTab: Tab = { id: generateId(), label: 'Nova Conversa', type: 'chat' };
    updateChat(vaultKey, (c) => ({
      ...c,
      tabs: [...c.tabs, newTab],
      tabMessages: { ...c.tabMessages, [newTab.id]: [] },
      activeTabId: newTab.id,
    }));
    setWorkspaceView('chat');
  }, [updateChat, vaultKey]);

  // Anexa à conversa da aba (na vault em que ela foi aberta)
  const appendMessage = useCallback((tabId: string, message: MessageData) => {
    updateTabChat(tabId, (c) => ({ ...c, tabMessages: { ...c.tabMessages, [tabId]: [...(c.tabMessages[tabId] ?? []), message] } }));
  }, [updateTabChat]);

  // Pergunta ao corpus e anexa a resposta (estruturada, quando o backend a devolve)
  const askInTab = useCallback(
    async (tabId: string, text: string, askStrategy: AskStrategy, askSourceRoot: string | null) => {
      updateTabChat(tabId, (c) => ({ ...c, tabTyping: { ...c.tabTyping, [tabId]: true } }));
      try {
        const ask = await bridge.askCorpus(text, askStrategy, askSourceRoot);
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
        updateTabChat(tabId, (c) => ({ ...c, tabTyping: { ...c.tabTyping, [tabId]: false } }));
      }
    },
    [appendMessage, updateTabChat]
  );

  /* eslint-disable react-hooks/preserve-manual-memoization -- o React Compiler não preserva este memo com o estado por vault; as deps estão completas. */
  // Envia mensagem na conversa da aba ativa
  const handleSendMessage = useCallback(
    async (text: string, attachment?: File) => {
      if (!activeTabId) return;
      if (!text.trim() && !attachment) return;
      const tabId = activeTabId;
      const title = text.trim();

      appendMessage(tabId, {
        id: `msg-${generateId()}`,
        role: 'user',
        content: text || `[Arquivo: ${attachment?.name}]`,
        timestamp: new Date(),
      });
      // O nome da primeira pergunta vira o título da aba
      const label = title.length > 32 ? `${title.slice(0, 32)}…` : title;
      updateTabChat(tabId, (c) => ({
        ...c,
        tabs: c.tabs.map((tab) => (tab.id === tabId && tab.label === 'Nova Conversa' && title ? { ...tab, label } : tab)),
      }));
      await askInTab(tabId, text, strategy, activeSourceRoot);
    },
    [activeTabId, appendMessage, updateTabChat, askInTab, strategy, activeSourceRoot]
  );

  const handleRetry = useCallback(
    (query: string, retryStrategy: AskStrategy) => {
      if (activeTabId) void askInTab(activeTabId, query, retryStrategy, activeSourceRoot);
    },
    [activeTabId, askInTab, activeSourceRoot]
  );
  /* eslint-enable react-hooks/preserve-manual-memoization */

  // Determina a aba ativa para renderizar a view correta
  const activeTab = tabs.find((t) => t.id === activeTabId) ?? null;
  const hasMessages = activeMessages.length > 0;

  return (
    <>
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
            {workspaceView === 'notes' && <NotesPanel key={pendingNote ? `nota-${pendingNote.at}` : `lista-${vaultVersion}`} initialNoteId={pendingNote?.noteId ?? null} />}

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
                corpusRoots={corpusRoots}
                sourceRoot={activeSourceRoot}
                onSourceRootChange={chooseSourceRoot}
              />
            )}
          </div>

          {/* Painel lateral de grafos — expande à direita do conteúdo */}
          <GraphPanel isOpen={isGraphPanelOpen} onToggle={handleToggleGraphPanel} onOpenNote={handleOpenNote} />
        </div>
      </QueueProvider>
    </>
  );
}

function App() {
  return (
    <VaultsProvider>
      <AppContent />
    </VaultsProvider>
  );
}

export default App;
