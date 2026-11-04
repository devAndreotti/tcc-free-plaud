// Aparência além do tema: cor de destaque, tamanho do texto, fonte das respostas, densidade, animações e ícones nos títulos.
// Cada opção vira um atributo data-* no <html> (dataset.textSize → data-text-size); appearance.css faz o resto.
// O padrão não grava atributo, então sem escolha o app fica exatamente como era.

const OPTIONS = {
  accent: ['violet', 'indigo', 'blue', 'cyan', 'teal', 'green', 'lime', 'amber', 'orange', 'red', 'rose', 'fuchsia'],
  textSize: ['90', '100', '110', '125'],
  readingFont: ['serif', 'sans'],
  density: ['comfortable', 'compact'],
  motion: ['system', 'always', 'never'],
  noteIcons: ['svg', 'original', 'none'],
} as const;

export type Appearance = { [K in keyof typeof OPTIONS]: (typeof OPTIONS)[K][number] };

export const DEFAULT_APPEARANCE: Appearance = {
  accent: 'violet',
  textSize: '100',
  readingFont: 'serif',
  density: 'comfortable',
  motion: 'system',
  noteIcons: 'svg',
};

const STORAGE_KEY = 'escolio:appearance';
const KEYS = Object.keys(OPTIONS) as (keyof Appearance)[];

export function readAppearance(): Appearance {
  const appearance: Record<string, string> = { ...DEFAULT_APPEARANCE };
  try {
    const stored = JSON.parse(window.localStorage.getItem(STORAGE_KEY) ?? '{}');
    for (const key of KEYS) {
      const value = stored?.[key];
      if ((OPTIONS[key] as readonly string[]).includes(value)) appearance[key] = value;
    }
  } catch {
    // Armazenamento bloqueado ou valor corrompido: segue com o padrão.
  }
  return appearance as Appearance;
}

export function applyAppearance(appearance: Appearance): void {
  const { dataset } = document.documentElement;
  for (const key of KEYS) {
    if (appearance[key] === DEFAULT_APPEARANCE[key]) delete dataset[key];
    else dataset[key] = appearance[key];
  }
}

export function saveAppearance(appearance: Appearance): void {
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(appearance));
  } catch {
    // Sem persistência: a aparência vale só para esta sessão.
  }
  applyAppearance(appearance);
}
