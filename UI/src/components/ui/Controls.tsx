import { useState, type CSSProperties, type ReactNode } from 'react';
import { Glyph, GlyphBadge, type GlyphName } from './Glyph';

export interface SegOption<T extends string> {
  value: T;
  label: string;
}

interface SegmentedProps<T extends string> {
  label: string;
  options: SegOption<T>[];
  value: T;
  onChange: (value: T) => void;
  disabled?: boolean;
}

/** Seletor de poucas opções com indicador que desliza até a escolhida. */
export const Segmented = <T extends string>({ label, options, value, onChange, disabled = false }: SegmentedProps<T>) => {
  const index = Math.max(0, options.findIndex((option) => option.value === value));
  return (
    <div className="ui-seg" role="radiogroup" aria-label={label} style={{ '--n': options.length, '--i': index } as CSSProperties}>
      <span className="ui-seg__ind" aria-hidden="true" />
      {options.map((option) => (
        <button
          key={option.value}
          type="button"
          role="radio"
          aria-checked={option.value === value}
          className="ui-seg__opt"
          disabled={disabled}
          onClick={() => onChange(option.value)}
        >
          {option.label}
        </button>
      ))}
    </div>
  );
};

interface StepperProps {
  label: string;
  /** Texto do campo (rascunho); − e + somam o passo ao número dele. */
  value: string;
  onChange: (value: string) => void;
  step?: number;
  min?: number;
  max?: number;
  unit?: string;
  disabled?: boolean;
}

const stepFor = (value: number) => {
  if (value >= 100) return value % 100 === 0 ? 100 : value % 64 === 0 ? 64 : 20;
  if (value >= 10) return value % 16 === 0 ? 16 : 10;
  return 1;
};

/** Número com − e +: o valor dá um pulinho a cada clique e o campo aceita digitação normal. */
export const Stepper = ({ label, value, onChange, step, min = 0, max, unit, disabled = false }: StepperProps) => {
  const [flip, setFlip] = useState<boolean | null>(null);
  const current = Number(value);
  const number = Number.isFinite(current) ? current : min;
  const delta = step ?? stepFor(number);
  const nudge = (direction: 1 | -1) => {
    const next = Math.min(max ?? Number.POSITIVE_INFINITY, Math.max(min, number + direction * delta));
    setFlip((prev) => !prev);
    onChange(String(next));
  };
  return (
    <div className="ui-stepper">
      <button type="button" aria-label={`Diminuir ${label}`} disabled={disabled || number <= min} onClick={() => nudge(-1)}>
        <Glyph name="minus" size={14} strokeWidth={2} />
      </button>
      <input
        className={flip === null ? undefined : flip ? 'bump-a' : 'bump-b'}
        type="number"
        inputMode="numeric"
        aria-label={label}
        value={value}
        min={min}
        max={max}
        disabled={disabled}
        onChange={(event) => onChange(event.target.value)}
      />
      {unit && <span className="ui-stepper__unit">{unit}</span>}
      <button type="button" aria-label={`Aumentar ${label}`} disabled={disabled || (max !== undefined && number >= max)} onClick={() => nudge(1)}>
        <Glyph name="plus" size={14} strokeWidth={2} />
      </button>
    </div>
  );
};

interface SectionHeadProps {
  icon: GlyphName;
  title: ReactNode;
  lede?: ReactNode;
  id?: string;
  children?: ReactNode;
}

/** Cabeçalho de seção: ícone no acento, título, linha de apoio e ações à direita. */
export const SectionHead = ({ icon, title, lede, id, children }: SectionHeadProps) => (
  <div className="ui-head rise">
    <GlyphBadge name={icon} size={40} />
    <div className="ui-head__text">
      <h3 id={id} className="ui-head__title">{title}</h3>
      {lede && <p className="ui-head__lede">{lede}</p>}
    </div>
    {children}
  </div>
);

interface GroupCardProps {
  icon: GlyphName;
  title: string;
  desc?: ReactNode;
  right?: ReactNode;
  tone?: 'accent' | 'ok' | 'err' | 'muted';
  delay?: number;
  className?: string;
  /** Falso quando o campo de dentro já tem o mesmo nome (evita dois elementos com o mesmo rótulo). */
  region?: boolean;
  children: ReactNode;
}

/** Cartão de um grupo de ajustes: entra em sequência (delay em ms) e sobe ao passar o mouse. */
export const GroupCard = ({ icon, title, desc, right, tone = 'accent', delay = 0, className = '', region = true, children }: GroupCardProps) => (
  <section className={`ui-card rise lift ${className}`} style={{ animationDelay: `${delay}ms` }} aria-label={region ? title : undefined}>
    <header className="ui-card__head">
      <GlyphBadge name={icon} size={32} tone={tone} />
      <div className="ui-card__titles">
        <h4 className="ui-card__title">{title}</h4>
        {desc && <p className="ui-card__desc">{desc}</p>}
      </div>
      {right}
    </header>
    {children}
  </section>
);
