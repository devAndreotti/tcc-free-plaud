import { useState, type KeyboardEvent } from 'react';
import { useVaults } from '../hooks/useVaults';
import { notifyCorpusChanged } from '../hooks/useCorpusHealth';
import { bridge, type Vault } from '../services/bridge';
import { vaultMeta } from '../lib/vaultVisuals';
import VaultAppearanceFields from './VaultAppearanceFields';
import VaultDialog from './VaultDialog';
import { VaultGlyph } from './VaultGlyph';
import { FolderIcon, PlusIcon, TrashIcon } from './Icons';

interface VaultsTabProps {
  onOpenQueue: () => void;
}

type Report = (result: { ok: boolean; message?: string }, fallback: string) => boolean;

const createdOn = (iso: string): string => {
  const date = new Date(iso);
  return Number.isNaN(date.getTime()) ? '' : date.toLocaleDateString('pt-BR');
};

const folderName = (path: string): string => path.split(/[\\/]/).filter(Boolean).pop() ?? path;

interface VaultDetailProps {
  vault: Vault;
  isActive: boolean;
  onlyOne: boolean;
  report: Report;
  onOpenQueue: () => void;
}

/** Detalhe da vault escolhida: nome, ícone e cor (valem na hora), pastas, índice e exclusão. */
const VaultDetail = ({ vault, isActive, onlyOne, report, onOpenQueue }: VaultDetailProps) => {
  const { select, update, remove } = useVaults();
  const [name, setName] = useState(vault.name);
  const [removingRoot, setRemovingRoot] = useState<string | null>(null);
  const [deleting, setDeleting] = useState(false);
  const [confirmText, setConfirmText] = useState('');
  const roots = vault.roots ?? [];
  const created = createdOn(vault.created_at);

  const saveName = async () => {
    const trimmed = name.trim();
    if (!trimmed) {
      setName(vault.name);
      report({ ok: false, message: 'Dê um nome à vault.' }, '');
      return;
    }
    if (trimmed !== vault.name) report(await update(vault.id, { name: trimmed }), 'Não foi possível renomear.');
  };

  const onNameKey = (event: KeyboardEvent<HTMLInputElement>) => {
    if (event.key === 'Enter') event.currentTarget.blur();
    if (event.key === 'Escape') setName(vault.name);
  };

  // A Fila indexa na vault ativa: ativa esta antes, se preciso.
  const indexFolder = async () => {
    if (!isActive && !report(await select(vault.id), 'Não foi possível ativar a vault.')) return;
    onOpenQueue();
  };

  const removeRoot = async (root: string) => {
    let result: { ok: boolean; message?: string };
    try {
      result = await bridge.removeCorpusRoot(root, 'REMOVER');
    } catch (err) {
      result = { ok: false, message: err instanceof Error ? err.message : undefined };
    }
    if (report(result, 'Não foi possível remover a pasta.')) {
      setRemovingRoot(null);
      notifyCorpusChanged();
    }
  };

  const confirmDelete = async () => {
    if (report(await remove(vault.id, confirmText), 'Não foi possível excluir.')) {
      setDeleting(false);
      setConfirmText('');
    }
  };

  return (
    <div className="vaults-tab__detail">
      <div className="vaults-tab__detail-head">
        <span className="vaults-tab__glyph">
          <VaultGlyph icon={vault.icon} color={vault.color} size={26} />
        </span>
        <div className="vaults-tab__name">
          <label htmlFor={`vault-name-${vault.id}`}>Nome da vault</label>
          <input
            id={`vault-name-${vault.id}`}
            type="text"
            value={name}
            maxLength={60}
            onChange={(event) => setName(event.target.value)}
            onBlur={() => void saveName()}
            onKeyDown={onNameKey}
          />
          <span className="mono">
            {vaultMeta(vault)}
            {created && ` · criada em ${created}`}
          </span>
        </div>
        {isActive ? (
          <span className="vaults-tab__badge vaults-tab__badge--lg">Ativa agora</span>
        ) : (
          <button
            type="button"
            className="btn"
            onClick={() => void select(vault.id).then((result) => report(result, 'Não foi possível ativar a vault.'))}
          >
            Ativar esta vault
          </button>
        )}
      </div>

      <VaultAppearanceFields
        icon={vault.icon}
        color={vault.color}
        onIconChange={(icon) => void update(vault.id, { icon }).then((result) => report(result, 'Não foi possível trocar o ícone.'))}
        onColorChange={(color) => void update(vault.id, { color }).then((result) => report(result, 'Não foi possível trocar a cor.'))}
      />

      <div className="vaults-tab__section">
        <div className="vaults-tab__section-head">
          <h4>Pastas indexadas</h4>
          <button type="button" className="btn btn--sm" onClick={() => void indexFolder()}>
            <PlusIcon size={15} />
            Indexar pasta
          </button>
        </div>
        {roots.length > 0 ? (
          <ul className="vaults-tab__roots" aria-label={`Pastas de ${vault.name}`}>
            {roots.map((root) => (
              <li key={root.root} className="vaults-tab__root">
                <FolderIcon size={16} />
                <span className="vaults-tab__root-text">
                  <span>{folderName(root.root)}</span>
                  <small className="mono" title={root.root}>{root.root}</small>
                </span>
                <span className="vaults-tab__root-count mono">
                  {root.notes_count.toLocaleString('pt-BR')} {root.notes_count === 1 ? 'nota' : 'notas'}
                </span>
                {isActive &&
                  (removingRoot === root.root ? (
                    <span className="vaults-tab__root-confirm">
                      <button type="button" className="btn btn--sm btn--danger" onClick={() => void removeRoot(root.root)}>
                        Remover do índice
                      </button>
                      <button type="button" className="btn btn--sm" onClick={() => setRemovingRoot(null)}>
                        Cancelar
                      </button>
                    </span>
                  ) : (
                    <button
                      type="button"
                      className="btn-icon"
                      aria-label={`Remover a pasta ${folderName(root.root)} do índice`}
                      onClick={() => setRemovingRoot(root.root)}
                    >
                      <TrashIcon size={15} />
                    </button>
                  ))}
              </li>
            ))}
          </ul>
        ) : (
          <p className="vaults-tab__empty">Nenhuma pasta indexada nesta vault ainda.</p>
        )}
        <p className="settings-item__description">
          {isActive
            ? 'Remover uma pasta tira as notas dela do índice; os arquivos continuam no disco.'
            : 'Indexar pasta ativa esta vault e abre a Fila dela. Para remover pastas, ative a vault.'}
        </p>
      </div>

      <div className="vaults-tab__index">
        <span>Modelo de busca semântica</span>
        <code>{vault.embedding_model ?? 'padrão'}</code>
        <small>fixo nesta vault; trocar exige reindexar</small>
      </div>

      <div className="vaults-tab__danger">
        <div className="vaults-tab__danger-row">
          <div>
            <h4>Excluir vault</h4>
            <p>Apaga o índice desta vault: notas, vetores e conversas. As pastas de origem continuam no disco.</p>
          </div>
          {!deleting && (
            <button
              type="button"
              className="btn vaults-tab__danger-btn"
              disabled={onlyOne}
              onClick={() => {
                setDeleting(true);
                setConfirmText('');
              }}
            >
              Excluir…
            </button>
          )}
        </div>
        {onlyOne && <p className="settings-item__description">É a única vault: crie outra antes de excluir esta.</p>}
        {deleting && (
          <div className="vaults-tab__confirm">
            <label htmlFor={`vault-confirm-${vault.id}`}>
              Digite <b>{vault.name}</b> para confirmar
            </label>
            <input
              id={`vault-confirm-${vault.id}`}
              type="text"
              value={confirmText}
              autoFocus
              onChange={(event) => setConfirmText(event.target.value)}
            />
            <button type="button" className="btn" onClick={() => setDeleting(false)}>
              Cancelar
            </button>
            <button
              type="button"
              className="btn btn--danger"
              disabled={confirmText !== vault.name}
              onClick={() => void confirmDelete()}
            >
              Excluir vault
            </button>
          </div>
        )}
      </div>
    </div>
  );
};

