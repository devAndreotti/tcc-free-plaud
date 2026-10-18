import { act, cleanup, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeAll, describe, expect, it, vi } from 'vitest';
import App from './App';
import { bridge, type AskResult } from './services/bridge';

type User = ReturnType<typeof userEvent.setup>;

// Espera a vault ativa carregar: antes disso a conversa ainda não tem dono.
const waitForVault = () => screen.findByRole('button', { name: /Vault ativa: Obsidian/ });

const switchVault = async (user: User, name: RegExp) => {
  await user.click(await screen.findByRole('button', { name: /Vault ativa:/ }));
  await user.click(screen.getByRole('menuitemradio', { name }));
};

const send = async (user: User, text: string) => {
  await user.type(await screen.findByRole('textbox', { name: 'Campo de mensagem' }), text);
  await user.click(screen.getByRole('button', { name: 'Enviar mensagem' }));
};

describe('vault: conversas por vault', () => {
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

  it('vault: abas da vault A não aparecem na B', async () => {
    const user = userEvent.setup();
    render(<App />);
    await waitForVault();
    await send(user, 'Pergunta da Obsidian');
    expect((await screen.findAllByText('Pergunta da Obsidian')).length).toBeGreaterThan(0);

    await switchVault(user, /Culinária/);
    await waitFor(() => expect(screen.queryAllByText('Pergunta da Obsidian')).toHaveLength(0));
  });

  it('vault: voltar para A restaura as abas e as mensagens', async () => {
    const user = userEvent.setup();
    render(<App />);
    await waitForVault();
    await send(user, 'Pergunta da Obsidian');
    expect((await screen.findAllByText('Pergunta da Obsidian')).length).toBeGreaterThan(0);

    await switchVault(user, /Culinária/);
    await switchVault(user, /Obsidian/);
    expect((await screen.findAllByText('Pergunta da Obsidian')).length).toBeGreaterThan(0);
  });

  it('vault: resposta enviada em A e resolvida depois da troca cai em A, não em B', async () => {
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

    await switchVault(user, /Obsidian/);
    expect(await screen.findByText('Resposta da Obsidian')).toBeTruthy();
  });
});
