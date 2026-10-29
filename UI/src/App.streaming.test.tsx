import { act, cleanup, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeAll, describe, expect, it, vi } from 'vitest';
import App from './App';
import { bridge, type AskProgress, type AskResult } from './services/bridge';

type User = ReturnType<typeof userEvent.setup>;

// Resposta final que o backend devolve quando a IA termina de escrever.
const ANSWER: AskResult = {
  query: 'O que é Docker?',
  status: 'answer',
  no_answer: false,
  answer: 'Docker roda containers isolados.',
  claims: [],
  citations: [],
  limitations: [],
  reason_for_no_answer: null,
  latency_ms: 1,
  answer_provider: 'ollama',
  answer_model: 'qwen2.5:3b',
  generated: true,
};

const progress = (askId: string, stage: AskProgress['stage'], partial = ''): AskProgress => ({
  ask_id: askId,
  stage,
  partial,
  result: null,
  error: null,
});

const waitForVault = () => screen.findByRole('button', { name: /Vault ativa: Obsidian/ });

const send = async (user: User, text: string) => {
  await user.type(await screen.findByRole('textbox', { name: 'Campo de mensagem' }), text);
  await user.click(screen.getByRole('button', { name: 'Enviar mensagem' }));
};

// Backend com streaming: startAsk devolve um id e cada pollAsk segue o roteiro do teste (call = número da consulta).
const streamingBackend = (poll: (askId: string, call: number) => AskProgress) => {
  vi.spyOn(bridge, 'supportsAskStreaming').mockResolvedValue(true);
  vi.spyOn(bridge, 'startAsk').mockResolvedValue({ ask_id: 'ask-teste' });
  let calls = 0;
  return vi.spyOn(bridge, 'pollAsk').mockImplementation(async (askId) => {
    calls += 1;
    return poll(askId, calls);
  });
};

const pausa = (ms: number) =>
  act(async () => {
    await new Promise<void>((resolve) => setTimeout(resolve, ms));
  });

describe('App: resposta em streaming', () => {
  beforeAll(() => {
    // jsdom não tem ResizeObserver nem canvas (mesmo ajuste de App.conversas.test.tsx).
    vi.stubGlobal('ResizeObserver', class { observe() {} unobserve() {} disconnect() {} });
    vi.spyOn(HTMLCanvasElement.prototype, 'getContext').mockReturnValue(null);
    Element.prototype.scrollIntoView = vi.fn();
  });

  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
    vi.useRealTimers();
  });

  it('mostra o texto enquanto a IA escreve e termina com a resposta final', async () => {
    let released = false;
    streamingBackend((askId, call) => {
      if (call === 1) return progress(askId, 'retrieving');
      if (!released) return progress(askId, 'writing', 'Docker roda');
      return { ...progress(askId, 'done'), result: ANSWER };
    });
    const user = userEvent.setup();
    render(<App />);
    await waitForVault();
    await send(user, 'O que é Docker?');

    expect(await screen.findByText('Escrevendo com qwen2.5:3b…')).toBeTruthy();
    expect(await screen.findByText('Docker roda')).toBeTruthy();

    released = true;
    expect(await screen.findByText('Docker roda containers isolados.')).toBeTruthy();
    expect(screen.queryByText(/Escrevendo com/)).toBeNull();
  });

  it('erro no meio da resposta vira a mensagem de erro de sempre', async () => {
    vi.spyOn(console, 'error').mockImplementation(() => {});
    streamingBackend((askId) => ({ ...progress(askId, 'error'), error: 'modelo indisponível' }));
    const user = userEvent.setup();
    render(<App />);
    await waitForVault();
    await send(user, 'Pergunta com erro');

    expect(await screen.findByText('Ocorreu um erro ao processar sua mensagem. Tente novamente.')).toBeTruthy();
    expect(screen.queryByText('Buscando no vault…')).toBeNull();
  });

  it('fechar a aba no meio da resposta para de consultar o backend', async () => {
    const pollAsk = streamingBackend((askId) => progress(askId, 'writing', 'Docker roda'));
    const user = userEvent.setup();
    render(<App />);
    await waitForVault();
    await send(user, 'Pergunta que será fechada');
    expect(await screen.findByText('Docker roda')).toBeTruthy();

    await user.click(screen.getByRole('button', { name: 'Fechar aba Pergunta que será fechada' }));
    await pausa(400);
    const depois = pollAsk.mock.calls.length;
    await pausa(400);
    expect(pollAsk.mock.calls.length).toBe(depois);
  });

  it('Parar descarta a pergunta no backend, para de consultar e não grava resposta na conversa', async () => {
    const cancel = vi.spyOn(bridge, 'cancelAsk').mockResolvedValue({ ok: true });
    const pollAsk = streamingBackend((askId) => progress(askId, 'writing', 'Docker roda'));
    const user = userEvent.setup();
    render(<App />);
    await waitForVault();
    await send(user, 'Pergunta parada');
    expect(await screen.findByText('Docker roda')).toBeTruthy();

    await user.click(screen.getByRole('button', { name: 'Parar resposta' }));

    expect(cancel).toHaveBeenCalledWith('ask-teste');
    await pausa(400);
    expect(screen.queryByText('Docker roda')).toBeNull();
    expect(screen.queryByRole('article', { name: 'Resposta' })).toBeNull();
    const depois = pollAsk.mock.calls.length;
    await pausa(400);
    expect(pollAsk.mock.calls.length).toBe(depois);
  });

  it('erro: "Tentar de novo" repete a mesma pergunta com a mesma estratégia', async () => {
    vi.spyOn(console, 'error').mockImplementation(() => {});
    streamingBackend((askId, call) =>
      call === 1 ? { ...progress(askId, 'error'), error: 'modelo indisponível' } : { ...progress(askId, 'done'), result: ANSWER }
    );
    const user = userEvent.setup();
    render(<App />);
    await waitForVault();
    await send(user, 'Pergunta que falha');

    await user.click(await screen.findByRole('button', { name: 'Tentar de novo' }));

    expect(bridge.startAsk).toHaveBeenLastCalledWith('Pergunta que falha', 'hybrid', null);
    expect(await screen.findByText('Docker roda containers isolados.')).toBeTruthy();
  });

  it('aquece o modelo ao abrir e, ao focar o campo, no máximo uma vez a cada 4 min', async () => {
    vi.useFakeTimers({ toFake: ['Date'] });
    vi.setSystemTime(new Date('2026-10-19T10:00:00Z'));
    const warm = vi.spyOn(bridge, 'warmAnswerModel');
    const user = userEvent.setup();
    render(<App />);
    await waitForVault();
    expect(warm).toHaveBeenCalledTimes(1);

    // Foco de novo dentro dos 4 min: não aquece outra vez.
    const input = screen.getByRole('textbox', { name: 'Campo de mensagem' });
    await user.click(input);
    await user.click(document.body);
    await user.click(input);
    expect(warm).toHaveBeenCalledTimes(1);

    // Passados os 4 min, o próximo foco aquece; um foco logo depois não repete.
    vi.setSystemTime(new Date('2026-10-19T10:04:00Z'));
    await user.click(document.body);
    await user.click(input);
    expect(warm).toHaveBeenCalledTimes(2);

    await user.click(document.body);
    await user.click(input);
    expect(warm).toHaveBeenCalledTimes(2);
  });
});
