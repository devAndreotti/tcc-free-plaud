import { cleanup, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import ChatInput from './ChatInput';

const bridgeMock = vi.hoisted(() => ({
  startAudioCapture: vi.fn(),
  getAudioCapture: vi.fn(),
  stopAudioCapture: vi.fn(),
  cancelAudioCapture: vi.fn(),
  listAnswerModels: vi.fn(),
  saveBackendSettings: vi.fn(),
}));

vi.mock('../services/bridge', () => ({
  bridge: bridgeMock,
}));

describe('ChatInput - cancelamento da captura de áudio', () => {
  beforeEach(() => {
    bridgeMock.startAudioCapture.mockReset();
    bridgeMock.getAudioCapture.mockReset();
    bridgeMock.stopAudioCapture.mockReset();
    bridgeMock.cancelAudioCapture.mockReset();
  });

  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  it('loga o erro quando o cancelamento falha ao sair do chat no meio da gravação', async () => {
    const user = userEvent.setup();
    const consoleError = vi.spyOn(console, 'error').mockImplementation(() => {});
    const rejection = new Error('Serviço de áudio indisponível.');
    bridgeMock.startAudioCapture.mockResolvedValue({
      job_id: 'audio-cancel-falha',
      status: 'recording',
      source_path: 'C:\\audio-cancel-falha.wav',
      samples_captured: 0,
      error_code: null,
      message: null,
      result: null,
    });
    bridgeMock.cancelAudioCapture.mockRejectedValue(rejection);

    const { unmount } = render(<ChatInput onSendMessage={vi.fn()} />);
    await user.click(screen.getByRole('button', { name: 'Gravar áudio' }));
    await screen.findByRole('button', { name: 'Parar gravação' });

    unmount();

    await waitFor(() => {
      expect(consoleError).toHaveBeenCalledWith(
        expect.stringContaining('Não foi possível cancelar a gravação'),
        rejection,
      );
    });
    expect(bridgeMock.cancelAudioCapture).toHaveBeenCalledWith('audio-cancel-falha');
  });

  it('descarta a captura que termina depois que o chat foi desmontado', async () => {
    const user = userEvent.setup();
    // Promessa controlada: a captura só resolve depois que o chat já foi desmontado.
    let resolveStart: (value: unknown) => void = () => {};
    bridgeMock.startAudioCapture.mockReturnValue(
      new Promise((resolve) => {
        resolveStart = resolve;
      }),
    );

    const { unmount } = render(<ChatInput onSendMessage={vi.fn()} />);
    await user.click(screen.getByRole('button', { name: 'Gravar áudio' }));
    expect(bridgeMock.startAudioCapture).toHaveBeenCalledTimes(1);

    unmount();
    resolveStart({
      job_id: 'audio-tardio',
      status: 'recording',
      source_path: 'C:\\audio-tardio.wav',
      samples_captured: 0,
      error_code: null,
      message: null,
      result: null,
    });

    await waitFor(() => {
      expect(bridgeMock.cancelAudioCapture).toHaveBeenCalledWith('audio-tardio');
    });
    expect(bridgeMock.cancelAudioCapture).toHaveBeenCalledTimes(1);
  });
});

describe('ChatInput - envio com Enter', () => {
  afterEach(() => {
    cleanup();
  });

  it('Enter com campo vazio ou só com espaços não envia mensagem', async () => {
    const user = userEvent.setup();
    const onSendMessage = vi.fn();
    render(<ChatInput onSendMessage={onSendMessage} />);

    const textarea = screen.getByRole('textbox', { name: 'Campo de mensagem' });
    await user.click(textarea);
    await user.keyboard('{Enter}');
    await user.type(textarea, '   {Enter}');
    expect(onSendMessage).not.toHaveBeenCalled();

    // Controle: com texto, o mesmo Enter envia.
    await user.type(textarea, 'oi{Enter}');
    expect(onSendMessage).toHaveBeenCalledWith('oi');
  });
});
