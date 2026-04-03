import { useState, useRef, useEffect, useCallback } from 'react';
import './App.css';

import Header from './components/Header';
import WelcomeScreen from './components/WelcomeScreen';
import MessageBubble, {
  TypingIndicator,
  type MessageData,
} from './components/MessageBubble';
import ChatInput from './components/ChatInput';
import { bridge } from './services/bridge';

// Gera ID único para cada mensagem
const generateId = () =>
  `msg-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;

function App() {
  const [messages, setMessages] = useState<MessageData[]>([]);
  const [isTyping, setIsTyping] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Mantém o scroll sempre no final da lista de mensagens
  const scrollToBottom = useCallback(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [messages, isTyping, scrollToBottom]);

  // Envia mensagem ao backend Python (ou mock em dev) via bridge
  const handleSendMessage = useCallback(
    async (text: string, attachment?: File) => {
      if (!text.trim() && !attachment) return;

      // Adiciona mensagem do usuário na tela imediatamente
      const userMessage: MessageData = {
        id: generateId(),
        role: 'user',
        content: text || `[Arquivo: ${attachment?.name}]`,
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, userMessage]);
      setIsTyping(true);

      try {
        // Chama o backend Python via bridge (ou mock em dev)
        const response = await bridge.sendMessage(
          text,
          attachment?.name
        );

        const assistantMessage: MessageData = {
          id: generateId(),
          role: 'assistant',
          content: response,
          timestamp: new Date(),
        };
        setMessages((prev) => [...prev, assistantMessage]);
      } catch (error) {
        // Exibe erro como mensagem do assistente para não travar a UI
        const errorMessage: MessageData = {
          id: generateId(),
          role: 'assistant',
          content: 'Ocorreu um erro ao processar sua mensagem. Tente novamente.',
          timestamp: new Date(),
        };
        setMessages((prev) => [...prev, errorMessage]);
        console.error('[App] Erro ao chamar bridge.sendMessage:', error);
      } finally {
        setIsTyping(false);
      }
    },
    []
  );

  const hasMessages = messages.length > 0;

  return (
    <div className="app" id="app-root">
      {/* Cabeçalho superior */}
      <Header />

      {/* Conteúdo principal */}
      <main className="main" id="main-content">
        {/* Lista de mensagens ou tela de boas-vindas */}
        {hasMessages ? (
          <div
            className="messages-area"
            role="log"
            aria-label="Histórico de mensagens"
            aria-live="polite"
          >
            {messages.map((message) => (
              <MessageBubble key={message.id} message={message} />
            ))}

            {/* Indicador de digitação enquanto aguarda o backend */}
            {isTyping && <TypingIndicator />}

            {/* Âncora de scroll para o final */}
            <div ref={messagesEndRef} aria-hidden="true" />
          </div>
        ) : (
          <WelcomeScreen />
        )}
      </main>

      {/* Input de mensagem */}
      <ChatInput onSendMessage={handleSendMessage} isLoading={isTyping} />
    </div>
  );
}

export default App;
