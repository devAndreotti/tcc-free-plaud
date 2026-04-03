import { useEffect, useRef } from 'react';
import { createPortal } from 'react-dom';
import { XIcon } from './Icons';

// Props do modal de configurações
interface SettingsModalProps {
  isOpen: boolean;
  onClose: () => void;
}

const SettingsModal = ({ isOpen, onClose }: SettingsModalProps) => {
  const modalRef = useRef<HTMLDivElement>(null);

  // Fecha o modal ao pressionar Escape
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    if (isOpen) document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, onClose]);

  // Foca o modal quando abre (acessibilidade)
  useEffect(() => {
    if (isOpen) modalRef.current?.focus();
  }, [isOpen]);

  if (!isOpen) return null;

  // Renderiza diretamente no document.body via Portal.
  // O overlay usa display:flex para centralizar o modal de forma confiável,
  // sem depender de position:fixed + transform no próprio modal.
  return createPortal(
    // Overlay como contêiner flex que centraliza o modal
    <div
      className="modal-overlay"
      onClick={onClose}
      aria-hidden="true"
    >
      {/* Janela do modal — filho direto do overlay flex */}
      <div
        ref={modalRef}
        className="modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="settings-title"
        tabIndex={-1}
        onClick={(e) => e.stopPropagation()} // Impede que clique no modal feche o overlay
      >
        {/* Cabeçalho do modal */}
        <div className="modal__header">
          <h2 id="settings-title" className="modal__title">Configurações</h2>
          <button
            id="btn-close-settings"
            type="button"
            className="modal__close"
            aria-label="Fechar configurações"
            onClick={onClose}
          >
            <XIcon size={16} />
          </button>
        </div>

        {/* Corpo do modal */}
        <div className="modal__body">
          {/* Seção: Aparência */}
          <section className="settings-section" aria-labelledby="settings-appearance">
            <h3 id="settings-appearance" className="settings-section__title">
              Aparência
            </h3>

            <div className="settings-item">
              <div className="settings-item__info">
                <span className="settings-item__label">Tema</span>
                <span className="settings-item__description">
                  Aparência visual do aplicativo
                </span>
              </div>
              <div className="settings-item__control">
                <select
                  id="select-theme"
                  className="settings-select"
                  defaultValue="dark"
                  aria-label="Selecionar tema"
                >
                  <option value="dark">Escuro</option>
                  <option value="light" disabled>Claro (em breve)</option>
                </select>
              </div>
            </div>
          </section>

          <div className="settings-divider" aria-hidden="true" />

          {/* Seção: Sobre */}
          <section className="settings-section" aria-labelledby="settings-about">
            <h3 id="settings-about" className="settings-section__title">
              Sobre
            </h3>

            <div className="settings-item">
              <div className="settings-item__info">
                <span className="settings-item__label">Assistente IA</span>
                <span className="settings-item__description">
                  Interface de chat com inteligência artificial
                </span>
              </div>
              <span className="settings-badge">v0.1.0</span>
            </div>
          </section>
        </div>

        {/* Rodapé do modal */}
        <div className="modal__footer">
          <button
            id="btn-settings-close"
            type="button"
            className="btn-modal-primary"
            onClick={onClose}
          >
            Fechar
          </button>
        </div>
      </div>
    </div>,
    document.body
  );
};

export default SettingsModal;
