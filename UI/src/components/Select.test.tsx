import { cleanup, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';
import Select, { type SelectOption } from './Select';

const OPTIONS: SelectOption[] = [
  { value: 'pt', label: 'Português' },
  { value: 'en', label: 'Inglês' },
  { value: 'auto', label: 'Automático', disabled: true },
];

describe('Select', () => {
  afterEach(() => {
    cleanup();
  });

  it('abre o menu ao clicar e mostra as opções', async () => {
    const user = userEvent.setup();
    render(<Select value="pt" options={OPTIONS} onChange={vi.fn()} ariaLabel="Idioma" />);

    expect(screen.queryByRole('listbox')).toBeNull();
    await user.click(screen.getByRole('combobox', { name: 'Idioma' }));

    expect(screen.getByRole('listbox')).toBeTruthy();
    expect(screen.getByRole('option', { name: 'Português' })).toBeTruthy();
    expect(screen.getByRole('option', { name: 'Inglês' })).toBeTruthy();
  });

  it('seleciona uma opção com clique e dispara onChange', async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(<Select value="pt" options={OPTIONS} onChange={onChange} ariaLabel="Idioma" />);

    await user.click(screen.getByRole('combobox', { name: 'Idioma' }));
    await user.click(screen.getByRole('option', { name: 'Inglês' }));

    expect(onChange).toHaveBeenCalledWith('en');
    expect(screen.queryByRole('listbox')).toBeNull();
  });

  it('não dispara onChange ao clicar em uma opção desabilitada', async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(<Select value="pt" options={OPTIONS} onChange={onChange} ariaLabel="Idioma" />);

    await user.click(screen.getByRole('combobox', { name: 'Idioma' }));
    await user.click(screen.getByRole('option', { name: 'Automático' }));

    expect(onChange).not.toHaveBeenCalled();
    // Opção desabilitada não fecha o menu (nenhuma seleção válida ocorreu).
    expect(screen.getByRole('listbox')).toBeTruthy();
  });

  it('navega e seleciona com teclado (ArrowDown + Enter)', async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(<Select value="pt" options={OPTIONS} onChange={onChange} ariaLabel="Idioma" />);

    const trigger = screen.getByRole('combobox', { name: 'Idioma' });
    trigger.focus();
    await user.keyboard('{ArrowDown}');
    expect(screen.getByRole('listbox')).toBeTruthy();

    await user.keyboard('{ArrowDown}');
    await user.keyboard('{Enter}');

    expect(onChange).toHaveBeenCalledWith('en');
  });

  it('fecha com Escape sem disparar onChange', async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(<Select value="pt" options={OPTIONS} onChange={onChange} ariaLabel="Idioma" />);

    await user.click(screen.getByRole('combobox', { name: 'Idioma' }));
    expect(screen.getByRole('listbox')).toBeTruthy();

    await user.keyboard('{Escape}');

    expect(screen.queryByRole('listbox')).toBeNull();
    expect(onChange).not.toHaveBeenCalled();
  });

  it('fecha ao clicar fora do componente', async () => {
    const user = userEvent.setup();
    render(
      <div>
        <Select value="pt" options={OPTIONS} onChange={vi.fn()} ariaLabel="Idioma" />
        <button type="button">fora</button>
      </div>
    );

    await user.click(screen.getByRole('combobox', { name: 'Idioma' }));
    expect(screen.getByRole('listbox')).toBeTruthy();

    await user.click(screen.getByRole('button', { name: 'fora' }));
    expect(screen.queryByRole('listbox')).toBeNull();
  });
});
