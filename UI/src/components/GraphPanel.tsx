import { useState, useRef, useCallback, useEffect } from 'react';
import ForceGraph from './ForceGraph';
import VaultsOverview from './VaultsOverview';
import { GraphIcon, XIcon } from './Icons';
import { useCorpusGraph } from '../hooks/useCorpusGraph';
import type { GraphMode } from '../lib/vaultGraph';

// Props do painel lateral de grafos
interface GraphPanelProps {
  isOpen: boolean;
  onToggle: () => void;
  onOpenNote?: (noteId: string) => void;
  /** Nota ou conversa de outra vault: quem abre troca de vault antes. */
  onOpenVaultNote?: (vaultId: string, noteId: string) => void;
  onAskVault?: (vaultId: string) => void;
}

// Largura mínima e máxima permitidas ao redimensionar
const MIN_WIDTH = 220;
const MAX_WIDTH = 700;
const DEFAULT_WIDTH = 320;

// Modos do seletor (ordem dos botões) e a chave do localStorage que lembra a escolha
const MODE_STORAGE_KEY = 'escolio:graph:mode';
const SCOPE_STORAGE_KEY = 'escolio:graph:scope';
const GRAPH_MODES: { id: GraphMode; label: string }[] = [
  { id: 'pastas', label: 'Pastas' },
  { id: 'links', label: 'Links' },
  { id: 'ambos', label: 'Ambos' },
];

// Último modo escolhido; sem acesso ao armazenamento (modo privado, bloqueado) vale o padrão
function readStoredMode(): GraphMode {
  try {
    const saved = window.localStorage.getItem(MODE_STORAGE_KEY);
    if (saved === 'pastas' || saved === 'links' || saved === 'ambos') return saved;
  } catch {
    // sem armazenamento: segue no padrão
  }
  return 'ambos';
}

