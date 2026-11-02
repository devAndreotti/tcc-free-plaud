import { useEffect } from 'react';
import { CheckCircleIcon, XCircleIcon, XIcon } from './Icons';

interface AppToastProps {
  message: string;
  tone: 'ok' | 'erro';
  /** Ação opcional (ex.: "Desfazer"), mostrada ao lado da mensagem. */
  actionLabel?: string;
  onAction?: () => void;
  onDismiss: () => void;
  /** Tempo até sumir sozinho, em ms. */
  durationMs: number;
  /** Sobe o aviso para ficar acima de outro aviso no rodapé. */
  raised?: boolean;
}

/** Aviso de rodapé com ação opcional. Some sozinho após `durationMs`; reinicia quando o aviso muda. */
const AppToast = ({ message, tone, actionLabel, onAction, onDismiss, durationMs, raised = false }: AppToastProps) => {
  useEffect(() => {
    const timer = window.setTimeout(onDismiss, durationMs);
    return () => window.clearTimeout(timer);
  }, [onDismiss, durationMs]);

  return (
    <div className={`app-toast${raised ? ' app-toast--raised' : ''}`} role="status" aria-live="polite">
      {tone === 'ok' ? <CheckCircleIcon size={15} /> : <XCircleIcon size={15} />}
      <span className="app-toast__message">{message}</span>
      {actionLabel && onAction && (
        <button type="button" className="app-toast__action" onClick={onAction}>
          {actionLabel}
        </button>
      )}
      <button type="button" className="btn-icon app-toast__close" onClick={onDismiss} aria-label="Fechar aviso">
        <XIcon size={12} />
      </button>
    </div>
  );
};

export default AppToast;
