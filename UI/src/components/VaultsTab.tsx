import { useState } from 'react';
import { useVaults } from '../hooks/useVaults';
import { Sk, SkLines } from './ui/Loading';
import { folderName, vaultMeta } from '../lib/vaultVisuals';
import VaultDetail, { type Report } from './VaultDetail';
import VaultDialog from './VaultDialog';
import { VaultGlyph } from './VaultGlyph';
import { FolderIcon, PlusIcon } from './Icons';
import './VaultsTab.css';

interface VaultsTabProps {
  onOpenQueue: () => void;
}

/** Aba Vaults das Configurações: vaults em cartões na largura toda, detalhe da escolhida logo abaixo. */
const VaultsTab = ({ onOpenQueue }: VaultsTabProps) => {
  const { vaults, active, loaded } = useVaults();
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
        <h3 id="settings-vaults" className="settings-section__title">Vaults</h3>
        <p className="settings-item__description">
          Cada vault é um espaço separado: índice, pastas, Fila, grafo e conversas próprios. Mudanças aqui valem na
          hora.
        </p>
      </div>

      {message && <p className="vault-dialog__error" role="alert">{message}</p>}

      <div className="vaults-tab__body">
        <ul className="vaults-tab__list" aria-label="Vaults cadastradas">
          {loaded === false && vaults.length === 0 && [0, 1].map((key) => (
            <li key={key} className="load-wait load-row" style={{ padding: 12 }} aria-hidden="true"><Sk w={34} h={34} r={10} /><SkLines widths={['44%', '66%']} gap={6} /></li>
          ))}
          {vaults.map((vault) => {
            const isSelected = vault.id === selected?.id;
            const paths = vault.roots?.map((root) => root.root) ?? vault.folders;
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
                  <VaultGlyph icon={vault.icon} color={vault.color} size={20} />
                  <span className="vaults-tab__row-text">
                    <span className="vaults-tab__row-title">
                      <b>{vault.name}</b>
                      {vault.id === active?.id && <span className="vaults-tab__badge">Ativa</span>}
                    </span>
                    <small className="mono">{vaultMeta(vault)}</small>
                    <small className="vaults-tab__row-folders">
                      <FolderIcon size={12} />
                      <span>{paths.length > 0 ? paths.map(folderName).join(', ') : 'Nenhuma pasta indexada'}</span>
                    </small>
                  </span>
                </button>
              </li>
            );
          })}
          <li>
            <button type="button" className="vaults-tab__add" onClick={() => setCreating(true)}>
              <PlusIcon size={16} />
              Nova vault
            </button>
          </li>
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
