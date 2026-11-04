import { useCallback, useEffect, useMemo, useState } from 'react';
import { bridge, type VaultOverview, type VaultOverviewNote } from '../services/bridge';
import { CORPUS_CHANGED, CORPUS_PROGRESS_EVENT } from '../lib/corpusEvents';
import { buildOverviewLayout, searchOverview, vaultColorHex, VIEW_H, VIEW_W } from '../lib/vaultsOverviewLayout';
import { VaultGlyph } from './VaultGlyph';
import './VaultsOverview.css';

interface VaultsOverviewProps {
  /** Tela cheia: abre as pastas e busca. No painel estreito, só as vaults fechadas. */
  full: boolean;
  /** Indexação em andamento na vault ativa: ela pulsa e os pontos entram conforme os lotes são gravados. */
  live: boolean;
  onExpand: () => void;
  onClose: () => void;
  onOpenNote: (vaultId: string, noteId: string) => void;
  onAsk: (vaultId: string) => void;
}

const fmt = (value: number) => value.toLocaleString('pt-BR');

/** O Escólio no centro e cada vault em volta; clicar numa vault abre as pastas e as notas dela. */
const VaultsOverview = ({ full, live, onExpand, onClose, onOpenNote, onAsk }: VaultsOverviewProps) => {
  const [vaults, setVaults] = useState<VaultOverview[]>([]);
  const [active, setActive] = useState<string | null>(null);
  const [loaded, setLoaded] = useState(false);
  const [openId, setOpenId] = useState<string | null>(null);
  const [query, setQuery] = useState('');

  const refresh = useCallback(() => {
    Promise.resolve(bridge.getVaultsOverview?.())
      .then((overview) => {
        if (!overview) return;
        setVaults(overview.vaults);
        setActive(overview.active);
      })
      .catch(() => {
        // Sem a visão geral, o seletor continua e o grafo da vault ativa segue funcionando.
      })
      .finally(() => setLoaded(true));
  }, []);

  useEffect(() => {
    refresh();
    window.addEventListener(CORPUS_CHANGED, refresh);
    window.addEventListener(CORPUS_PROGRESS_EVENT, refresh);
    return () => {
      window.removeEventListener(CORPUS_CHANGED, refresh);
      window.removeEventListener(CORPUS_PROGRESS_EVENT, refresh);
    };
  }, [refresh]);

  const term = full ? query.trim().toLowerCase() : '';
  const searching = term.length > 1;
  const hits = useMemo(() => (searching ? searchOverview(vaults, term) : []), [searching, vaults, term]);
  const opened = full && !searching ? openId : null;
  const layout = useMemo(() => buildOverviewLayout(vaults, opened, searching ? hits : null), [vaults, opened, searching, hits]);
  const openVault = vaults.find((vault) => vault.id === opened) ?? null;
  const totalNotes = vaults.reduce((sum, vault) => sum + vault.note_count, 0);
  const totalChunks = vaults.reduce((sum, vault) => sum + vault.chunk_count, 0);
  const maxFolder = openVault?.folders[0]?.count ?? 1;

  const clickVault = (vaultId: string) => {
    if (!full) {
      onExpand();
      setOpenId(vaultId);
      return;
    }
    setQuery('');
    setOpenId((current) => (current === vaultId ? null : vaultId));
  };
  const clickNote = (note: VaultOverviewNote & { vaultId: string }) => onOpenNote(note.vaultId, note.id);

  if (loaded && vaults.length === 0) return <p className="overview__empty">Nenhuma vault cadastrada ainda.</p>;

  return (
    <div className={`overview${full ? ' overview--full' : ''}`} role={full ? 'dialog' : undefined} aria-modal={full || undefined} aria-label={full ? 'Grafo de todas as vaults' : undefined}>
      {full && (
        <header className="overview__head">
          <b>Todas as vaults</b>
          <span className="mono">{searching ? `${hits.length} ${hits.length === 1 ? 'resultado' : 'resultados'}` : `${vaults.length} vaults`}</span>
          <input
            id="overview-search"
            aria-label="Buscar em todas as vaults"
            placeholder="Buscar em todas as vaults"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
          />
          <button type="button" className="btn" onClick={onClose}>Sair da tela cheia</button>
        </header>
      )}
      <div className="overview__body">
        <svg className="overview__graph" viewBox={`0 0 ${VIEW_W} ${VIEW_H}`} role="group" aria-label="Vaults">
          {layout.spokes.map((spoke) => (
            <line key={spoke.id} className="overview__spoke" x1={spoke.x1} y1={spoke.y1} x2={spoke.x2} y2={spoke.y2} style={{ color: spoke.color }} opacity={spoke.dim ? 0.3 : 1} />
          ))}
          {layout.edges.map((edge) => (
            <line key={edge.id} x1={edge.x1} y1={edge.y1} x2={edge.x2} y2={edge.y2} stroke={edge.color} strokeOpacity={edge.dim ? 0.05 : 0.28} />
          ))}
          {layout.dots.map((dot) => (
            <circle
              key={dot.key}
              className="overview__dot"
              cx={dot.x}
              cy={dot.y}
              r={dot.r}
              fill={dot.color}
              opacity={dot.dim ? 0.12 : 1}
              onClick={() => clickNote({ id: dot.note.id, title: dot.note.title, folder: dot.note.folder, vaultId: dot.vaultId })}
            >
              <title>{dot.note.title}</title>
            </circle>
          ))}
          {layout.folders.map((folder) => (
            <g key={folder.key}>
              <circle cx={folder.x} cy={folder.y} r={folder.r} fill={folder.color} opacity={folder.dim ? 0.15 : 1} />
              {!folder.dim && (
                <text className="overview__label" x={folder.x + (folder.right ? folder.r + 5 : -folder.r - 5)} y={folder.y + 4} textAnchor={folder.right ? 'start' : 'end'}>
                  {folder.name} {folder.count}
                </text>
              )}
            </g>
          ))}
        </svg>
        {/* Botões de verdade por cima do desenho: dá para chegar neles pelo teclado. */}
        <div className="overview__nodes">
          <button type="button" className="overview__hub" style={{ left: `${(layout.hub.x / VIEW_W) * 100}%`, top: `${(layout.hub.y / VIEW_H) * 100}%` }} aria-label="Escólio: recolher tudo" onClick={() => { setOpenId(null); setQuery(''); }}>ES</button>
          {layout.vaults.map((node) => {
            const color = vaultColorHex(node.vault.color);
            return (
              <div key={node.vault.id} className={`overview__vault${node.dim ? ' is-dim' : ''}`} style={{ left: `${(node.x / VIEW_W) * 100}%`, top: `${(node.y / VIEW_H) * 100}%` }}>
                <button
                  type="button"
                  className={`overview__node${live && node.vault.id === active ? ' is-live' : ''}${node.vault.id === opened ? ' is-open' : ''}`}
                  style={{ color, width: node.size, height: node.size }}
                  aria-label={`${node.vault.name}: ${node.vault.note_count} notas${live && node.vault.id === active ? ', indexando' : ''}`}
                  aria-pressed={node.vault.id === opened}
                  onClick={() => clickVault(node.vault.id)}
                >
                  <VaultGlyph icon={node.vault.icon} color={node.vault.color} size={Math.round(node.size * 0.42)} />
                </button>
                <span className="overview__name"><b>{node.vault.name}</b><span className="mono">{fmt(node.vault.note_count)} notas</span></span>
              </div>
            );
          })}
        </div>
      </div>
      <aside className="overview__side" aria-label="Detalhes">
        {searching ? (
          <>
            <h2>{hits.length ? `${hits.length} ${hits.length === 1 ? 'resultado' : 'resultados'}` : 'Nada encontrado'}</h2>
            <p className="mono">para “{query.trim()}”, em todas as vaults</p>
            <ul className="overview__hits">
              {hits.slice(0, 60).map((hit) => (
                <li key={`${hit.vaultId}:${hit.note.id}`}>
                  <button type="button" onClick={() => clickNote({ ...hit.note, vaultId: hit.vaultId })}>
                    <span>{hit.note.title}</span><small>{hit.vaultName}{hit.note.folder ? ` · ${hit.note.folder}` : ''}</small>
                  </button>
                </li>
              ))}
            </ul>
          </>
        ) : openVault ? (
          <>
            <h2>{openVault.name}</h2>
            <p className="mono">{fmt(openVault.note_count)} notas · {fmt(openVault.chunk_count)} trechos</p>
            <ul className="overview__folders">
              {openVault.folders.slice(0, 12).map((folder) => (
                <li key={folder.name}>
                  <span>{folder.name || 'Na raiz da vault'}</span><b className="mono">{fmt(folder.count)}</b>
                  <i><u style={{ width: `${(folder.count / maxFolder) * 100}%` }} /></i>
                </li>
              ))}
            </ul>
            <button type="button" className="btn btn--primary" onClick={() => onAsk(openVault.id)}>Perguntar a esta vault</button>
            <button type="button" className="btn" onClick={() => setOpenId(null)}>Recolher</button>
          </>
        ) : (
          <>
            {full && <h2>Todas as vaults</h2>}
            <p className="mono">{fmt(totalNotes)} notas · {fmt(totalChunks)} trechos</p>
            <p>{full ? 'O Escólio fica no centro e cada vault em volta. Clique numa vault para abrir as pastas dela.' : 'Aqui as vaults aparecem fechadas. Para abrir as pastas e buscar, use a tela cheia.'}</p>
            {!full && <button type="button" className="btn btn--primary" onClick={onExpand}>Abrir em tela cheia</button>}
          </>
        )}
      </aside>
    </div>
  );
};

export default VaultsOverview;
