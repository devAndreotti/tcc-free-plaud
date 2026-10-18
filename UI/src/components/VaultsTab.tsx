import { useState } from 'react';
import { useVaults } from '../hooks/useVaults';
import type { Vault } from '../services/bridge';
import VaultDialog from './VaultDialog';
import { VaultGlyph } from './VaultGlyph';

interface VaultsTabProps {
  onOpenQueue: () => void;
}

/** Aba Vaults das Configurações: lista, ativa, renomeia, troca ícone/cor e exclui (só o índice). */
const VaultsTab = ({ onOpenQueue }: VaultsTabProps) => {
  const { vaults, active, select, update, remove } = useVaults();
  const [renamingId, setRenamingId] = useState<string | null>(null);
  const [renameText, setRenameText] = useState('');
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [confirmText, setConfirmText] = useState('');
  const [editing, setEditing] = useState<Vault | 'new' | null>(null);
  const [message, setMessage] = useState('');

  const report = (result: { ok: boolean; message?: string }, fallback: string) => {
    setMessage(result.ok ? '' : result.message ?? fallback);
    return result.ok;
  };

  const startRename = (vault: Vault) => {
    setRenamingId(vault.id);
    setRenameText(vault.name);
    setDeletingId(null);
  };

  const saveRename = async (vault: Vault) => {
    const name = renameText.trim();
    if (!name) {
      setMessage('Dê um nome à vault.');
      return;
    }
    if (report(await update(vault.id, { name }), 'Não foi possível renomear.')) setRenamingId(null);
  };

  const startDelete = (vault: Vault) => {
    setDeletingId(vault.id);
    setConfirmText('');
    setRenamingId(null);
  };

  const confirmDelete = async (vault: Vault) => {
    if (report(await remove(vault.id, confirmText), 'Não foi possível excluir.')) {
      setDeletingId(null);
      setConfirmText('');
    }
  };

  return (
    <section className="settings-section" aria-labelledby="settings-vaults">
      <h3 id="settings-vaults" className="settings-section__title">Vaults</h3>
      <p className="settings-item__description">
        Cada vault tem seu corpus, suas pastas, sua Fila e suas conversas. Tudo na tela segue a vault ativa.
      </p>

      <ul className="vaults-list" aria-label="Vaults cadastradas">
        {vaults.map((vault) => {
          const isActive = vault.id === active?.id;
          const isRenaming = renamingId === vault.id;
          const isDeleting = deletingId === vault.id;
          return (
            <li key={vault.id} className="vaults-list__item">
              <div className="vaults-list__row">
                <VaultGlyph icon={vault.icon} color={vault.color} size={16} />
                <div className="vaults-list__info">
                  {isRenaming ? (
                    <input
                      type="text"
                      aria-label={`Novo nome de ${vault.name}`}
                      value={renameText}
                      maxLength={60}
                      onChange={(event) => setRenameText(event.target.value)}
                    />
                  ) : (
                    <b>
                      {vault.name}
                      {isActive && <em className="vaults-list__badge">ativa</em>}
                    </b>
                  )}
                  <span className="mono">
                    {(vault.note_count ?? 0).toLocaleString('pt-BR')} notas · {vault.folders.length} pastas
                  </span>
                  <span className="settings-item__description">
                    Modelo de embedding: {vault.embedding_model ?? 'padrão'} (fixo nesta vault; trocar exige reindexar)
                  </span>
                </div>
                <div className="vaults-list__actions">
                  {isRenaming ? (
                    <>
                      <button type="button" className="btn" onClick={() => void saveRename(vault)}>Salvar nome</button>
                      <button type="button" className="btn" onClick={() => setRenamingId(null)}>Cancelar</button>
                    </>
                  ) : (
                    <>
                      {!isActive && (
                        <button
                          type="button"
                          className="btn"
                          onClick={async () => report(await select(vault.id), 'Não foi possível ativar.')}
                        >
                          Ativar
                        </button>
                      )}
                      <button type="button" className="btn" onClick={() => startRename(vault)}>Renomear</button>
                      <button type="button" className="btn" onClick={() => setEditing(vault)}>Ícone e cor</button>
                      <button
                        type="button"
                        className="btn"
                        disabled={vaults.length === 1}
                        title={vaults.length === 1 ? 'Não é possível excluir a única vault' : undefined}
                        onClick={() => startDelete(vault)}
                      >
                        Excluir
                      </button>
                    </>
                  )}
                </div>
              </div>

              {isDeleting && (
                <div className="vaults-list__delete">
                  <p>
                    Digite <b>{vault.name}</b> para confirmar. Isso apaga só o índice desta vault
                    (data/vaults/{vault.id}). Os arquivos das pastas de origem não são tocados.
                  </p>
                  <input
                    type="text"
                    aria-label={`Digite ${vault.name} para excluir`}
                    value={confirmText}
                    onChange={(event) => setConfirmText(event.target.value)}
                  />
                  <button
                    type="button"
                    className="btn"
                    disabled={confirmText !== vault.name}
                    onClick={() => void confirmDelete(vault)}
                  >
                    Excluir índice
                  </button>
                  <button type="button" className="btn" onClick={() => setDeletingId(null)}>Cancelar</button>
                </div>
              )}
            </li>
          );
        })}
      </ul>

      {message && <p className="vault-dialog__error" role="alert">{message}</p>}

      <div className="vaults-list__footer">
        <button type="button" className="btn" onClick={() => setEditing('new')}>Nova vault</button>
        <button type="button" className="btn" onClick={onOpenQueue}>Indexar na Fila</button>
      </div>

      {editing && (
        <VaultDialog vault={editing === 'new' ? undefined : editing} onClose={() => setEditing(null)} />
      )}
    </section>
  );
};

export default VaultsTab;
