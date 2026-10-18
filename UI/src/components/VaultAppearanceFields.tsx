import type { VaultColor, VaultIconId } from '../services/bridge';
import { VAULT_COLOR_OPTIONS, VAULT_ICON_OPTIONS } from '../lib/vaultVisuals';
import { VAULT_ICON_COMPONENTS } from './VaultGlyph';

interface VaultAppearanceFieldsProps {
  icon: VaultIconId;
  color: VaultColor;
  onIconChange: (icon: VaultIconId) => void;
  onColorChange: (color: VaultColor) => void;
}

/** Ícone (do conjunto do app) e cor (paleta fixa) da vault: ao criar e na aba Vaults. */
const VaultAppearanceFields = ({ icon, color, onIconChange, onColorChange }: VaultAppearanceFieldsProps) => (
  <>
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
              onClick={() => onIconChange(option.id)}
            >
              <Glyph size={17} />
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
            title={option.label}
            aria-pressed={color === option.id}
            onClick={() => onColorChange(option.id)}
          />
        ))}
      </div>
    </fieldset>
  </>
);

export default VaultAppearanceFields;
