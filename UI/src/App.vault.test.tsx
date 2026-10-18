import { act, cleanup, render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeAll, describe, expect, it, vi } from 'vitest';
import App from './App';
import { bridge, type AskResult } from './services/bridge';

type User = ReturnType<typeof userEvent.setup>;

// Espera a vault ativa carregar: antes disso a conversa ainda não tem dono.
const waitForVault = (name: RegExp = /Obsidian/) =>
  screen.findByRole('button', { name: new RegExp(`Vault ativa: ${name.source}`) });

const switchVault = async (user: User, name: RegExp) => {
  await user.click(await screen.findByRole('button', { name: /Vault ativa:/ }));
  await user.click(screen.getByRole('menuitemradio', { name }));
  await waitForVault(name);
};

const send = async (user: User, text: string) => {
  await user.type(await screen.findByRole('textbox', { name: 'Campo de mensagem' }), text);
  await user.click(screen.getByRole('button', { name: 'Enviar mensagem' }));
};

const tabNamed = (label: string) =>
  within(screen.getByRole('tablist', { name: 'Abas abertas' })).getByText(label).closest('[role="tab"]') as HTMLElement;

describe('vault: cada conversa pertence a uma vault', () => {
  beforeAll(() => {
    // jsdom não tem ResizeObserver nem canvas (mesmo ajuste de App.test.tsx).
    vi.stubGlobal('ResizeObserver', class { observe() {} unobserve() {} disconnect() {} });
    vi.spyOn(HTMLCanvasElement.prototype, 'getContext').mockReturnValue(null);
    Element.prototype.scrollIntoView = vi.fn();
  });

  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
    // O mock guarda a vault ativa em módulo: volta para a primeira para o próximo teste.
    void bridge.selectVault('obsidian');
  });

  it('vault: a aba mostra o ícone e a cor da vault da conversa', async () => {
    const user = userEvent.setup();
    render(<App />);
    await waitForVault();
    expect(screen.getByRole('tab').querySelector('.vault-glyph--violet')).not.toBeNull();

    // Aba vazia acompanha a troca de vault.
    await switchVault(user, /Culinária/);
    expect(screen.getAllByRole('tab')).toHaveLength(1);
    expect(screen.getByRole('tab').querySelector('.vault-glyph--amber')).not.toBeNull();
  });

  it('vault: trocar pela sidebar abre a conversa da nova vault e mantém a aba da anterior', async () => {
    const user = userEvent.setup();
    render(<App />);
    await waitForVault();
    await send(user, 'Pergunta da Obsidian');
    await screen.findByRole('log', { name: 'Histórico de mensagens' });

    await switchVault(user, /Culinária/);
    await waitFor(() => expect(screen.queryByRole('log', { name: 'Histórico de mensagens' })).toBeNull());
    expect(screen.getAllByRole('tab')).toHaveLength(2);
    expect(tabNamed('Pergunta da Obsidian').querySelector('.vault-glyph--violet')).not.toBeNull();

    // Voltar mostra a conversa da Obsidian e fecha a "Nova Conversa" vazia da Culinária.
    await switchVault(user, /Obsidian/);
    expect(await within(await screen.findByRole('log')).findByText('Pergunta da Obsidian')).toBeTruthy();
    expect(screen.getAllByRole('tab')).toHaveLength(1);
  });

  it('vault: clicar na aba de outra vault ativa a vault da conversa', async () => {
    const user = userEvent.setup();
    render(<App />);
    await waitForVault();
    await send(user, 'Pergunta da Obsidian');
    await screen.findByRole('log', { name: 'Histórico de mensagens' });
    await switchVault(user, /Culinária/);

    await user.click(tabNamed('Pergunta da Obsidian'));
    expect(await waitForVault(/Obsidian/)).toBeTruthy();
    expect(await within(screen.getByRole('log')).findByText('Pergunta da Obsidian')).toBeTruthy();
  });

  it('vault: resposta enviada em A e resolvida depois da troca cai na aba de A', async () => {
    let resolveAsk: (value: AskResult) => void = () => {};
    vi.spyOn(bridge, 'askCorpus').mockImplementation(
      () => new Promise<AskResult>((resolve) => { resolveAsk = resolve; })
    );
    const user = userEvent.setup();
    render(<App />);
    await waitForVault();
    await send(user, 'Pergunta pendente');

    await switchVault(user, /Culinária/);
    await act(async () => {
      resolveAsk({
        query: 'Pergunta pendente', status: 'answer', no_answer: false, answer: 'Resposta da Obsidian',
        claims: [], citations: [], limitations: [], reason_for_no_answer: null, latency_ms: 1,
      });
    });
    expect(screen.queryByText('Resposta da Obsidian')).toBeNull();

    await user.click(tabNamed('Pergunta pendente'));
    expect(await screen.findByText('Resposta da Obsidian')).toBeTruthy();
  });

  it('vault: duplo clique renomeia a conversa; Esc cancela', async () => {
    const user = userEvent.setup();
    render(<App />);
    await waitForVault();

    await user.dblClick(tabNamed('Nova Conversa'));
    const field = screen.getByRole('textbox', { name: 'Nome da conversa' });
    await user.clear(field);
    await user.type(field, 'Estudos de redes{Enter}');
    expect(tabNamed('Estudos de redes')).toBeTruthy();

    await user.dblClick(tabNamed('Estudos de redes'));
    await user.type(screen.getByRole('textbox', { name: 'Nome da conversa' }), ' rascunho{Escape}');
    expect(tabNamed('Estudos de redes')).toBeTruthy();

    // Nome dado pelo usuário não é trocado pela primeira pergunta.
    await send(user, 'Qual broker foi adotado?');
    expect(tabNamed('Estudos de redes')).toBeTruthy();
  });
});
