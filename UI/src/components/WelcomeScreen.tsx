import type { Vault } from '../services/bridge';
import { VaultGlyph } from './VaultGlyph';

interface WelcomeScreenProps {
  /** Vault ativa; null enquanto a lista de vaults não chegou. */
  vault?: Vault | null;
  /** Vault vazia: leva à Fila para indexar a primeira pasta. */
  onOpenQueue?: () => void;
}

// Tela inicial exibida quando a conversa ainda não tem mensagens: mostra a vault que vai responder.
const WelcomeScreen = ({ vault = null, onOpenQueue }: WelcomeScreenProps) => {
  const notes = vault?.note_count ?? 0;
  const empty = vault !== null && notes === 0;
  return (
    <div className="welcome" role="main" aria-label="Tela inicial">
      {vault ? (
        <span className="welcome__glyph">
          <VaultGlyph icon={vault.icon} color={vault.color} size={28} />
        </span>
      ) : (
        <span className="welcome__mark" aria-hidden="true">ES</span>
      )}
      {vault && <span className="welcome__kicker">Vault ativa</span>}
      <h1 className="welcome__title">{vault ? vault.name : 'Pergunte ao seu vault'}</h1>
      <p className="welcome__lede">
        {empty
          ? 'Esta vault ainda está vazia. Indexe uma pasta para começar a perguntar.'
          : `As respostas vêm só das ${vault ? `${notes.toLocaleString('pt-BR')} ${notes === 1 ? 'nota' : 'notas'} desta vault` : 'notas indexadas'}, e cada afirmação aponta para o trecho que a sustenta.`}
      </p>
      {empty && onOpenQueue && (
        <button type="button" className="btn btn--primary welcome__cta" onClick={onOpenQueue}>
          Indexar uma pasta na Fila
        </button>
      )}
    </div>
  );
};

export default WelcomeScreen;
