import { useState, type ReactNode } from 'react';
import { readAppearance, saveAppearance, type Appearance } from '../appearance';
import { readThemeChoice, saveThemeChoice, type ThemeChoice } from '../theme';
import type { NoteIconsMode } from '../lib/noteIcons';
import { NoteTitle } from './NoteTitle';
import { GroupCard, Segmented } from './ui/Controls';
import './AppearanceFields.css';

// Amostra em tom médio, legível nos dois temas; os tokens de verdade ficam em appearance.css.
const ACCENTS: Record<Appearance['accent'], { label: string; swatch: string }> = {
  violet: { label: 'Violeta', swatch: '#7c62ea' },
  indigo: { label: 'Índigo', swatch: '#6366f1' },
  blue: { label: 'Azul', swatch: '#3b82f6' },
  cyan: { label: 'Ciano', swatch: '#06b6d4' },
  teal: { label: 'Verde-azulado', swatch: '#14b8a6' },
  green: { label: 'Verde', swatch: '#22c55e' },
  lime: { label: 'Lima', swatch: '#84cc16' },
  amber: { label: 'Âmbar', swatch: '#f59e0b' },
  orange: { label: 'Laranja', swatch: '#f97316' },
  red: { label: 'Vermelho', swatch: '#ef4444' },
  rose: { label: 'Rosa', swatch: '#f43f5e' },
  fuchsia: { label: 'Magenta', swatch: '#d946ef' },
};

const NOTE_ICON_OPTIONS: { value: NoteIconsMode; label: string }[] = [
  { value: 'svg', label: 'Ícone do app' },
  { value: 'original', label: 'Emoji original' },
  { value: 'none', label: 'Sem ícone' },
];
const NOTE_ICON_SAMPLES = ['❤️ Saúde', '🧠 Estudos'];

const prefersReducedMotion = () => {
  try {
    return window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  } catch {
    return false;
  }
};

/** Miniatura de janela no tema: escuro, claro ou metade de cada (sistema). */
const WindowThumb = ({ kind }: { kind: ThemeChoice }) => {
  const body = (bg: string, side: string, line: string) => (
    <>
      <rect width="120" height="72" fill={bg} />
      <rect width="26" height="72" fill={side} />
      <rect x="36" y="14" width="56" height="5" rx="2.5" fill={line} />
      <rect x="36" y="26" width="72" height="4" rx="2" fill={line} />
      <rect x="36" y="35" width="64" height="4" rx="2" fill={line} />
      <rect x="36" y="52" width="30" height="10" rx="5" className="ap-thumb__accent" />
      <circle cx="13" cy="14" r="4" className="ap-thumb__accent" />
    </>
  );
  return (
    <svg className="ap-thumb" viewBox="0 0 120 72" aria-hidden="true" focusable="false">
      {kind !== 'light' && body('#141319', '#101015', '#3a3944')}
      {kind === 'light' && body('#fbfbfc', '#efeef3', '#d6d5de')}
      {kind === 'system' && <g style={{ clipPath: 'inset(0 0 0 50%)' }}>{body('#fbfbfc', '#efeef3', '#d6d5de')}</g>}
    </svg>
  );
};

const DensityThumb = ({ gap }: { gap: number }) => (
  <svg className="ap-thumb" viewBox="0 0 120 64" aria-hidden="true" focusable="false">
    {[0, 1, 2, 3, 4].map((i) => (
      <rect key={i} x="10" y={8 + i * gap} width={i % 2 ? 78 : 100} height={gap > 12 ? 7 : 5} rx="2.5" className={i === 0 ? 'ap-thumb__accent' : 'ap-thumb__line'} />
    ))}
  </svg>
);

interface TilesProps<T extends string> {
  label: string;
  value: T;
  options: { value: T; label: string; art: ReactNode }[];
  onChange: (value: T) => void;
}

const Tiles = <T extends string>({ label, value, options, onChange }: TilesProps<T>) => (
  <div className="ap-tiles" role="radiogroup" aria-label={label}>
    {options.map((option) => (
      <button key={option.value} type="button" role="radio" aria-checked={option.value === value} className="ap-tile ui-tile" onClick={() => onChange(option.value)}>
        {option.art}
        <span>{option.label}</span>
      </button>
    ))}
  </div>
);

