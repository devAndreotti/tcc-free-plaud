import { afterEach, describe, expect, it, vi } from 'vitest';
import { applyAppearance, DEFAULT_APPEARANCE, readAppearance, saveAppearance } from './appearance';
import { prefersReducedMotion } from './lib/graphMotion';

const { dataset } = document.documentElement;

describe('appearance', () => {
  afterEach(() => {
    window.localStorage.clear();
    applyAppearance(DEFAULT_APPEARANCE);
    vi.restoreAllMocks();
  });

  it('lê o padrão e descarta valores inválidos campo a campo', () => {
    expect(readAppearance()).toEqual(DEFAULT_APPEARANCE);
    window.localStorage.setItem('escolio:appearance', JSON.stringify({ accent: 'rose', textSize: '300', density: 'compact' }));
    expect(readAppearance()).toEqual({ ...DEFAULT_APPEARANCE, accent: 'rose', density: 'compact' });
    window.localStorage.setItem('escolio:appearance', '{quebrado');
    expect(readAppearance()).toEqual(DEFAULT_APPEARANCE);
  });

  it('salva, aplica como data-* e remove o atributo ao voltar ao padrão', () => {
    const custom = { accent: 'cyan', textSize: '125', readingFont: 'sans', density: 'compact', motion: 'always' } as const;
    saveAppearance(custom);

    expect(readAppearance()).toEqual(custom);
    expect(dataset).toMatchObject({ accent: 'cyan', textSize: '125', readingFont: 'sans', density: 'compact', motion: 'always' });
    expect(document.documentElement.getAttribute('data-text-size')).toBe('125');

    saveAppearance(DEFAULT_APPEARANCE);
    for (const key of ['accent', 'textSize', 'readingFont', 'density', 'motion']) expect(dataset[key]).toBeUndefined();
  });

  it('o grafo segue "Reduzir animações": forçado vence o sistema', () => {
    vi.stubGlobal('matchMedia', () => ({ matches: true }));
    expect(prefersReducedMotion()).toBe(true);
    applyAppearance({ ...DEFAULT_APPEARANCE, motion: 'never' });
    expect(prefersReducedMotion()).toBe(false);
    vi.unstubAllGlobals();
    applyAppearance({ ...DEFAULT_APPEARANCE, motion: 'always' });
    expect(prefersReducedMotion()).toBe(true);
  });

  it('continua funcionando com o armazenamento bloqueado', () => {
    vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
      throw new Error('bloqueado');
    });
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new Error('bloqueado');
    });

    expect(readAppearance()).toEqual(DEFAULT_APPEARANCE);
    saveAppearance({ ...DEFAULT_APPEARANCE, accent: 'green' });
    expect(dataset.accent).toBe('green');
  });
});
