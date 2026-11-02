import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';
import ForceGraph from '../ForceGraph';
import { Sk, SettingsTabSkeleton } from './Loading';

describe('carregamento', () => {
  afterEach(cleanup);

  it('grafo carregando mostra o fantasma, e o aviso de vazio só depois da leitura', () => {
    // Regressão: o painel dizia "Nenhuma nota indexada" enquanto as notas ainda vinham.
    const { rerender } = render(<ForceGraph vaultNodes={[]} links={[]} mode="pastas" loading />);
    expect(screen.getByRole('status', { name: 'Carregando o grafo' })).toBeTruthy();
    expect(screen.queryByText(/Nenhuma nota indexada/)).toBeNull();

    rerender(<ForceGraph vaultNodes={[]} links={[]} mode="pastas" />);
    expect(screen.getByText(/Nenhuma nota indexada/)).toBeTruthy();
  });

  it('o esqueleto usa a classe comum e o tamanho pedido, escondido de leitor de tela', () => {
    const { container } = render(<Sk w={40} h={10} />);
    const box = container.querySelector('.skeleton-box') as HTMLElement;
    expect(box.style.width).toBe('40px');
    expect(box.style.height).toBe('10px');
    expect(box.getAttribute('aria-hidden')).toBe('true');
  });

  it('aba carregando já mostra os títulos dos cards', () => {
    render(<SettingsTabSkeleton tab="ia" />);
    expect(screen.getByRole('region', { name: 'Carregando Fontes de IA' }).getAttribute('aria-busy')).toBe('true');
    expect(screen.getByText('Modelo de resposta')).toBeTruthy();
  });
});
