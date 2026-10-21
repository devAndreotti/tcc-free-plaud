import { cleanup, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { AnswerPicker } from './AnswerPicker';

const bridgeMock = vi.hoisted(() => ({
  listAnswerModels: vi.fn(),
}));

vi.mock('../services/bridge', () => ({
  bridge: bridgeMock,
}));

const AVISO_SEM_CONEXAO_OLLAMA = 'Não consegui conectar ao Ollama. Inicie o Ollama e tente de novo.';

const abrirMenu = async () => {
  render(<AnswerPicker provider="ollama" model="qchat:latest" onSaved={vi.fn()} />);
  await userEvent.setup().click(screen.getByRole('button', { name: 'Como responder: qchat' }));
};

describe('AnswerPicker - falhas da listagem de modelos', () => {
  beforeEach(() => {
    bridgeMock.listAnswerModels.mockReset();
  });

  afterEach(() => {
    cleanup();
  });

  it('se a ponte rejeita a listagem, mostra o aviso de conexão sem URL', async () => {
    bridgeMock.listAnswerModels.mockRejectedValue(new Error('pywebview indisponível'));

    await abrirMenu();

    const aviso = await screen.findByRole('alert');
    expect(aviso.textContent).toBe(AVISO_SEM_CONEXAO_OLLAMA);
    expect(bridgeMock.listAnswerModels).toHaveBeenCalledWith({ provider: 'ollama' });
    expect(screen.queryByText('Nenhum modelo de conversa instalado.')).toBeNull();
    expect(screen.queryByText('Listando modelos…')).toBeNull();
  });

  it('lista sem modelos de conversa mostra o aviso de vazio, sem alerta', async () => {
    bridgeMock.listAnswerModels.mockResolvedValue({
      provider: 'ollama',
      base_url: null,
      status: 'ok',
      models: [],
      latency_ms: 5,
      cached: false,
      message: null,
    });

    await abrirMenu();

    expect(await screen.findByText('Nenhum modelo de conversa instalado.')).toBeTruthy();
    expect(screen.queryByRole('alert')).toBeNull();
  });

  it('enquanto a lista carrega, mostra Listando modelos e nenhum aviso', async () => {
    bridgeMock.listAnswerModels.mockReturnValue(new Promise(() => {}));

    await abrirMenu();

    expect(screen.getByText('Listando modelos…')).toBeTruthy();
    expect(screen.queryByText('Nenhum modelo de conversa instalado.')).toBeNull();
    expect(screen.queryByRole('alert')).toBeNull();
  });
});
