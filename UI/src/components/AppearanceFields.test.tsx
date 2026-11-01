import { cleanup, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it } from 'vitest';
import AppearanceFields from './AppearanceFields';
import { applyAppearance, DEFAULT_APPEARANCE, readAppearance } from '../appearance';

describe('AppearanceFields', () => {
  afterEach(() => {
    cleanup();
    window.localStorage.clear();
    applyAppearance(DEFAULT_APPEARANCE);
  });

  it('troca a cor de destaque pelas amostras e grava na hora', async () => {
    const user = userEvent.setup();
    render(<AppearanceFields />);

    const group = screen.getByRole('group', { name: 'Cor de destaque' });
    expect(screen.getByRole('button', { name: 'Violeta' }).getAttribute('aria-pressed')).toBe('true');
    expect(group.querySelectorAll('button')).toHaveLength(6);

    await user.click(screen.getByRole('button', { name: 'Âmbar' }));

    expect(screen.getByRole('button', { name: 'Âmbar' }).getAttribute('aria-pressed')).toBe('true');
    expect(screen.getByRole('button', { name: 'Violeta' }).getAttribute('aria-pressed')).toBe('false');
    expect(document.documentElement.dataset.accent).toBe('amber');
    expect(readAppearance().accent).toBe('amber');
  });

  it('troca tamanho do texto e densidade pelos selects', async () => {
    const user = userEvent.setup();
    render(<AppearanceFields />);

    await user.click(screen.getByRole('combobox', { name: 'Tamanho do texto' }));
    await user.click(screen.getByRole('option', { name: '125%' }));
    await user.click(screen.getByRole('combobox', { name: 'Densidade' }));
    await user.click(screen.getByRole('option', { name: 'Compacta' }));

    expect(screen.getByRole('combobox', { name: 'Tamanho do texto' }).textContent).toContain('125%');
    expect(document.documentElement.dataset).toMatchObject({ textSize: '125', density: 'compact' });
    expect(readAppearance()).toMatchObject({ textSize: '125', density: 'compact', accent: 'violet' });
  });
});
