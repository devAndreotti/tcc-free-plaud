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
    expect(await screen.findByText(/notas · .* trechos/)).toBeTruthy();

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
    // Sem streaming: esta regressão cobre o caminho askCorpus (o mock do navegador responde em streaming).
    const streamingSpy = vi.spyOn(bridge, 'supportsAskStreaming').mockResolvedValue(false);
    render(<App />);

    await user.click(await screen.findByRole('button', { name: 'Pasta de origem: Todas as pastas' }));
    const menu = await screen.findByRole('group', { name: 'Pasta de origem' });
    expect(within(menu).getByRole('button', { name: /Obsidian/ }).getAttribute('title')).toBe('D:\\Notas\\Obsidian');
    await user.click(within(menu).getByRole('button', { name: /Culinaria/ }));

    await user.type(screen.getByRole('textbox', { name: 'Campo de mensagem' }), 'Como fazer bolo de chocolate?');
    await user.click(screen.getByRole('button', { name: 'Enviar mensagem' }));

    expect(askSpy).toHaveBeenCalledWith('Como fazer bolo de chocolate?', 'hybrid', 'D:\\Notas\\Culinaria');
    expect(window.localStorage.getItem('escolio:chat:sourceRoot')).toBe('D:\\Notas\\Culinaria');
    askSpy.mockRestore();
    streamingSpy.mockRestore();
  });

  it('o rascunho é de cada aba: volta depois de passar por Notas, e uma aba nova abre vazia', async () => {
    const user = userEvent.setup();
    render(<App />);
    await screen.findByRole('button', { name: /Vault ativa: Obsidian/ });
    const campo = () => screen.getByRole('textbox', { name: 'Campo de mensagem' }) as HTMLTextAreaElement;
    await user.type(campo(), 'Rascunho da aba A');

    await user.click(screen.getByRole('button', { name: /Notas/ }));
    expect(await screen.findByRole('heading', { name: 'Notas' })).toBeTruthy();
    await user.click(screen.getByRole('tab'));
    expect(campo().value).toBe('Rascunho da aba A');

    await user.click(screen.getByRole('button', { name: 'Nova conversa' }));
    expect(campo().value).toBe('');
  });

  it('os menus da barra usam grupos e botões, sem papel de menu, lista ou opção', async () => {
    const user = userEvent.setup();
    render(<App />);
    await screen.findByRole('button', { name: /Vault ativa: Obsidian/ });
    const barra = () => document.querySelector('.input-area') as HTMLElement;
    const semPapelDeMenu = () =>
      expect(barra().querySelector('[role="menu"], [role="menuitemradio"], [role="listbox"], [role="option"], [aria-haspopup="menu"], [aria-haspopup="listbox"]')).toBeNull();

    await user.click(screen.getByRole('button', { name: /Vault da pergunta/ }));
    expect(screen.getByRole('group', { name: 'Vault da pergunta' })).toBeTruthy();
    semPapelDeMenu();

    await user.click(await screen.findByRole('button', { name: /Pasta de origem/ }));
    expect(screen.getByRole('group', { name: 'Pasta de origem' })).toBeTruthy();
    semPapelDeMenu();

    await user.click(await screen.findByRole('button', { name: /Como responder/ }));
    expect(screen.getByRole('group', { name: 'Como responder' })).toBeTruthy();
    semPapelDeMenu();
  });

  it('estratégia padrão lida do backend segue valendo depois de salvar o modelo na barra', async () => {
    const user = userEvent.setup();
    window.localStorage.clear();
    const base = await bridge.getBackendSettings({ doctor: false });
    const settingsSpy = vi.spyOn(bridge, 'getBackendSettings').mockResolvedValue({ ...base, default_ask_strategy: 'lexical' });
    const askSpy = vi.spyOn(bridge, 'askCorpus');
    const streamingSpy = vi.spyOn(bridge, 'supportsAskStreaming').mockResolvedValue(false);
    render(<App />);

    await user.click(await screen.findByRole('button', { name: /Como responder/ }));
    await user.click(await screen.findByRole('button', { name: /qwen2\.5:3b/ }));
    await user.type(screen.getByRole('textbox', { name: 'Campo de mensagem' }), 'Pergunta depois de salvar');
    await user.click(screen.getByRole('button', { name: 'Enviar mensagem' }));

    expect(settingsSpy).toHaveBeenCalledWith({ doctor: false });
    expect(askSpy).toHaveBeenCalledWith('Pergunta depois de salvar', 'lexical', null);
    askSpy.mockRestore();
    streamingSpy.mockRestore();
    settingsSpy.mockRestore();
  });

  it('clicar numa fonte da resposta abre a nota na tela Notas, com o trecho citado destacado', async () => {
    const user = userEvent.setup();
    render(<App />);
    await screen.findByRole('button', { name: /Vault ativa: Obsidian/ });

    await user.type(screen.getByRole('textbox', { name: 'Campo de mensagem' }), 'Como funciona o id de um chunk?');
    await user.click(screen.getByRole('button', { name: 'Enviar mensagem' }));
    const history = await screen.findByRole('log', { name: 'Histórico de mensagens' });
    await within(history).findByRole('article', { name: 'Resposta' }, { timeout: 5000 });

    // Duas fontes são da mesma nota: a primeira é o trecho "O id de um trecho junta…".
    await user.click(within(history).getAllByRole('button', { name: 'Abrir Arquitetura do índice no trecho citado' })[0]);

    expect(await screen.findByRole('heading', { name: 'Notas' })).toBeTruthy();
    expect(await screen.findByText('trecho citado')).toBeTruthy();
    expect(document.querySelector('.reader__chunk--cited')?.textContent).toContain('O id de um trecho junta');
  });
});
