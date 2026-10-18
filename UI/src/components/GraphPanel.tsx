import { useState, useRef, useCallback, useEffect } from 'react';
import ForceGraph from './ForceGraph';
import { GraphIcon, XIcon } from './Icons';
import { useCorpusGraph } from '../hooks/useCorpusGraph';

// Props do painel lateral de grafos
interface GraphPanelProps {
  isOpen: boolean;
  onToggle: () => void;
  onOpenNote?: (noteId: string) => void;
}

// Largura mínima e máxima permitidas ao redimensionar
const MIN_WIDTH = 220;
const MAX_WIDTH = 700;
const DEFAULT_WIDTH = 320;

// Painel lateral direito para visualização de grafos
const GraphPanel = ({ isOpen, onToggle, onOpenNote }: GraphPanelProps) => {
  const [width, setWidth] = useState(DEFAULT_WIDTH);
  const [isResizingActive, setIsResizingActive] = useState(false);
  const isResizing = useRef(false);

  // Notas indexadas da vault ativa; recarrega ao abrir o painel
  const { nodes, refresh } = useCorpusGraph();
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
          {nodes.length > 0 && <span className="graph-panel__count mono">{nodes.length}</span>}
        </span>
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

      {/* Corpo do painel — grafo de força interativo */}
      <div className="graph-panel__body">
        <ForceGraph vaultNodes={nodes} onOpenNote={onOpenNote} />
      </div>
    </aside>
  );
};

export default GraphPanel;
