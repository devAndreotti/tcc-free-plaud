import { Sk } from './ui/Loading';
import './BenchEmpty.css';

// Três colunas (palavras, significado, híbrida) que crescem; perguntas descem do conjunto até elas.
const COLS = [
  { x: 128, h: 70, label: 'Palavras' },
  { x: 188, h: 54, label: 'Significado' },
  { x: 248, h: 92, label: 'Híbrida' },
];

const BenchArt = ({ running }: { running: boolean }) => (
  <svg className={`bench-art${running ? ' bench-art--running' : ''}`} viewBox="0 0 380 200" fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" focusable="false">
    <path d="M96 170H312" strokeOpacity=".35" strokeWidth="1.6" />
    {[130, 100, 70].map((y) => <path key={y} d={`M96 ${y}H312`} strokeOpacity=".1" strokeWidth="1" strokeDasharray="2 6" />)}
    {COLS.map((col, i) => (
      <g key={col.label}>
        <rect className={`bench-art__col bench-art__col--${i + 1}`} x={col.x} y={170 - col.h} width="34" height={col.h} rx="6" fill="currentColor" fillOpacity={i === 2 ? 0.32 : 0.14} strokeOpacity={i === 2 ? 0.9 : 0.5} strokeWidth="1.6" />
        <text x={col.x + 17} y="188" textAnchor="middle" fontSize="9.5" fill="currentColor" fillOpacity=".6" stroke="none" fontFamily="var(--font-family)">{col.label}</text>
      </g>
    ))}
    <g className="bench-art__suite">
      <rect x="22" y="40" width="54" height="66" rx="6" fill="var(--bg-primary)" strokeOpacity=".7" strokeWidth="1.6" />
      <path d="M32 56h22M32 66h30M32 76h26M32 86h18" strokeOpacity=".45" strokeWidth="1.6" />
      <text x="49" y="122" textAnchor="middle" fontSize="9.5" fill="currentColor" fillOpacity=".6" stroke="none" fontFamily="var(--font-mono)">suite.json</text>
    </g>
    <path className="bench-art__trail" d="M80 66C130 20 220 20 266 64" strokeOpacity=".4" strokeWidth="1.4" />
    {[1, 2, 3].map((n) => <circle key={n} className={`bench-art__q bench-art__q--${n}`} cx="80" cy="66" r="4" fill="currentColor" stroke="none" />)}
    <g className="bench-art__star">
      <path d="M265 52l2.4 6.6 6.6 2.4-6.6 2.4-2.4 6.6-2.4-6.6-6.6-2.4 6.6-2.4Z" fill="currentColor" stroke="none" />
    </g>
  </svg>
);

interface BenchEmptyProps {
  running: boolean;
}

const skCard = (title: string, rows: number, delay: number) => (
  <section className="card rise" style={{ animationDelay: `${delay}ms` }}>
    <div className="card__head"><h2>{title}</h2></div>
    <div className="load-wait" style={{ display: 'grid', gap: 12, padding: '4px 2px 10px' }}>
      {Array.from({ length: rows }, (_, i) => <Sk key={i} w={`${92 - (i % 3) * 14}%`} h={i % 2 ? 10 : 14} />)}
    </div>
  </section>
);

/** Enquanto a comparação roda: a mesma grade do resultado (frase, 4 números, pares de cards), já com os títulos. */
export const BenchLoading = () => (
  <div role="status" aria-label="Rodando a comparação" style={{ display: 'contents' }}>
    <div className="bench-lead load-wait">
      <div style={{ flex: 1, minWidth: 300, maxWidth: 780, display: 'grid', gap: 10 }}><Sk w="92%" h={20} /><Sk w="64%" h={20} /></div>
      <div className="load-row"><Sk w={64} h={30} r={999} /><Sk w={64} h={30} r={999} /></div>
    </div>
    <div className="bench-stats load-wait">
      {Array.from({ length: 4 }, (_, i) => (
        <div key={i} className="bench-stat"><Sk w="55%" h={11} /><Sk w="45%" h={26} r={8} /><Sk w="70%" h={11} /></div>
      ))}
    </div>
    <div className="bench-pair">{skCard('As três buscas', 6, 60)}{skCard('Responder ou recusar', 5, 120)}</div>
    {skCard('Por que errou', 3, 180)}
    <div className="bench-pair bench-pair--map">{skCard('Mapa das perguntas', 9, 240)}{skCard('Pergunta selecionada', 6, 300)}</div>
  </div>
);

/** Benchmark sem resultado ainda (ou rodando): arte no acento, título e o que a comparação faz. */
const BenchEmpty = ({ running }: BenchEmptyProps) => (
  <div className="card bench-empty" role={running ? 'status' : undefined}>
    <BenchArt running={running} />
    {running ? (
      <>
        <h2>Rodando lexical, vetorial e híbrida no mesmo conjunto de perguntas…</h2>
        <p>Cada documento da suite é indexado num corpus temporário antes das perguntas. Leva cerca de meio minuto.</p>
      </>
    ) : (
      <>
        <h2>Nenhum benchmark executado nesta sessão.</h2>
        <p>
          Escolha uma suite.json com perguntas e as notas esperadas. A comparação roda lexical, vetorial e híbrida
          com o mesmo top-k e grava os relatórios em JSON e CSV.
        </p>
      </>
    )}
  </div>
);

export default BenchEmpty;
