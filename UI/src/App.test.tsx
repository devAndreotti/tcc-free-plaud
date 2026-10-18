import { cleanup, render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeAll, describe, expect, it, vi } from 'vitest';
import App from './App';
import { bridge } from './services/bridge';

// O app roda sobre o bridge em modo mock (sem pywebview), como no navegador de desenvolvimento.
describe('App', () => {
  beforeAll(() => {
    // jsdom não tem ResizeObserver nem canvas; o grafo só precisa montar sem quebrar.
    vi.stubGlobal(
      'ResizeObserver',
      class {
        observe() {}
        unobserve() {}
        disconnect() {}
      }
    );
    vi.spyOn(HTMLCanvasElement.prototype, 'getContext').mockReturnValue(null);
    Element.prototype.scrollIntoView = vi.fn();
  });

  afterEach(() => {
    cleanup();
  });

  it('abre na tela inicial, pergunta e mostra a conversa', async () => {
    const user = userEvent.setup();
    render(<App />);

    expect(screen.getByRole('main', { name: 'Tela inicial' })).toBeTruthy();
    // A sidebar resume o corpus a partir das configurações do backend.
    expect(await screen.findByText(/notas · .* chunks/)).toBeTruthy();

    // Regressão: o campo não pode remontar quando a lista de vaults chega (o texto digitado se perdia).
    const input = screen.getByRole('textbox', { name: 'Campo de mensagem' });
    expect(await screen.findByRole('button', { name: /Vault ativa: Obsidian/ })).toBeTruthy();
    expect(screen.getByRole('textbox', { name: 'Campo de mensagem' })).toBe(input);

    await user.type(input, 'Qual broker foi adotado?');
    await user.click(screen.getByRole('button', { name: 'Enviar mensagem' }));

    const history = await screen.findByRole('log', { name: 'Histórico de mensagens' });
    expect(await within(history).findByText('Qual broker foi adotado?')).toBeTruthy();
    expect(await within(history).findByRole('article', { name: 'Resposta' }, { timeout: 5000 })).toBeTruthy();
  });

  it('troca de tela pela sidebar, abre aba nova e o painel de grafos', async () => {
    const user = userEvent.setup();
    render(<App />);

    await user.click(screen.getByRole('button', { name: /Notas/ }));
    expect(await screen.findByRole('heading', { name: 'Notas' })).toBeTruthy();

    await user.click(screen.getByRole('button', { name: /Fila/ }));
    expect(await screen.findByRole('heading', { name: /Fila/ })).toBeTruthy();

    await user.click(screen.getByRole('button', { name: /Benchmark/ }));
    expect(await screen.findByRole('heading', { name: 'Benchmark' })).toBeTruthy();

    await user.click(screen.getByRole('button', { name: /Perguntar/ }));
    await user.click(screen.getByRole('button', { name: 'Nova conversa' }));
    expect(screen.getAllByRole('tab')).toHaveLength(2);

    await user.click(screen.getByRole('button', { name: 'Abrir painel de grafos' }));
    expect(await screen.findByRole('button', { name: 'Fechar painel de grafos' })).toBeTruthy();
  });

  it('lista as pastas do corpus no seletor e envia a pasta escolhida na pergunta (regressao)', async () => {
    const user = userEvent.setup();
    window.localStorage.clear();
    const askSpy = vi.spyOn(bridge, 'askCorpus');
    render(<App />);

    await user.click(await screen.findByRole('button', { name: 'Pasta de origem: Todas as pastas' }));
    const menu = await screen.findByRole('menu', { name: 'Pasta de origem' });
    expect(within(menu).getByRole('menuitemradio', { name: /Obsidian/ }).getAttribute('title')).toBe('D:\\Notas\\Obsidian');
    await user.click(within(menu).getByRole('menuitemradio', { name: /Culinaria/ }));

    await user.type(screen.getByRole('textbox', { name: 'Campo de mensagem' }), 'Como fazer bolo de chocolate?');
    await user.click(screen.getByRole('button', { name: 'Enviar mensagem' }));

    expect(askSpy).toHaveBeenCalledWith('Como fazer bolo de chocolate?', 'hybrid', 'D:\\Notas\\Culinaria');
    expect(window.localStorage.getItem('escolio:chat:sourceRoot')).toBe('D:\\Notas\\Culinaria');
    askSpy.mockRestore();
  });
});
