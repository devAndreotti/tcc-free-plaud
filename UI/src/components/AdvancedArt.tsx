// Desenhos dos grupos do Avançado (canvas "Avançado · presets e ajustes"), no acento do app.

/** Busca: palavras (BM25) e significado (vetor) se cruzam na híbrida. */
export const HybridArt = () => (
  <div className="adv-art">
    <svg width="118" height="56" viewBox="0 0 118 56" fill="none" aria-hidden="true" focusable="false">
      <circle cx="42" cy="28" r="22" fill="currentColor" fillOpacity=".1" stroke="currentColor" strokeOpacity=".5" />
      <circle cx="76" cy="28" r="22" fill="currentColor" fillOpacity=".1" stroke="currentColor" strokeOpacity=".5" />
      <path className="adv-art__mix" d="M59 14.1a22 22 0 0 1 0 27.8a22 22 0 0 1 0-27.8Z" fill="currentColor" fillOpacity=".55" />
      <text x="22" y="31" fontSize="8" fill="var(--text-secondary)" fontFamily="var(--font-family)">BM25</text>
      <text x="80" y="31" fontSize="8" fill="var(--text-secondary)" fontFamily="var(--font-family)">vetor</text>
    </svg>
    <span>A híbrida junta a busca por palavras e a por significado e ordena tudo junto (RRF).</span>
  </div>
);

const DOTS = [[18, 22], [40, 64], [62, 30], [84, 72], [104, 18], [128, 56], [150, 76], [176, 24], [204, 66], [226, 34], [252, 74], [262, 16], [112, 84], [30, 80]];
const NEAR = [[150, 46], [172, 58], [138, 32]];

/** Busca semântica: a pergunta vira um ponto e os trechos mais próximos voltam. */
export const VectorArt = () => (
  <div className="adv-art adv-art--stack">
    <svg viewBox="0 0 280 92" width="100%" height="84" fill="none" aria-hidden="true" focusable="false">
      {DOTS.map(([x, y]) => <circle key={`${x}-${y}`} cx={x} cy={y} r="3" fill="var(--border-color)" />)}
      {NEAR.map(([x, y], i) => (
        <g key={`${x}-${y}`} className="adv-art__near" style={{ animationDelay: `${i * 0.25}s` }}>
          <path d={`M158 50L${x} ${y}`} stroke="currentColor" strokeOpacity=".6" strokeDasharray="2 3" />
          <circle cx={x} cy={y} r="4" fill="currentColor" fillOpacity=".85" />
        </g>
      ))}
      <circle className="adv-art__query" cx="158" cy="50" r="12" stroke="currentColor" strokeOpacity=".35" />
      <path d="M158 43l2 5 5 2-5 2-2 5-2-5-5-2 5-2Z" fill="currentColor" />
    </svg>
    <span>A pergunta vira um ponto; os trechos mais próximos dele voltam.</span>
  </div>
);

/** Trechos: três trechos vizinhos com a sobreposição em destaque, nos valores salvos. */
export const ChunkArt = ({ size, overlap }: { size: number; overlap: number }) => {
  const ratio = size > 0 ? Math.min(0.45, overlap / size) : 0.15;
  const w = 118;
  const o = Math.round(w * ratio);
  const xs = [2, 2 + w - o, 2 + 2 * (w - o)];
  return (
    <div className="adv-art adv-art--stack">
      <svg viewBox="0 0 300 36" width="100%" height="36" fill="none" aria-hidden="true" focusable="false">
        {xs.map((x) => <rect key={x} x={x} y="6" width={Math.min(w, 298 - x)} height="24" rx="6" fill="currentColor" fillOpacity=".14" stroke="currentColor" strokeOpacity=".55" />)}
        {xs.slice(1).map((x) => <rect key={`o${x}`} className="adv-art__overlap" x={x} y="6" width={o} height="24" fill="currentColor" fillOpacity=".45" />)}
      </svg>
      <span>{size.toLocaleString('pt-BR')} caracteres por trecho; os {overlap.toLocaleString('pt-BR')} em destaque se repetem entre vizinhos.</span>
    </div>
  );
};
