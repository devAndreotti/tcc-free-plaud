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

// Conversas: abas (cada uma presa a uma vault), aba ativa e mensagens/digitação por aba.
interface ChatState {
  tabs: Tab[];
  activeTabId: string | null;
  tabMessages: Record<string, MessageData[]>;
  tabTyping: Record<string, boolean>;
}

const newChatTab = (vaultId: string): Tab => ({ id: generateId(), label: 'Nova Conversa', type: 'chat', vaultId });

// Abertura: uma "Nova Conversa" vazia, sem vault até a lista de vaults chegar.
const newChatState = (): ChatState => {
  const tab = newChatTab('');
  return { tabs: [tab], activeTabId: tab.id, tabMessages: { [tab.id]: [] }, tabTyping: {} };
};

const withoutKey = <T,>(record: Record<string, T>, key: string): Record<string, T> => {
  const next = { ...record };
  delete next[key];
  return next;
};

// Ajusta as conversas quando a vault ativa ou a lista de vaults muda (sidebar, criar, excluir, abertura):
// abas sem vault ganham a ativa, abas de vault excluída fecham, e a aba à vista passa a ser da vault ativa:
// a última aba dela (uma "Nova Conversa" vazia deixada para trás fecha, para não acumular abas ao alternar);
// sem aba na vault ativa, a vazia muda de vault junto e a com conversa dá lugar a uma nova.
const syncWithVaults = (chat: ChatState, vaultKey: string, vaultIds: string[]): ChatState => {
  if (!vaultKey) return chat;
  const gone = new Set(chat.tabs.filter((tab) => tab.vaultId && !vaultIds.includes(tab.vaultId)).map((tab) => tab.id));
  let { tabMessages, tabTyping } = chat;
  for (const id of gone) {
    tabMessages = withoutKey(tabMessages, id);
    tabTyping = withoutKey(tabTyping, id);
  }
  const tabs = chat.tabs.filter((tab) => !gone.has(tab.id)).map((tab) => (tab.vaultId ? tab : { ...tab, vaultId: vaultKey }));
  const next = { ...chat, tabs, tabMessages, tabTyping };
  const current = tabs.find((tab) => tab.id === chat.activeTabId);
  if (current?.vaultId === vaultKey) return next;
  const currentEmpty = current !== undefined && !tabMessages[current.id]?.length;
  const last = tabs.findLast((tab) => tab.vaultId === vaultKey);
  if (last) {
    if (!currentEmpty || current.label !== 'Nova Conversa') return { ...next, activeTabId: last.id };
    return { ...next, tabs: tabs.filter((tab) => tab.id !== current.id), tabMessages: withoutKey(tabMessages, current.id), activeTabId: last.id };
  }
  if (currentEmpty) {
    return { ...next, tabs: tabs.map((tab) => (tab.id === current.id ? { ...tab, vaultId: vaultKey } : tab)) };
  }
  const tab = newChatTab(vaultKey);
  return { ...next, tabs: [...tabs, tab], activeTabId: tab.id, tabMessages: { ...tabMessages, [tab.id]: [] } };
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
  // Conversas em memória; cada aba é de uma vault e mostra o ícone e a cor dela.
  const { vaults, active: activeVault, version: vaultVersion, select: selectVault } = useVaults();
  const vaultKey = activeVault ? activeVault.id : '';
  const vaultIds = vaults.map((vault) => vault.id);
  const vaultsKey = `${vaultKey}|${vaultIds.join('|')}`;
  const [chat, setChat] = useState<ChatState>(newChatState);
  // Ajustado na renderização (não em efeito): o chat nunca pisca vazio, então o campo de mensagem não remonta nem perde o texto.
  const [syncedVaultsKey, setSyncedVaultsKey] = useState(vaultsKey);
  if (syncedVaultsKey !== vaultsKey) {
    setSyncedVaultsKey(vaultsKey);
    setChat(syncWithVaults(chat, vaultKey, vaultIds));
  }
  // Atualiza a conversa de uma aba; aba já fechada é ignorada (a resposta tardia não a recria).
  const updateTab = useCallback((tabId: string, update: (chat: ChatState) => ChatState) => {
    setChat((prev) => (prev.tabs.some((tab) => tab.id === tabId) ? update(prev) : prev));
  }, [setChat]);
  const { tabs, activeTabId, tabMessages, tabTyping } = chat;
  const activeTab = tabs.find((t) => t.id === activeTabId) ?? null;

  // Aba de outra vault à vista (clique, ou vizinha ao fechar uma aba): ativa a vault da conversa.
  // Até a troca terminar, o envio fica bloqueado, para a pergunta não ir ao corpus errado.
  const activeTabVault = activeTab?.vaultId ?? '';
  const switchingVault = activeTabVault !== '' && activeTabVault !== vaultKey;
  useEffect(() => {
    if (!switchingVault) return;
    void selectVault(activeTabVault).then((result) => {
      if (!result.ok) console.error('[App] Não foi possível ativar a vault da conversa:', result.message);
    });
  }, [switchingVault, activeTabVault, selectVault]);

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

  // Seleciona uma aba pelo id (a vault dela vira a ativa)
  const handleSelectTab = useCallback((id: string) => {
    setChat((c) => ({ ...c, activeTabId: id }));
    setWorkspaceView('chat');
  }, [setChat]);

  const handleRenameTab = useCallback((id: string, label: string) => {
    setChat((c) => ({ ...c, tabs: c.tabs.map((tab) => (tab.id === id ? { ...tab, label } : tab)) }));
  }, [setChat]);

  // Fecha uma aba; limpa seu estado e ativa a vizinha
  const handleCloseTab = useCallback(
    (id: string) => {
      setChat((c) => {
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
    [setChat]
  );

  // Abre nova aba de chat na vault ativa e a torna ativa
  const handleNewTab = useCallback(() => {
    const newTab = newChatTab(vaultKey);
    setChat((c) => ({
      ...c,
      tabs: [...c.tabs, newTab],
      tabMessages: { ...c.tabMessages, [newTab.id]: [] },
      activeTabId: newTab.id,
    }));
    setWorkspaceView('chat');
  }, [vaultKey, setChat]);

  // Anexa à conversa da aba (na vault dela, mesmo depois de trocar de vault)
  const appendMessage = useCallback((tabId: string, message: MessageData) => {
    updateTab(tabId, (c) => ({ ...c, tabMessages: { ...c.tabMessages, [tabId]: [...(c.tabMessages[tabId] ?? []), message] } }));
  }, [updateTab]);

  // Pergunta ao corpus e anexa a resposta (estruturada, quando o backend a devolve)
  const askInTab = useCallback(
    async (tabId: string, text: string, askStrategy: AskStrategy, askSourceRoot: string | null) => {
      updateTab(tabId, (c) => ({ ...c, tabTyping: { ...c.tabTyping, [tabId]: true } }));
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
        updateTab(tabId, (c) => ({ ...c, tabTyping: { ...c.tabTyping, [tabId]: false } }));
      }
    },
    [appendMessage, updateTab]
  );

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
      updateTab(tabId, (c) => ({
        ...c,
        tabs: c.tabs.map((tab) => (tab.id === tabId && tab.label === 'Nova Conversa' && title ? { ...tab, label } : tab)),
      }));
      await askInTab(tabId, text, strategy, activeSourceRoot);
    },
    [activeTabId, appendMessage, updateTab, askInTab, strategy, activeSourceRoot]
  );

  const handleRetry = useCallback(
    (query: string, retryStrategy: AskStrategy) => {
      if (activeTabId) void askInTab(activeTabId, query, retryStrategy, activeSourceRoot);
    },
    [activeTabId, askInTab, activeSourceRoot]
  );

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
              onRenameTab={handleRenameTab}
              vaults={vaults}
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
                  <WelcomeScreen vault={activeVault} onOpenQueue={() => navigate('queue')} />
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
                isLoading={isTyping || switchingVault}
                strategy={strategy}
                onStrategyChange={setStrategy}
                corpusRoots={corpusRoots}
                sourceRoot={activeSourceRoot}
                onSourceRootChange={chooseSourceRoot}
                vault={activeVault}
                vaults={vaults}
                onVaultChange={(vaultId) => void selectVault(vaultId)}
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
