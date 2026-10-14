import { afterEach, describe, expect, it, vi } from 'vitest';
import { applyTheme, readThemeChoice, saveThemeChoice } from './theme';

describe('theme', () => {
  afterEach(() => {
    window.localStorage.clear();
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it('lê a escolha salva e cai no escuro quando não há escolha válida', () => {
    expect(readThemeChoice()).toBe('dark');
    window.localStorage.setItem('escolio:theme', 'light');
    expect(readThemeChoice()).toBe('light');
    window.localStorage.setItem('escolio:theme', 'roxo');
    expect(readThemeChoice()).toBe('dark');
  });

  it('migra a escolha salva com a chave antiga free-plaud:theme', () => {
    window.localStorage.setItem('free-plaud:theme', 'light');
    expect(readThemeChoice()).toBe('light');
    expect(window.localStorage.getItem('escolio:theme')).toBe('light');
  });

  it('salva, aplica e segue o sistema quando a escolha é "system"', () => {
    saveThemeChoice('light');
    expect(window.localStorage.getItem('escolio:theme')).toBe('light');
    expect(document.documentElement.dataset.theme).toBe('light');

    vi.stubGlobal('matchMedia', (query: string) => ({ matches: query.includes('light') }));
    applyTheme('system');
    expect(document.documentElement.dataset.theme).toBe('light');
    applyTheme('dark');
    expect(document.documentElement.dataset.theme).toBe('dark');
  });

  it('continua funcionando com o armazenamento bloqueado', () => {
    vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
      throw new Error('bloqueado');
    });
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new Error('bloqueado');
    });

    expect(readThemeChoice()).toBe('dark');
    saveThemeChoice('light');
    expect(document.documentElement.dataset.theme).toBe('light');
  });
});