/** Aba Vaults das Configurações: lista à esquerda, detalhe da vault escolhida à direita. */
const VaultsTab = ({ onOpenQueue }: VaultsTabProps) => {
  const { vaults, active } = useVaults();
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);
  const [message, setMessage] = useState('');
  // A vault escolhida some ao ser excluída: o detalhe volta para a ativa.
  const selected = vaults.find((vault) => vault.id === selectedId) ?? active ?? vaults[0] ?? null;

  const report: Report = (result, fallback) => {
    setMessage(result.ok ? '' : result.message ?? fallback);
    return result.ok;
  };

  return (
    <section className="settings-section vaults-tab" aria-labelledby="settings-vaults">
      <div className="vaults-tab__head">
        <div>
          <h3 id="settings-vaults" className="settings-section__title">Vaults</h3>
          <p className="settings-item__description">
            Cada vault é um espaço separado: índice, pastas, Fila, grafo e conversas próprios. Mudanças aqui valem na
            hora.
          </p>
        </div>
        <button type="button" className="btn btn--primary" onClick={() => setCreating(true)}>
          <PlusIcon size={16} />
          Nova vault
        </button>
      </div>

      {message && <p className="vault-dialog__error" role="alert">{message}</p>}

      <div className="vaults-tab__body">
        <ul className="vaults-tab__list" aria-label="Vaults cadastradas">
          {vaults.map((vault) => {
            const isSelected = vault.id === selected?.id;
            return (
              <li key={vault.id}>
                <button
                  type="button"
                  className={`vaults-tab__row${isSelected ? ' vaults-tab__row--on' : ''}`}
                  aria-current={isSelected ? 'true' : undefined}
                  onClick={() => {
                    setSelectedId(vault.id);
                    setMessage('');
                  }}
                >
                  <VaultGlyph icon={vault.icon} color={vault.color} size={17} />
                  <span className="vaults-tab__row-text">
                    <b>{vault.name}</b>
                    <small className="mono">{vaultMeta(vault)}</small>
                  </span>
                  {vault.id === active?.id && <span className="vaults-tab__badge">Ativa</span>}
                </button>
              </li>
            );
          })}
        </ul>
        {selected && (
          <VaultDetail
            key={selected.id}
            vault={selected}
            isActive={selected.id === active?.id}
            onlyOne={vaults.length === 1}
            report={report}
            onOpenQueue={onOpenQueue}
          />
        )}
      </div>

      {creating && <VaultDialog onClose={() => setCreating(false)} />}
    </section>
  );
};

export default VaultsTab;
