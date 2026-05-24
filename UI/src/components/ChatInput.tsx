import {
  useRef,
  useState,
  useCallback,
  type KeyboardEvent,
  type ChangeEvent,
} from 'react';
import { PaperclipIcon, MicIcon, SendIcon, FileIcon, XIcon } from './Icons';

// Props do componente de input de chat
interface ChatInputProps {
  onSendMessage: (text: string, attachment?: File) => void;
  isLoading?: boolean;
}

const ChatInput = ({ onSendMessage, isLoading = false }: ChatInputProps) => {
  const [text, setText] = useState('');
  const [attachment, setAttachment] = useState<File | null>(null);
  const [isMicActive, setIsMicActive] = useState(false);

  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Ajusta a altura do textarea automaticamente conforme o conteúdo cresce
  const adjustTextareaHeight = useCallback(() => {
    const textarea = textareaRef.current;
    if (!textarea) return;
    textarea.style.height = 'auto';
    textarea.style.height = `${Math.min(textarea.scrollHeight, 200)}px`;
  }, []);

  // Atualiza texto e ajusta altura
  const handleTextChange = (e: ChangeEvent<HTMLTextAreaElement>) => {
    setText(e.target.value);
    adjustTextareaHeight();
  };

  // Envia mensagem ao pressionar Enter (sem Shift)
  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  // Lógica de envio da mensagem
  const handleSend = useCallback(() => {
    const trimmed = text.trim();
    if (!trimmed && !attachment) return;
    if (isLoading) return;

    onSendMessage(trimmed, attachment ?? undefined);
    setText('');
    setAttachment(null);

    // Reseta altura do textarea
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
    }
  }, [text, attachment, isLoading, onSendMessage]);

  // Abre diálogo de seleção de arquivo
  const handleAttachClick = () => {
    fileInputRef.current?.click();
  };

  // Armazena arquivo selecionado
  const handleFileChange = (e: ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) setAttachment(file);
    // Limpa o input para permitir selecionar o mesmo arquivo novamente
    e.target.value = '';
  };

  // Remove o arquivo anexado
  const handleRemoveAttachment = () => {
    setAttachment(null);
  };

  // Alterna estado do microfone (simulado)
  const handleMicToggle = () => {
    setIsMicActive((prev) => !prev);
  };

  const canSend = (text.trim().length > 0 || attachment !== null) && !isLoading;

  return (
    <section className="input-area" aria-label="Área de entrada de mensagem">
      <div className="input-container" role="form" aria-label="Formulário de chat">
        {/* Input oculto para seleção de arquivo */}
        <input
          ref={fileInputRef}
          id="file-input"
          type="file"
          aria-label="Selecionar arquivo para anexar"
          style={{ display: 'none' }}
          onChange={handleFileChange}
          accept="*/*"
        />

        {/* Botão de anexar */}
        <button
          id="btn-attach"
          type="button"
          className="btn-attach"
          aria-label="Anexar arquivo"
          title="Anexar arquivo"
          onClick={handleAttachClick}
          disabled={isLoading}
        >
          <PaperclipIcon size={18} />
        </button>

        {/* Área de composição */}
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: '6px' }}>
          {/* Preview do arquivo anexado */}
          {attachment && (
            <div className="attachment-preview" aria-label={`Arquivo anexado: ${attachment.name}`}>
              <div className="attachment-preview__icon" aria-hidden="true">
                <FileIcon size={14} />
              </div>
              <span className="attachment-preview__name" title={attachment.name}>
                {attachment.name}
              </span>
              <button
                type="button"
                className="attachment-preview__remove"
                aria-label="Remover arquivo anexado"
                onClick={handleRemoveAttachment}
              >
                <XIcon size={12} />
              </button>
            </div>
          )}

          {/* Campo de texto */}
          <textarea
            ref={textareaRef}
            id="chat-textarea"
            className="chat-input"
            placeholder="Digite sua mensagem..."
            value={text}
            onChange={handleTextChange}
            onKeyDown={handleKeyDown}
            rows={1}
            aria-label="Campo de mensagem"
            aria-multiline="true"
            disabled={isLoading}
          />
        </div>

        {/* Ações: microfone e enviar */}
        <div className="input-actions">
          <button
            id="btn-mic"
            type="button"
            className={`btn-mic ${isMicActive ? 'active' : ''}`}
            aria-label={isMicActive ? 'Desativar microfone' : 'Ativar microfone'}
            title={isMicActive ? 'Desativar microfone' : 'Ativar microfone'}
            onClick={handleMicToggle}
            aria-pressed={isMicActive}
          >
            <MicIcon size={18} />
          </button>

          <button
            id="btn-send"
            type="button"
            className="btn-send"
            aria-label="Enviar mensagem"
            title="Enviar mensagem (Enter)"
            onClick={handleSend}
            disabled={!canSend}
          >
            <SendIcon size={16} />
          </button>
        </div>
      </div>

      {/* Aviso de rodapé */}
      <p className="input-footer" aria-live="polite">
        O Assistente IA pode cometer erros. Verifique informações importantes.
      </p>
    </section>
  );
};

export default ChatInput;
