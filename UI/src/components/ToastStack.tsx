import { useEffect } from 'react';
import type { DropzoneToast } from './Dropzone';
import { CheckCircleIcon, XCircleIcon, XIcon } from './Icons';

const AUTO_DISMISS_MS = 4000;

interface ToastStackProps {
  toasts: DropzoneToast[];
  onDismiss: (id: string) => void;
}

/** Pilha de notificações toast exibidas quando o watcher indexa novos documentos. */
const ToastStack = ({ toasts, onDismiss }: ToastStackProps) => {
  useEffect(() => {
    if (toasts.length === 0) return undefined;
    const timers = toasts.map((toast) =>
      window.setTimeout(() => onDismiss(toast.id), AUTO_DISMISS_MS)
    );
    return () => timers.forEach((timer) => window.clearTimeout(timer));
  }, [toasts, onDismiss]);

  if (toasts.length === 0) return null;

  return (
    <div className="toast-stack" role="status" aria-live="polite">
      {toasts.map((toast) => (
        <div key={toast.id} className={`toast toast--${toast.status}`}>
          {toast.status === 'success' ? <CheckCircleIcon size={15} /> : <XCircleIcon size={15} />}
          <span className="toast__message">{toast.message}</span>
          <button
            type="button"
            className="btn-icon toast__close"
            onClick={() => onDismiss(toast.id)}
            aria-label="Fechar notificação"
          >
            <XIcon size={12} />
          </button>
        </div>
      ))}
    </div>
  );
};

export default ToastStack;
