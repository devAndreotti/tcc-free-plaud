export type ThemeChoice = 'dark' | 'light' | 'system';

import { readMigratedItem } from './services/localStorageMigration';

const STORAGE_KEY = 'escolio:theme';
const LEGACY_STORAGE_KEY = 'free-plaud:theme';

export function readThemeChoice(): ThemeChoice {
  try {
    const stored = readMigratedItem(STORAGE_KEY, LEGACY_STORAGE_KEY);
    if (stored === 'dark' || stored === 'light' || stored === 'system') return stored;
  } catch {
    // Armazenamento bloqueado: segue com o padrão.
  }
  return 'dark';
}

export function applyTheme(choice: ThemeChoice): void {
  const prefersLight = window.matchMedia?.('(prefers-color-scheme: light)').matches ?? false;
  const light = choice === 'light' || (choice === 'system' && prefersLight);
  document.documentElement.dataset.theme = light ? 'light' : 'dark';
}

export function saveThemeChoice(choice: ThemeChoice): void {
  try {
    window.localStorage.setItem(STORAGE_KEY, choice);
  } catch {
    // Sem persistência: o tema vale só para esta sessão.
  }
  applyTheme(choice);
}
