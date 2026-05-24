import { useEffect, useRef } from 'react';
import { createPortal } from 'react-dom';
import { XIcon } from './Icons';
import { useVaultContext } from '../contexts/VaultContext';

// Props do modal de configurações
interface SettingsModalProps {
  isOpen: boolean;
  onClose: () => void;
}

const SettingsModal = ({ isOpen, onClose }: SettingsModalProps) => {
  const modalRef = useRef<HTMLDivElement>(null);

  // Consome o contexto global do vault
  const { vaultPath, selectVault, isScanning } = useVaultContext();
  const isSelectingVault = isScanning;

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

  // Chama o contexto para abrir o seletor e escanear automaticamente
  const handleSelectVault = async () => {
    await selectVault();
  };

  if (!isOpen) return null;

  // Renderiza diretamente no document.body via Portal.
  // O overlay usa display:flex para centralizar o modal de forma confiável.
  return createPortal(
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
        onClick={(e) => e.stopPropagation()}
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

          {/* Seção: Vault */}
          <section className="settings-section" aria-labelledby="settings-vault">
            <h3 id="settings-vault" className="settings-section__title">
              Vault
            </h3>

            <div className="settings-item" style={{ flexDirection: 'column', alignItems: 'flex-start' }}>
              <div className="settings-item__info">
                <span className="settings-item__label">Pasta de destino</span>
                <span className="settings-item__description">
                  Diretório onde os arquivos gerados serão salvos
                </span>
              </div>

              {/* Campo de caminho + botão de seleção */}
              <div className="vault-picker" role="group" aria-label="Selecionar pasta de destino">
                <input
                  id="input-vault-path"
                  type="text"
                  className="vault-picker__input"
                  value={vaultPath}
                  placeholder="Nenhuma pasta selecionada"
                  readOnly
                  aria-label="Caminho da pasta de destino"
                  title={vaultPath || 'Nenhuma pasta selecionada'}
                />
                <button
                  id="btn-select-vault"
                  type="button"
                  className="vault-picker__btn"
                  onClick={handleSelectVault}
                  disabled={isSelectingVault}
                  aria-label="Selecionar pasta de destino"
                >
                  {isSelectingVault ? 'Selecionando…' : 'Selecionar'}
                </button>
              </div>
            </div>
          </section>

          <div className="settings-divider" aria-hidden="true" />

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