// Painel lateral direito para visualização de grafos
const GraphPanel = ({ isOpen, onToggle, onOpenNote, onOpenVaultNote, onAskVault }: GraphPanelProps) => {
  // Esta vault ou todas: a escolha fica lembrada; a tela cheia, não.
  const [scope, setScope] = useState<'vault' | 'all'>(() => {
    try {
      return window.localStorage.getItem(SCOPE_STORAGE_KEY) === 'all' ? 'all' : 'vault';
    } catch {
      return 'vault';
    }
  });
  const [fullscreen, setFullscreen] = useState(false);
  const chooseScope = (next: 'vault' | 'all') => {
    setScope(next);
    try {
      window.localStorage.setItem(SCOPE_STORAGE_KEY, next);
    } catch {
      // sem armazenamento a escolha vale só nesta sessão
    }
  };
  const [width, setWidth] = useState(DEFAULT_WIDTH);
  const [isResizingActive, setIsResizingActive] = useState(false);
  const isResizing = useRef(false);

  // Notas indexadas da vault ativa e as ligações entre elas; recarrega ao abrir o painel
  const { nodes, links, refresh, activeId, live, loaded } = useCorpusGraph();
  const [mode, setMode] = useState<GraphMode>(readStoredMode);
  const chooseMode = (next: GraphMode) => {
    setMode(next);
    try {
      window.localStorage.setItem(MODE_STORAGE_KEY, next);
    } catch {
      // sem armazenamento a escolha vale só nesta sessão
    }
  };
  useEffect(() => {
    if (isOpen) void refresh();
  }, [isOpen, refresh]);

  // Inicia o arrasto da alça de redimensionamento
  const handleResizeStart = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    isResizing.current = true;
    setIsResizingActive(true);
    const startX = e.clientX;
    const startWidth = width;

    // Adiciona cursor global durante o arrasto para evitar flickering
    document.body.style.cursor = 'col-resize';
    document.body.style.userSelect = 'none';

    const onMouseMove = (ev: MouseEvent) => {
      if (!isResizing.current) return;
      // Arrastar para a esquerda = painel mais largo
      const delta = startX - ev.clientX;
      setWidth(Math.max(MIN_WIDTH, Math.min(MAX_WIDTH, startWidth + delta)));
    };

    const onMouseUp = () => {
      isResizing.current = false;
      setIsResizingActive(false);
      document.body.style.cursor = '';
      document.body.style.userSelect = '';
      window.removeEventListener('mousemove', onMouseMove);
      window.removeEventListener('mouseup', onMouseUp);
    };

    window.addEventListener('mousemove', onMouseMove);
    window.addEventListener('mouseup', onMouseUp);
  }, [width]);

  // Estilo inline controla a largura quando aberto; transição desativada durante resize
  const panelStyle = isOpen
    ? {
        width: `${width}px`,
        minWidth: `${width}px`,
        transition: isResizingActive
          ? 'border-left-width 260ms cubic-bezier(0.4, 0, 0.2, 1)'
          : undefined,
      }
    : {};

  return (
    <aside
      className={`graph-panel${isOpen ? ' graph-panel--open' : ''}`}
      style={panelStyle}
      aria-label="Painel de grafos"
      aria-hidden={!isOpen}
      id="graph-panel"
    >
      {/* Alça de redimensionamento — borda esquerda arrastável */}
      {isOpen && (
        <div
          className="graph-panel__resize-handle"
          onMouseDown={handleResizeStart}
          title="Arrastar para redimensionar"
          aria-hidden="true"
        />
      )}

      {/* Cabeçalho do painel — contém o botão de toggle (alinhado à tab bar) */}
      <div className="graph-panel__header">
        <span className="graph-panel__title">
          <GraphIcon size={14} />
          Grafo
          {scope === 'vault' && nodes.length > 0 && <span className="graph-panel__count mono">{nodes.length}</span>}
        </span>
        {scope === 'vault' && <div className="graph-panel__modes" role="group" aria-label="O que o grafo mostra">
          {GRAPH_MODES.map((option) => (
            <button
              key={option.id}
              type="button"
              className="graph-panel__mode"
              aria-pressed={mode === option.id}
              onClick={() => chooseMode(option.id)}
            >
              {option.label}
            </button>
          ))}
        </div>}
        <button
          type="button"
          className="btn-icon"
          onClick={onToggle}
          aria-label="Fechar painel de grafos"
          aria-expanded={isOpen}
          aria-controls="graph-panel"
          title="Fechar"
        >
          <XIcon size={14} />
        </button>
      </div>

      <div className="graph-panel__scope" role="group" aria-label="Quais vaults o grafo mostra">
        <button type="button" aria-pressed={scope === 'vault'} onClick={() => chooseScope('vault')}>Esta vault</button>
        <button type="button" aria-pressed={scope === 'all'} onClick={() => chooseScope('all')}>Todas as vaults</button>
      </div>

      {/* Indexação em andamento: o que está entrando no grafo agora (visual; o andamento é anunciado na Fila) */}
      {live && (
        <p className="graph-panel__live">
          <span className="graph-panel__live-dot ui-pulse" aria-hidden="true" />
          <span className="graph-panel__live-text">
            Ao vivo
            {live.current && ` · ${live.current}`}
            {live.pending > 0 && ` · ${live.pending} aguardando gravação`}
          </span>
        </p>
      )}

      {/* Corpo do painel — grafo de força interativo */}
      <div className="graph-panel__body">
        {/* Fechado, o painel não desenha o anel: o job pode durar minutos */}
        {scope === 'all' ? (
          isOpen && (
            <VaultsOverview
              full={fullscreen}
              live={Boolean(live)}
              onExpand={() => setFullscreen(true)}
              onClose={() => setFullscreen(false)}
              onOpenNote={(vaultId, noteId) => {
                setFullscreen(false);
                onOpenVaultNote?.(vaultId, noteId);
              }}
              onAsk={(vaultId) => {
                setFullscreen(false);
                onAskVault?.(vaultId);
              }}
            />
          )
        ) : (
        <ForceGraph vaultNodes={nodes} links={links} mode={mode} onOpenNote={onOpenNote} activeId={isOpen ? activeId : null} loading={!loaded} />
        )}
      </div>
    </aside>
  );
};

export default GraphPanel;
