// Desenhos dos grupos do Avançado (canvas "Avançado · presets e ajustes"), no acento do app.

// Lexical: linhas de texto com as palavras exatas da pergunta acesas.
const LexicalDrawing = () => (
  <svg viewBox="0 0 96 56" width="96" height="56" fill="none" aria-hidden="true" focusable="false">
    {[[8, 38, 46, 24], [8, 20, 34, 34, 60, 28], [8, 52, 66, 22]].map((row, y) =>
      row.reduce<number[][]>((pairs, _, i) => (i % 2 ? pairs : [...pairs, [row[i], row[i + 1]]]), []).map(([x, width]) => (
        <rect key={`${y}-${x}`} x={x} y={10 + y * 15} width={width} height="6" rx="3" fill="currentColor" fillOpacity=".22" />
      ))
    )}
    <rect className="adv-art__word" x="46" y="8" width="24" height="10" rx="3" fill="currentColor" fillOpacity=".75" />
    <rect className="adv-art__word" x="34" y="23" width="26" height="10" rx="3" fill="currentColor" fillOpacity=".75" />
  </svg>
);

// Vetorial: a pergunta é um ponto, e os trechos de sentido parecido estão perto dela.
const VectorDrawing = () => (
  <svg viewBox="0 0 96 56" width="96" height="56" fill="none" aria-hidden="true" focusable="false">
    {[[10, 12], [24, 44], [80, 10], [86, 42], [12, 34], [70, 48]].map(([x, y]) => (
      <circle key={`${x}-${y}`} cx={x} cy={y} r="2.5" fill="currentColor" fillOpacity=".25" />
    ))}
    {[[36, 18], [62, 20], [56, 40]].map(([x, y]) => (
      <g key={`${x}-${y}`}>
        <path d={`M48 28L${x} ${y}`} stroke="currentColor" strokeOpacity=".55" strokeDasharray="2 2" />
        <circle cx={x} cy={y} r="3.5" fill="currentColor" fillOpacity=".8" />
      </g>
    ))}
    <circle className="adv-art__query" cx="48" cy="28" r="8" stroke="currentColor" strokeOpacity=".4" />
    <circle cx="48" cy="28" r="3.5" fill="currentColor" />
  </svg>
);

// Híbrida: palavras e significado se cruzam.
const HybridDrawing = () => (
  <svg viewBox="0 0 96 56" width="96" height="56" fill="none" aria-hidden="true" focusable="false">
    <circle cx="35" cy="28" r="21" fill="currentColor" fillOpacity=".12" stroke="currentColor" strokeOpacity=".5" />
    <circle cx="61" cy="28" r="21" fill="currentColor" fillOpacity=".12" stroke="currentColor" strokeOpacity=".5" />
    <path className="adv-art__mix" d="M48 11.5a21 21 0 0 1 0 33a21 21 0 0 1 0-33Z" fill="currentColor" fillOpacity=".55" />
  </svg>
);

const SEARCH_KINDS = [
  { id: 'lexical', label: 'Lexical', Drawing: LexicalDrawing, text: 'A lexical procura as palavras exatas da pergunta (FTS5). É a mais rápida.' },
  { id: 'vector', label: 'Vetorial', Drawing: VectorDrawing, text: 'A vetorial busca por significado: acha o trecho mesmo sem as palavras exatas.' },
  { id: 'hybrid', label: 'Híbrida', Drawing: HybridDrawing, text: 'A híbrida junta a busca por palavras e a por significado e ordena tudo junto (RRF).' },
];

/** Busca: as três estratégias lado a lado, com a escolhida em destaque e explicada embaixo. */
export const SearchArt = ({ strategy }: { strategy: string }) => {
  const chosen = SEARCH_KINDS.find((kind) => kind.id === strategy) ?? SEARCH_KINDS[2];
  return (
    <div className="adv-art adv-art--stack">
      <ul className="adv-search">
        {SEARCH_KINDS.map(({ id, label, Drawing }) => (
          <li key={id} className={`adv-search__kind${id === chosen.id ? ' is-on' : ''}`} aria-current={id === chosen.id || undefined}>
            <Drawing />
            <b>{label}</b>
          </li>
        ))}
      </ul>
      <span>{chosen.text}</span>
    </div>
  );
};

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
