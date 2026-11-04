import { useRef, useState } from 'react';
import { useDismissOnOutside } from '../hooks/useDismissOnOutside';
import type { ExportChoice } from '../lib/conversationExport';
import './ExportMenu.css';

const SOURCES_KEY = 'escolio:export:sources';

const FORMATS: { id: ExportChoice; label: string; hint: string }[] = [
  { id: 'md', label: 'Markdown', hint: 'Abre no Obsidian e em editores de notas' },
  { id: 'txt', label: 'Texto simples', hint: 'Sem formatação' },
  { id: 'html', label: 'Página HTML', hint: 'Abre em qualquer navegador' },
  { id: 'json', label: 'JSON', hint: 'Para ler em outro programa' },
  { id: 'pdf', label: 'PDF', hint: 'Pela impressão do sistema' },
];

const readIncludeSources = (): boolean => {
  try {
    return window.localStorage.getItem(SOURCES_KEY) !== '0';
  } catch {
    return true;
  }
};

const ExportIcon = () => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
    <polyline points="7 10 12 15 17 10" />
    <line x1="12" y1="15" x2="12" y2="3" />
  </svg>
);

interface ExportMenuProps {
  onExport: (format: ExportChoice, includeSources: boolean) => void;
}

/** Botão Exportar do cabeçalho: escolhe o formato e se as fontes vão junto. */
const ExportMenu = ({ onExport }: ExportMenuProps) => {
  const [open, setOpen] = useState(false);
  const [includeSources, setIncludeSources] = useState(readIncludeSources);
  const wrapRef = useRef<HTMLDivElement>(null);
  useDismissOnOutside(open, wrapRef, () => setOpen(false));

  const toggleSources = (next: boolean) => {
    setIncludeSources(next);
    try {
      window.localStorage.setItem(SOURCES_KEY, next ? '1' : '0');
    } catch {
      // Sem armazenamento, a escolha vale só nesta sessão.
    }
  };

  return (
    <div className="export-menu" ref={wrapRef}>
      <button
        type="button"
        className="header-action-btn"
        aria-label="Exportar conversa"
        aria-expanded={open}
        title="Exportar conversa"
        onClick={() => setOpen((value) => !value)}
      >
        <ExportIcon />
        <span>Exportar</span>
      </button>
      {open && (
        <div className="export-menu__pop" role="group" aria-label="Formato da exportação">
          {FORMATS.map((format) => (
            <button
              key={format.id}
              type="button"
              className="export-menu__item"
              onClick={() => {
                setOpen(false);
                onExport(format.id, includeSources);
              }}
            >
              <b>{format.label}</b>
              <small>{format.hint}</small>
            </button>
          ))}
          <label className="export-menu__sources">
            <input type="checkbox" checked={includeSources} onChange={(event) => toggleSources(event.target.checked)} />
            Incluir as fontes de cada resposta
          </label>
        </div>
      )}
    </div>
  );
};

export default ExportMenu;
