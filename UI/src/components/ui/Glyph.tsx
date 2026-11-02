import { GLYPHS, type GlyphName } from './glyphs';

export type { GlyphName };

interface GlyphProps {
  name: GlyphName;
  size?: number;
  strokeWidth?: number;
  className?: string;
}

export const Glyph = ({ name, size = 16, strokeWidth = 1.75, className }: GlyphProps) => (
  <svg
    className={className}
    width={size}
    height={size}
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth={strokeWidth}
    strokeLinecap="round"
    strokeLinejoin="round"
    aria-hidden="true"
    focusable="false"
  >
    <path d={GLYPHS[name]} />
  </svg>
);

/** Ícone num quadrado arredondado com o fundo suave do acento (ou de outro tom). */
export const GlyphBadge = ({ name, size = 32, tone = 'accent' }: { name: GlyphName; size?: number; tone?: 'accent' | 'ok' | 'warn' | 'err' | 'muted' }) => (
  <span className={`glyph-badge glyph-badge--${tone}`} style={{ width: size, height: size, borderRadius: Math.round(size * 0.3) }} aria-hidden="true">
    <Glyph name={name} size={Math.round(size * 0.5)} />
  </span>
);
