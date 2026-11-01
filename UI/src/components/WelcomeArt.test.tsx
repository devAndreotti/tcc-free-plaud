import { cleanup, render } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';
import type { Vault } from '../services/bridge';
import WelcomeScreen from './WelcomeScreen';

const base = { embedding_model: 'chroma-default', created_at: '2026-10-18T12:00:00-03:00', sqlite_path: null, vector_store_dir: null };
const OBSIDIAN: Vault = { ...base, id: 'obsidian', name: 'Obsidian', icon: 'notes', color: 'amber', folders: [], note_count: 632, roots: [] };
const LEITURAS: Vault = { ...base, id: 'leituras', name: 'Leituras', icon: 'layers', color: 'violet', folders: [], note_count: 0, roots: [] };

const colorOf = (el: Element | null) => [...(el?.classList ?? [])].find((c) => c.startsWith('vault-glyph--'));

describe('tela inicial: arte na cor da vault', () => {
  afterEach(cleanup);

  it('a arte usa a cor da vault ativa e acompanha a troca de cor e de vault', () => {
    const { container, rerender } = render(<WelcomeScreen vault={OBSIDIAN} />);
    const art = () => container.querySelector('.welcome-art');

    expect(colorOf(art())).toBe('vault-glyph--amber');
    expect(colorOf(container.querySelector('.vault-glyph'))).toBe('vault-glyph--amber');
    expect(art()?.querySelector('svg')?.getAttribute('aria-hidden')).toBe('true');
    expect(art()?.querySelectorAll('.welcome-art__thread')).toHaveLength(4);

    rerender(<WelcomeScreen vault={{ ...OBSIDIAN, color: 'rose' }} />);
    expect(colorOf(art())).toBe('vault-glyph--rose');

    rerender(<WelcomeScreen vault={LEITURAS} />);
    expect(colorOf(art())).toBe('vault-glyph--violet');
    expect(art()?.classList.contains('welcome-art--empty')).toBe(true);
    expect(art()?.querySelectorAll('.welcome-art__thread')).toHaveLength(0);
  });

  it('sem vault carregada, a arte fica sem cor de vault (usa o acento do app)', () => {
    const { container } = render(<WelcomeScreen />);
    expect(colorOf(container.querySelector('.welcome-art'))).toBeUndefined();
  });
});
