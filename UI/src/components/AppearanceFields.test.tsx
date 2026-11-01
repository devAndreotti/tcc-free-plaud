import { cleanup, render, screen, within } from '@testing-library/react';
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

  it('troca tamanho do texto, densidade e tema pelos controles com indicador e miniaturas', async () => {
    const user = userEvent.setup();
    render(<AppearanceFields />);

    const size = screen.getByRole('radiogroup', { name: 'Tamanho do texto' });
    await user.click(within(size).getByRole('radio', { name: '125%' }));
    await user.click(within(screen.getByRole('radiogroup', { name: 'Densidade' })).getByRole('radio', { name: 'Compacta' }));
    await user.click(within(screen.getByRole('radiogroup', { name: 'Tema' })).getByRole('radio', { name: 'Claro' }));

    expect(within(size).getByRole('radio', { name: '125%' }).getAttribute('aria-checked')).toBe('true');
    expect(size.style.getPropertyValue('--i')).toBe('3');
    expect(document.documentElement.dataset).toMatchObject({ textSize: '125', density: 'compact', theme: 'light' });
    expect(readAppearance()).toMatchObject({ textSize: '125', density: 'compact', accent: 'violet' });
  });

  it('Reduzir animações diz o que vale agora e grava a escolha', async () => {
    const user = userEvent.setup();
    render(<AppearanceFields />);

    await user.click(within(screen.getByRole('radiogroup', { name: 'Reduzir animações' })).getByRole('radio', { name: 'Sempre' }));

    expect(screen.getByRole('status').textContent).toContain('Animações desligadas em todo o app.');
    expect(document.documentElement.dataset.motion).toBe('always');
  });
});
