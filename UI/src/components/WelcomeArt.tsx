import type { ReactNode } from 'react';
import type { VaultColor } from '../services/bridge';
import './WelcomeArt.css';

// Notas em volta da vault, cada uma presa ao centro por um fio de citação que sai do trecho destacado.
// viewBox 440×200, centro (220,100); cartões de 56 de altura girados em torno do próprio centro.
// anchor = meio da borda voltada ao centro, já com a rotação; thread vai da âncora até o anel (r=46).
const CARDS = [
  { x: 38, y: 24, w: 84, r: -7, anchor: [121.7, 46.9], thread: 'M121.7 46.9C150.6 46.9 150.6 78.1 179.5 78.1' },
  { x: 78, y: 122, w: 72, r: 5, anchor: [149.9, 153.1], thread: 'M149.9 153.1C166.6 153.1 166.6 127.8 183.3 127.8' },
  { x: 318, y: 18, w: 84, r: 6, anchor: [318.2, 41.6], thread: 'M318.2 41.6C288.9 41.6 288.9 76.5 259.5 76.5' },
  { x: 296, y: 124, w: 76, r: -4, anchor: [296.1, 154.7], thread: 'M296.1 154.7C276.7 154.7 276.7 126.8 257.4 126.8' },
] as const;

// [x, y, raio, atraso do brilho em s (só nos que piscam)]
const STARS: [number, number, number, number?][] = [
  [24, 108, 1.6, 0], [168, 24, 1.3], [198, 178, 1.2], [270, 16, 1.6, 1.2], [414, 114, 1.4, 2.4],
  [252, 186, 1.1], [140, 98, 1.1], [300, 96, 1.2], [432, 170, 1.2], [10, 40, 1.1],
];

interface WelcomeArtProps {
  /** Cor da vault ativa; sem ela, a arte usa o acento do app. */
  color?: VaultColor;
  /** Vault sem notas: cartões em branco e sem fios. */
  empty?: boolean;
  /** Fica no centro da arte (ícone da vault). */
  children?: ReactNode;
}

/** Arte da tela inicial na cor da vault: a mesma classe vault-glyph--<cor> do VaultGlyph define --vault-color. */
const WelcomeArt = ({ color, empty = false, children }: WelcomeArtProps) => (
  <div className={['welcome-art', empty && 'welcome-art--empty', color && `vault-glyph--${color}`].filter(Boolean).join(' ')}>
    <svg
      className="welcome-art__svg"
      viewBox="0 0 440 200"
      fill="none"
      stroke="currentColor"
      strokeLinecap="round"
      aria-hidden="true"
      focusable="false"
    >
      <circle className="welcome-art__halo" cx="220" cy="100" r="62" strokeOpacity=".18" strokeDasharray="2 6" />
      <circle
        cx="220"
        cy="100"
        r="46"
        fill="currentColor"
        fillOpacity=".05"
        strokeOpacity={empty ? 0.32 : 0.24}
        strokeDasharray={empty ? '3 5' : undefined}
      />
      {STARS.map(([x, y, r, delay]) => (
        <circle
          key={`${x}-${y}`}
          className={delay === undefined || empty ? undefined : 'welcome-art__star'}
          style={delay === undefined ? undefined : { animationDelay: `${delay}s` }}
          cx={x}
          cy={y}
          r={r}
          fill="currentColor"
          fillOpacity={empty ? 0.3 : 0.6}
          stroke="none"
        />
      ))}
      {CARDS.map(({ x, y, w, r, anchor, thread }) => (
        <g key={thread}>
          {!empty && <path className="welcome-art__thread" d={thread} strokeOpacity=".7" strokeWidth="1.4" strokeDasharray="1 5" />}
          <g transform={`rotate(${r} ${x + w / 2} ${y + 28})`}>
            <rect
              x={x}
              y={y}
              width={w}
              height="56"
              rx="7"
              fill={empty ? 'none' : 'currentColor'}
              fillOpacity=".07"
              strokeOpacity={empty ? 0.4 : 0.45}
              strokeWidth="1.2"
              strokeDasharray={empty ? '4 4' : undefined}
            />
            {!empty && (
              <>
                <path d={`M${x + 10} ${y + 12}h${Math.round(w * 0.45)}`} strokeOpacity=".55" strokeWidth="2.6" />
                <path
                  d={`M${x + 10} ${y + 21}H${x + w - 12}M${x + 10} ${y + 37}H${x + w - 18}M${x + 10} ${y + 45}h${Math.round(w * 0.4)}`}
                  strokeOpacity=".28"
                  strokeWidth="1.6"
                />
                <rect x={x + 6} y={y + 23.5} width={w - 12} height="9" rx="3" fill="currentColor" fillOpacity=".2" stroke="none" />
                <path d={`M${x + 10} ${y + 28}H${x + w - 14}`} strokeOpacity=".95" strokeWidth="1.8" />
              </>
            )}
          </g>
          {!empty && (
            <>
              <circle cx={anchor[0]} cy={anchor[1]} r="5" strokeOpacity=".35" />
              <circle cx={anchor[0]} cy={anchor[1]} r="2.6" fill="currentColor" stroke="none" />
            </>
          )}
        </g>
      ))}
    </svg>
    <div className="welcome-art__center">{children}</div>
  </div>
);

export default WelcomeArt;