/** Aparência inteira: cada troca grava e aplica na hora, e a prévia usa os tokens reais do app. */
const AppearanceFields = () => {
  const [appearance, setAppearance] = useState<Appearance>(readAppearance);
  const [theme, setTheme] = useState<ThemeChoice>(readThemeChoice);
  const systemReduces = prefersReducedMotion();

  const update = (patch: Partial<Appearance>) => {
    const next = { ...appearance, ...patch };
    setAppearance(next);
    saveAppearance(next);
  };

  const reduced = appearance.motion === 'always' || (appearance.motion === 'system' && systemReduces);
  const motionNote =
    appearance.motion === 'system'
      ? `Segue o Windows: animações ${systemReduces ? 'reduzidas' : 'ligadas'}.`
      : reduced
        ? 'Animações desligadas em todo o app.'
        : 'Animações sempre ligadas.';

  return (
    <div className="ap ui-grid">
      <GroupCard icon="moon" title="Tema" desc="Claro, escuro ou o mesmo do Windows." className="ap--wide" delay={0}>
        <Tiles<ThemeChoice>
          label="Tema"
          value={theme}
          onChange={(choice) => {
            setTheme(choice);
            saveThemeChoice(choice);
          }}
          options={[
            { value: 'dark', label: 'Escuro', art: <WindowThumb kind="dark" /> },
            { value: 'light', label: 'Claro', art: <WindowThumb kind="light" /> },
            { value: 'system', label: 'Sistema', art: <WindowThumb kind="system" /> },
          ]}
        />
      </GroupCard>

      <GroupCard icon="palette" title="Cor de destaque" desc="Botões, seleção e realces. Cada vault mantém a cor própria." className="ap--wide" delay={60}>
        <div className="appearance-swatches" role="group" aria-label="Cor de destaque">
          {(Object.keys(ACCENTS) as Appearance['accent'][]).map((accent) => (
            <button
              key={accent}
              type="button"
              className="appearance-swatch"
              style={{ color: ACCENTS[accent].swatch }}
              aria-label={ACCENTS[accent].label}
              aria-pressed={appearance.accent === accent}
              title={ACCENTS[accent].label}
              onClick={() => update({ accent })}
            />
          ))}
        </div>
      </GroupCard>

      <GroupCard icon="type" title="Tamanho do texto" desc="Amplia ou reduz toda a interface." delay={120}>
        <Segmented
          label="Tamanho do texto"
          value={appearance.textSize}
          onChange={(textSize) => update({ textSize })}
          options={(['90', '100', '110', '125'] as const).map((value) => ({ value, label: `${value}%` }))}
        />
      </GroupCard>

      <GroupCard icon="zap" title="Reduzir animações" desc="Transições, aberturas e o movimento do grafo." delay={160}>
        <Segmented
          label="Reduzir animações"
          value={appearance.motion}
          onChange={(motion) => update({ motion })}
          options={[
            { value: 'system', label: 'Seguir o sistema' },
            { value: 'always', label: 'Sempre' },
            { value: 'never', label: 'Nunca' },
          ]}
        />
        <p className="ap-note" role="status">
          <span className={`ap-note__dot${reduced ? '' : ' ap-note__dot--on'}`} aria-hidden="true" />
          {motionNote}
        </p>
      </GroupCard>

      <GroupCard icon="font" title="Fonte das respostas" desc="Letra do texto de leitura nas respostas e nas notas." delay={200}>
        <Tiles<Appearance['readingFont']>
          label="Fonte das respostas"
          value={appearance.readingFont}
          onChange={(readingFont) => update({ readingFont })}
          options={[
            { value: 'serif', label: 'Serifada', art: <span className="ap-font ap-font--serif">Aa</span> },
            { value: 'sans', label: 'Sem serifa', art: <span className="ap-font ap-font--sans">Aa</span> },
          ]}
        />
      </GroupCard>

      <GroupCard icon="rows" title="Densidade" desc="Espaço entre mensagens, notas e itens da barra lateral." delay={240}>
        <Tiles<Appearance['density']>
          label="Densidade"
          value={appearance.density}
          onChange={(density) => update({ density })}
          options={[
            { value: 'comfortable', label: 'Confortável', art: <DensityThumb gap={13} /> },
            { value: 'compact', label: 'Compacta', art: <DensityThumb gap={9} /> },
          ]}
        />
      </GroupCard>

      <GroupCard icon="notes" title="Ícones nos títulos" desc="Emojis nos títulos das notas, nas fontes do chat e no grafo. O texto dentro das notas não muda." className="ap--wide" delay={280}>
        <Tiles<NoteIconsMode>
          label="Ícones nos títulos"
          value={appearance.noteIcons}
          onChange={(noteIcons) => update({ noteIcons })}
          options={NOTE_ICON_OPTIONS.map(({ value, label }) => ({
            value,
            label,
            art: (
              <span className="ap-noteicons">
                {NOTE_ICON_SAMPLES.map((sample) => (
                  <span key={sample}><NoteTitle text={sample} mode={value} /></span>
                ))}
              </span>
            ),
          }))}
        />
      </GroupCard>

      <GroupCard icon="stars" title="Prévia ao vivo" desc="Cada escolha acima muda esta prévia na hora." className="ap--wide" delay={320}>
        <div className="ap-preview" aria-label="Prévia da aparência">
          <div className="ap-preview__q">O que a busca híbrida faz?</div>
          <div className="ap-preview__a">
            Ela junta a busca por palavras e a por significado e ordena os trechos juntos <span className="mono">[1]</span>.
          </div>
          <div className="ap-preview__job">
            <span className="ap-preview__orbit ui-spin" aria-hidden="true" />
            <span className="ap-preview__dots" aria-hidden="true"><i /><i /><i /></span>
            <span className="ap-preview__bar"><span className="ui-stripes" /></span>
            <span className="mono">62%</span>
          </div>
        </div>
      </GroupCard>
    </div>
  );
};

export default AppearanceFields;
