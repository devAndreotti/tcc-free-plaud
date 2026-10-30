/** Nomes, ordem e formatação pt-BR compartilhados pelo painel de benchmark e suas seções. */

export const STRATEGY_ORDER = ['lexical', 'vector', 'hybrid'];

export const STRATEGY_NAME: Record<string, { label: string; lower: string; sub: string }> = {
  lexical: { label: 'Lexical', lower: 'lexical', sub: 'busca por palavras' },
  vector: { label: 'Vetorial', lower: 'vetorial', sub: 'modelo de busca semântica' },
  hybrid: { label: 'Híbrida', lower: 'híbrida', sub: 'RRF' },
};

export const nameOf = (strategy: string) => STRATEGY_NAME[strategy] ?? { label: strategy, lower: strategy, sub: '' };
export const fmt3 = (v: number) => v.toLocaleString('pt-BR', { minimumFractionDigits: 3, maximumFractionDigits: 3 });
export const fmt2 = (v: number) => v.toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
export const pct = (v: number) => (v * 100).toLocaleString('pt-BR', { maximumFractionDigits: 1 });
export const ms = (v: number) => `${v.toLocaleString('pt-BR', { maximumFractionDigits: 1 })} ms`;

/** Número finito (rejeita NaN, Infinity, null e undefined vindos do backend). */
export const isFiniteNumber = (v: unknown): v is number => typeof v === 'number' && Number.isFinite(v);

/** Limita a [0, 1] para largura de barra. */
export const clamp01 = (v: number) => Math.max(0, Math.min(1, v));

/** Largura CSS de uma barra que representa uma fração de 0 a 1. */
export const barWidth = (v: number) => `${clamp01(v) * 100}%`;

/** Intervalo válido: os dois extremos finitos e na ordem certa. */
export const validInterval = (lower: unknown, upper: unknown): lower is number =>
  isFiniteNumber(lower) && isFiniteNumber(upper) && lower <= upper;

/** Texto do intervalo, no mesmo formato da tabela: 0,86–0,96. */
export const intervalText = (lower: number, upper: number) => `${fmt2(lower)}–${fmt2(upper)}`;
