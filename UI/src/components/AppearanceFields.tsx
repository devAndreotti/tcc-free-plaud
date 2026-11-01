import { useState } from 'react';
import Select from './Select';
import { readAppearance, saveAppearance, type Appearance } from '../appearance';

// Amostra em tom médio, legível nos dois temas; os tokens de verdade ficam em appearance.css.
const ACCENTS: Record<Appearance['accent'], { label: string; swatch: string }> = {
  violet: { label: 'Violeta', swatch: '#7c62ea' },
  blue: { label: 'Azul', swatch: '#3b82f6' },
  green: { label: 'Verde', swatch: '#22c55e' },
  amber: { label: 'Âmbar', swatch: '#f59e0b' },
  rose: { label: 'Rosa', swatch: '#f43f5e' },
  cyan: { label: 'Ciano', swatch: '#06b6d4' },
};

const SELECTS: {
  key: Exclude<keyof Appearance, 'accent'>;
  label: string;
  description: string;
  options: { value: string; label: string }[];
}[] = [
  {
    key: 'textSize',
    label: 'Tamanho do texto',
    description: 'Amplia ou reduz toda a interface',
    options: ['90', '100', '110', '125'].map((value) => ({ value, label: `${value}%` })),
  },
  {
    key: 'readingFont',
    label: 'Fonte das respostas',
    description: 'Letra do texto de leitura nas respostas e nas notas',
    options: [
      { value: 'serif', label: 'Serifada (Source Serif)' },
      { value: 'sans', label: 'Sem serifa (IBM Plex Sans)' },
    ],
  },
  {
    key: 'density',
    label: 'Densidade',
    description: 'Espaço entre mensagens, notas e itens da barra lateral',
    options: [
      { value: 'comfortable', label: 'Confortável' },
      { value: 'compact', label: 'Compacta' },
    ],
  },
  {
    key: 'motion',
    label: 'Reduzir animações',
    description: 'Transições, aberturas e o movimento do grafo',
    options: [
      { value: 'system', label: 'Seguir o sistema' },
      { value: 'always', label: 'Sempre' },
      { value: 'never', label: 'Nunca' },
    ],
  },
];

/** Linhas da Aparência abaixo do Tema: cada troca grava e aplica na hora. */
const AppearanceFields = () => {
  const [appearance, setAppearance] = useState<Appearance>(readAppearance);

  const update = (patch: Partial<Appearance>) => {
    const next = { ...appearance, ...patch };
    setAppearance(next);
    saveAppearance(next);
  };

  return (
    <>
      <div className="settings-item">
        <div className="settings-item__info">
          <span className="settings-item__label" id="appearance-accent">Cor de destaque</span>
          <span className="settings-item__description">Botões, links, seleção e realces</span>
        </div>
        <div className="settings-item__control appearance-swatches" role="group" aria-labelledby="appearance-accent">
          {(Object.keys(ACCENTS) as Appearance['accent'][]).map((accent) => (
            <button
              key={accent}
              type="button"
              className="appearance-swatch"
              style={{ color: ACCENTS[accent].swatch }}
              aria-label={ACCENTS[accent].label}
              title={ACCENTS[accent].label}
              aria-pressed={appearance.accent === accent}
              onClick={() => update({ accent })}
            />
          ))}
        </div>
      </div>

      {SELECTS.map((row) => (
        <div key={row.key} className="settings-item">
          <div className="settings-item__info">
            <span className="settings-item__label">{row.label}</span>
            <span className="settings-item__description">{row.description}</span>
          </div>
          <div className="settings-item__control">
            <Select
              id={`select-${row.key}`}
              value={appearance[row.key]}
              onChange={(value) => update({ [row.key]: value } as Partial<Appearance>)}
              ariaLabel={row.label}
              options={row.options}
            />
          </div>
        </div>
      ))}
    </>
  );
};

export default AppearanceFields;
