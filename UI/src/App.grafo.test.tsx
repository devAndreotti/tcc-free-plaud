import { cleanup, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';
import App from './App';

// O canvas do grafo não roda no jsdom: o botão de teste chama onOpenNote como o clique real faria.
vi.mock('./components/ForceGraph', () => ({
  default: ({ onOpenNote }: { onOpenNote?: (id: string) => void }) => (
    <div>
      <button type="button" onClick={() => onOpenNote?.('plataforma-local')}>nota no grafo</button>
      <button type="button" onClick={() => onOpenNote?.('nota-apagada')}>nota apagada</button>
    </div>
  ),
}));

describe('App: clique numa nota do grafo', () => {
  afterEach(() => {
    cleanup();
  });

  it('regressao: onOpenNote leva à tela Notas com o detalhe da nota', async () => {
    const user = userEvent.setup();
    render(<App />);
    await user.click(screen.getByRole('button', { name: 'Abrir painel de grafos' }));
    await user.click(await screen.findByRole('button', { name: 'nota no grafo' }));
    expect((await screen.findAllByText('Plataforma local')).length).toBeGreaterThan(0);
  });

  it('regressao: nota que não existe mais abre a tela Notas com mensagem curta', async () => {
    const user = userEvent.setup();
    render(<App />);
    await user.click(screen.getByRole('button', { name: 'Abrir painel de grafos' }));
    await user.click(await screen.findByRole('button', { name: 'nota apagada' }));
    expect(await screen.findByText('Esta nota não existe mais no corpus.')).toBeTruthy();
  });
});
