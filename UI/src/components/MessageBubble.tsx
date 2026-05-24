import { SparkleIcon, UserIcon } from './Icons';

// Tipos de mensagem
export type MessageRole = 'user' | 'assistant';

export interface MessageData {
  id: string;
  role: MessageRole;
  content: string;
  timestamp: Date;
}

// Props do componente de bolha de mensagem
interface MessageBubbleProps {
  message: MessageData;
}

// Componente de indicador de digitação da IA
export const TypingIndicator = () => (
  <div className="message message--ai fade-in" role="status" aria-label="Assistente está digitando">
    <div className="message__avatar message__avatar--ai" aria-hidden="true">
      <SparkleIcon size={16} />
    </div>
    <div className="message__bubble message__bubble--ai">
      <div className="typing-indicator">
        <span className="typing-indicator__dot" />
        <span className="typing-indicator__dot" />
        <span className="typing-indicator__dot" />
      </div>
    </div>
  </div>
);

// Componente de bolha de mensagem individual
const MessageBubble = ({ message }: MessageBubbleProps) => {
  const isUser = message.role === 'user';

  return (
    <article
      className={`message ${isUser ? 'message--user' : ''} fade-in`}
      aria-label={`Mensagem de ${isUser ? 'você' : 'Assistente IA'}`}
    >
      {/* Avatar */}
      <div
        className={`message__avatar ${isUser ? 'message__avatar--user' : 'message__avatar--ai'}`}
        aria-hidden="true"
      >
        {isUser ? <UserIcon size={16} /> : <SparkleIcon size={16} />}
      </div>

      {/* Conteúdo da mensagem */}
      <div
        className={`message__bubble ${isUser ? 'message__bubble--user' : 'message__bubble--ai'}`}
      >
        {message.content}
      </div>
    </article>
  );
};

export default MessageBubble;
