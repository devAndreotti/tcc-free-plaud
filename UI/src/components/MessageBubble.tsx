import { SparkleIcon, UserIcon } from './Icons';

export type MessageRole = 'user' | 'assistant';

export interface MessageData {
  id: string;
  role: MessageRole;
  content: string;
  timestamp: Date;
}

interface MessageBubbleProps {
  message: MessageData;
}

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

function renderFormattedContent(text: string) {
  const lines = text.split('\n');
  return lines.map((line, idx) => {
    if (line.startsWith('- ') || line.startsWith('* ')) {
      return (
        <div key={idx} className="pl-3 my-0.5 flex items-start gap-1.5">
          <span className="text-slate-400 select-none">•</span>
          <span>{line.substring(2)}</span>
        </div>
      );
    }
    if (line.startsWith('### ')) {
      return <div key={idx} className="font-bold text-slate-200 mt-2 mb-1">{line.substring(4)}</div>;
    }
    if (line.startsWith('## ')) {
      return <div key={idx} className="font-bold text-slate-100 mt-2.5 mb-1 text-base">{line.substring(3)}</div>;
    }
    if (line.startsWith('# ')) {
      return <div key={idx} className="font-extrabold text-slate-50 mt-3 mb-1.5 text-lg">{line.substring(2)}</div>;
    }
    if (!line.trim()) {
      return <div key={idx} className="h-2" />;
    }
    return <div key={idx} className="min-h-[1.25rem]">{line}</div>;
  });
}

const MessageBubble = ({ message }: MessageBubbleProps) => {
  const isUser = message.role === 'user';

  return (
    <article
      className={`message ${isUser ? 'message--user' : ''} fade-in`}
      aria-label={`Mensagem de ${isUser ? 'você' : 'Assistente IA'}`}
    >
      <div
        className={`message__avatar ${isUser ? 'message__avatar--user' : 'message__avatar--ai'}`}
        aria-hidden="true"
      >
        {isUser ? <UserIcon size={16} /> : <SparkleIcon size={16} />}
      </div>

      <div
        className={`message__bubble ${isUser ? 'message__bubble--user' : 'message__bubble--ai'}`}
      >
        {isUser ? message.content : renderFormattedContent(message.content)}
      </div>
    </article>
  );
};

export default MessageBubble;
