import { useEffect, useState, type FormEvent } from 'react';
import { useVaults } from '../hooks/useVaults';
import type { Vault, VaultColor, VaultIconId } from '../services/bridge';
import { VAULT_COLOR_OPTIONS, VAULT_ICON_OPTIONS } from '../lib/vaultVisuals';
import { VaultGlyph, VAULT_ICON_COMPONENTS } from './VaultGlyph';
import { XIcon } from './Icons';

interface VaultDialogProps {
  /** Sem vault: cria uma nova. Com vault: edita ícone, cor e nome dela. */
  vault?: Vault;
  onClose: () => void;
}

/** Modal de criar ou editar vault: nome obrigatório, ícone e cor da paleta fixa. */
const VaultDialog = ({ vault, onClose }: VaultDialogProps) => {
  const { create, update } = useVaults();
  const [name, setName] = useState(vault?.name ?? '');
  const [icon, setIcon] = useState<VaultIconId>(vault?.icon ?? 'notes');
  const [color, setColor] = useState<VaultColor>(vault?.color ?? 'violet');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose();
    };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [onClose]);

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    const trimmed = name.trim();
    if (!trimmed) {
      setError('Dê um nome à vault.');
      return;
    }
    setBusy(true);
    setError('');
    const result = vault
      ? await update(vault.id, { name: trimmed, icon, color })
      : await create(trimmed, icon, color);
    setBusy(false);
    if (result.ok) onClose();
    else setError(result.message ?? 'Não foi possível salvar a vault.');
  };

  const title = vault ? 'Editar vault' : 'Nova vault';

  return (
    <div className="vault-dialog-backdrop" role="presentation" onMouseDown={(event) => event.target === event.currentTarget && onClose()}>
      <form className="vault-dialog" role="dialog" aria-modal="true" aria-labelledby="vault-dialog-title" onSubmit={handleSubmit}>
        <header className="vault-dialog__head">
          <h2 id="vault-dialog-title">{title}</h2>
          <button type="button" className="vault-dialog__close" aria-label="Fechar" onClick={onClose}>
            <XIcon size={14} />
          </button>
        </header>

        <label className="vault-dialog__field">
          <span>Nome</span>
          <input
            id="input-vault-name"
            type="text"
            value={name}
            autoFocus
            maxLength={60}
            aria-invalid={error ? true : undefined}
            onChange={(event) => setName(event.target.value)}
          />
        </label>

        <fieldset className="vault-dialog__field">
          <legend>Ícone</legend>
          <div className="vault-dialog__icons">
            {VAULT_ICON_OPTIONS.map((option) => {
              const Glyph = VAULT_ICON_COMPONENTS[option.id];
              return (
                <button
                  key={option.id}
                  type="button"
                  className={`vault-dialog__icon${icon === option.id ? ' vault-dialog__icon--on' : ''}`}
                  aria-label={`Ícone ${option.label}`}
                  aria-pressed={icon === option.id}
                  onClick={() => setIcon(option.id)}
                >
                  <Glyph size={16} />
                </button>
              );
            })}
          </div>
        </fieldset>

        <fieldset className="vault-dialog__field">
          <legend>Cor</legend>
          <div className="vault-dialog__colors">
            {VAULT_COLOR_OPTIONS.map((option) => (
              <button
                key={option.id}
                type="button"
                className={`vault-dialog__color vault-glyph--${option.id}${color === option.id ? ' vault-dialog__color--on' : ''}`}
                aria-label={`Cor ${option.label}`}
                aria-pressed={color === option.id}
                onClick={() => setColor(option.id)}
              />
            ))}
          </div>
        </fieldset>

        <div className="vault-dialog__preview">
          <VaultGlyph icon={icon} color={color} size={16} />
          <span>{name.trim() || 'Sem nome'}</span>
        </div>

        {error && <p className="vault-dialog__error" role="alert">{error}</p>}

        <footer className="vault-dialog__actions">
          <button type="button" className="btn" onClick={onClose}>Cancelar</button>
          <button type="submit" className="btn btn--primary" disabled={busy}>
            {busy ? 'Salvando…' : vault ? 'Salvar' : 'Criar vault'}
          </button>
        </footer>
      </form>
    </div>
  );
};

export default VaultDialog;
