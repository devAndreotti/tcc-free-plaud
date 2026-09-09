import { cleanup, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import ChatInput from './ChatInput';

const bridgeMock = vi.hoisted(() => ({
  startAudioCapture: vi.fn(),
  getAudioCapture: vi.fn(),
  stopAudioCapture: vi.fn(),
  cancelAudioCapture: vi.fn(),
}));

vi.mock('../services/bridge', () => ({
  bridge: bridgeMock,
}));

describe('ChatInput - gravação de áudio', () => {
  afterEach(() => {
    cleanup();
  });

  beforeEach(() => {
    bridgeMock.startAudioCapture.mockReset();
    bridgeMock.getAudioCapture.mockReset();
    bridgeMock.stopAudioCapture.mockReset();
    bridgeMock.cancelAudioCapture.mockReset();
  });

  it('grava, transcreve e insere o texto reconhecido no campo de mensagem', async () => {
    const user = userEvent.setup();
    bridgeMock.startAudioCapture.mockResolvedValue({
      job_id: 'audio-1',
      status: 'recording',
      source_path: 'C:\\audio-1.wav',
      samples_captured: 0,
      error_code: null,
      message: null,
      result: null,
    });
    bridgeMock.stopAudioCapture.mockResolvedValue({
      job_id: 'audio-1',
      status: 'completed',
      source_path: 'C:\\audio-1.wav',
      samples_captured: 16000,
      error_code: null,
      message: null,
      result: { text: 'texto transcrito do microfone', language: 'pt', duration_seconds: 2 },
    });

    render(<ChatInput onSendMessage={vi.fn()} />);

    await user.click(screen.getByRole('button', { name: 'Gravar áudio' }));
    await waitFor(() => expect(bridgeMock.startAudioCapture).toHaveBeenCalled());
    expect(await screen.findByRole('button', { name: 'Parar gravação' })).toBeTruthy();

    await user.click(screen.getByRole('button', { name: 'Parar gravação' }));
    await waitFor(() => {
      expect(bridgeMock.stopAudioCapture).toHaveBeenCalledWith('audio-1');
    });

    const textarea = await screen.findByRole('textbox', { name: 'Campo de mensagem' });
    await waitFor(() => {
      expect((textarea as HTMLTextAreaElement).value).toBe('texto transcrito do microfone');
    });
    expect(screen.getByRole('button', { name: 'Gravar áudio' })).toBeTruthy();
  });

  it('mostra mensagem de erro quando o microfone falha ao iniciar', async () => {
    const user = userEvent.setup();
    bridgeMock.startAudioCapture.mockRejectedValue(new Error('Dispositivo de audio indisponivel.'));

    render(<ChatInput onSendMessage={vi.fn()} />);
    await user.click(screen.getByRole('button', { name: 'Gravar áudio' }));

    expect(await screen.findByText('Dispositivo de audio indisponivel.')).toBeTruthy();
  });

  it('incrementa o timer de tempo decorrido durante a gravação', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const user = userEvent.setup();
    bridgeMock.startAudioCapture.mockResolvedValue({
      job_id: 'audio-timer',
      status: 'recording',
      source_path: 'C:\\audio-timer.wav',
      samples_captured: 0,
      error_code: null,
      message: null,
      result: null,
    });

    render(<ChatInput onSendMessage={vi.fn()} />);
    await user.click(screen.getByRole('button', { name: 'Gravar áudio' }));
    await screen.findByRole('button', { name: 'Parar gravação' });

    await vi.advanceTimersByTimeAsync(3000);

    expect(screen.getByText('0:03')).toBeTruthy();
    vi.useRealTimers();
  });

  it('mostra spinner no botão de mic enquanto transcreve', async () => {
    const user = userEvent.setup();
    bridgeMock.startAudioCapture.mockResolvedValue({
      job_id: 'audio-spin',
      status: 'recording',
      source_path: 'C:\\audio-spin.wav',
      samples_captured: 0,
      error_code: null,
      message: null,
      result: null,
    });
    let resolveStop: (value: unknown) => void = () => {};
    bridgeMock.stopAudioCapture.mockReturnValue(new Promise((resolve) => { resolveStop = resolve; }));

    const { container } = render(<ChatInput onSendMessage={vi.fn()} />);
    await user.click(screen.getByRole('button', { name: 'Gravar áudio' }));
    await screen.findByRole('button', { name: 'Parar gravação' });
    await user.click(screen.getByRole('button', { name: 'Parar gravação' }));

    expect(await screen.findByText('Transcrevendo áudio localmente…')).toBeTruthy();
    expect(container.querySelector('.spin')).toBeTruthy();
    expect(container.querySelector('.btn-mic--recording')).toBeNull();

    resolveStop({
      job_id: 'audio-spin',
      status: 'completed',
      source_path: 'C:\\audio-spin.wav',
      samples_captured: 16000,
      error_code: null,
      message: null,
      result: { text: 'ok', language: 'pt', duration_seconds: 1 },
    });
    await screen.findByRole('button', { name: 'Gravar áudio' });
  });
});
