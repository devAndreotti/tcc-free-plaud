import { useState } from 'react';
import type { LegendEntry } from '../lib/graphColors';

// Legenda discreta das pastas de 1º nível: fechada por padrão, abre pelo botão do canto do painel
interface GraphLegendProps {
  entries: LegendEntry[];
  overflow: number;
  total: number;
}

const GraphLegend = ({ entries, overflow, total }: GraphLegendProps) => {
  const [open, setOpen] = useState(false);
  return (
    <div className="force-graph__legend">
      <button
        type="button"
        className="force-graph__legend-toggle"
        aria-expanded={open}
        onClick={() => setOpen((v) => !v)}
      >
        Pastas <span className="mono">{total}</span>
      </button>
      {open && (
        <ul className="force-graph__legend-list">
          {entries.map((e) => (
            <li key={e.name} className="force-graph__legend-item">
              <span className="force-graph__swatch" style={{ background: `var(${e.token})` }} aria-hidden="true" />
              <span className="force-graph__legend-name">{e.name}</span>
            </li>
          ))}
          {overflow > 0 && <li className="force-graph__legend-more">{`+${overflow} ${overflow === 1 ? 'pasta' : 'pastas'}`}</li>}
        </ul>
      )}
    </div>
  );
};

export default GraphLegend;
