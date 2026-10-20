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

  it('avisa quando a gravação termina sem fala detectada', async () => {
    const user = userEvent.setup();
    bridgeMock.startAudioCapture.mockResolvedValue({
      job_id: 'audio-silent',
      status: 'recording',
      source_path: 'C:\\audio-silent.wav',
      samples_captured: 0,
      error_code: null,
      message: null,
      result: null,
    });
    bridgeMock.stopAudioCapture.mockResolvedValue({
      job_id: 'audio-silent',
      status: 'completed',
      source_path: 'C:\\audio-silent.wav',
      samples_captured: 16000,
      error_code: null,
      message: null,
      result: { text: '', language: 'pt', duration_seconds: 1 },
    });

    render(<ChatInput onSendMessage={vi.fn()} />);

    await user.click(screen.getByRole('button', { name: 'Gravar áudio' }));
    await user.click(await screen.findByRole('button', { name: 'Parar gravação' }));

    expect(await screen.findByText(/Nenhuma fala detectada no áudio/)).toBeTruthy();
  });

  it('mostra mensagem de erro quando o microfone falha ao iniciar', async () => {
    const user = userEvent.setup();
    bridgeMock.startAudioCapture.mockRejectedValue(new Error('Dispositivo de audio indisponivel.'));

    render(<ChatInput onSendMessage={vi.fn()} />);
    await user.click(screen.getByRole('button', { name: 'Gravar áudio' }));

    expect(await screen.findByText('Dispositivo de audio indisponivel.')).toBeTruthy();
  });

  it('orienta a abrir Configurações → Voz quando o modelo de transcrição não está instalado', async () => {
    const user = userEvent.setup();
    bridgeMock.startAudioCapture.mockResolvedValue({
      job_id: 'audio-missing-model',
      status: 'recording',
      source_path: 'C:\\audio-missing-model.wav',
      samples_captured: 0,
      error_code: null,
      message: null,
      result: null,
    });
    bridgeMock.stopAudioCapture.mockResolvedValue({
      job_id: 'audio-missing-model',
      status: 'failed',
      source_path: 'C:\\audio-missing-model.wav',
      samples_captured: 16000,
      error_code: 'AUDIO_MODEL_NOT_READY',
      message: 'Model whisper-small missing or corrupt; download/verify it explicitly.',
      result: null,
    });

    render(<ChatInput onSendMessage={vi.fn()} />);
    await user.click(screen.getByRole('button', { name: 'Gravar áudio' }));
    expect(await screen.findByRole('button', { name: 'Parar gravação' })).toBeTruthy();

    await user.click(screen.getByRole('button', { name: 'Parar gravação' }));

    expect(
      await screen.findByText('Modelo de transcrição não está instalado. Abra Configurações → Voz para baixá-lo.')
    ).toBeTruthy();
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

describe('ChatInput - resposta da barra', () => {
  const models = [
    { id: 'qwen2.5:3b', label: 'qwen2.5:3b', provider: 'ollama', details: { parameter_size: '3.1B', quantization_level: 'Q4_K_M' } },
    { id: 'nomic-embed-text:latest', label: 'nomic-embed-text:latest', provider: 'ollama', details: {} },
    { id: 'qchat:latest', label: 'qchat:latest', provider: 'ollama', details: {} },
  ];

  beforeEach(() => {
    bridgeMock.listAnswerModels.mockReset().mockResolvedValue({ provider: 'ollama', base_url: null, status: 'ok', models, latency_ms: 5, cached: false, message: null });
    bridgeMock.saveBackendSettings.mockReset();
  });

  afterEach(() => {
    cleanup();
  });

  it('não tem mais a pílula de estratégia Híbrida', () => {
    render(<ChatInput onSendMessage={vi.fn()} answerProvider="extractive" onAnswerSaved={vi.fn()} />);

    expect(screen.queryByText('Híbrida')).toBeNull();
  });

  it('sem IA, mostra Só trechos e o texto de apoio sem modelo', () => {
    render(<ChatInput onSendMessage={vi.fn()} answerProvider="extractive" answerModel="qchat:latest" onAnswerSaved={vi.fn()} />);

    expect(screen.getByRole('button', { name: 'Como responder: Só trechos' }).getAttribute('aria-haspopup')).toBe('listbox');
    expect(screen.getByText('Mostra as frases dos seus trechos. Nenhum modelo é chamado.')).toBeTruthy();
  });

  it('com IA, mostra o modelo curto com o selo IA e o texto de apoio da IA', () => {
    render(<ChatInput onSendMessage={vi.fn()} answerProvider="ollama" answerModel="qchat:latest" onAnswerSaved={vi.fn()} />);

    expect(screen.getByRole('button', { name: 'Como responder: qchat' }).textContent).toContain('IA');
    expect(screen.getByText(/A IA escreve a resposta a partir dos trechos/)).toBeTruthy();
  });

  it('o menu lista Só trechos e os modelos, com o recomendado primeiro e sem embedding', async () => {
    const user = userEvent.setup();
    render(<ChatInput onSendMessage={vi.fn()} answerProvider="ollama" answerModel="qchat:latest" onAnswerSaved={vi.fn()} />);

    await user.click(screen.getByRole('button', { name: 'Como responder: qchat' }));
    await screen.findByRole('option', { name: /qwen2\.5:3b/ });
    const options = screen.getAllByRole('option');

    expect(bridgeMock.listAnswerModels).toHaveBeenCalledWith({ provider: 'ollama' });
    expect(options).toHaveLength(3);
    expect(options[0].textContent).toContain('Só trechos');
    expect(options[1].textContent).toContain('recomendado');
    expect(options[1].getAttribute('aria-selected')).toBe('true');
    expect(screen.queryByText(/nomic-embed/)).toBeNull();
  });

  it('escolher um modelo salva answer_provider e answer_model e devolve o que o backend salvou', async () => {
    const user = userEvent.setup();
    const saved = { answer_provider: 'ollama', answer_model: 'qwen2.5:3b' };
    bridgeMock.saveBackendSettings.mockResolvedValue(saved);
    const onAnswerSaved = vi.fn();
    render(<ChatInput onSendMessage={vi.fn()} answerProvider="ollama" answerModel="qchat:latest" onAnswerSaved={onAnswerSaved} />);

    await user.click(screen.getByRole('button', { name: 'Como responder: qchat' }));
    await user.click(await screen.findByRole('option', { name: /qwen2\.5:3b/ }));

    await waitFor(() =>
      expect(bridgeMock.saveBackendSettings).toHaveBeenCalledWith({ answer_provider: 'ollama', answer_model: 'qwen2.5:3b' })
    );
    expect(onAnswerSaved).toHaveBeenCalledWith(saved);
    expect(screen.queryByRole('listbox')).toBeNull();
  });

  it('escolher Só trechos salva só o provedor extractive', async () => {
    const user = userEvent.setup();
    bridgeMock.saveBackendSettings.mockResolvedValue({ answer_provider: 'extractive' });
    render(<ChatInput onSendMessage={vi.fn()} answerProvider="ollama" answerModel="qchat:latest" onAnswerSaved={vi.fn()} />);

    await user.click(screen.getByRole('button', { name: 'Como responder: qchat' }));
    await user.click(await screen.findByRole('option', { name: /Só trechos/ }));

    await waitFor(() => expect(bridgeMock.saveBackendSettings).toHaveBeenCalledWith({ answer_provider: 'extractive' }));
  });

  it('Esc fecha o menu sem salvar nada', async () => {
    const user = userEvent.setup();
    render(<ChatInput onSendMessage={vi.fn()} answerProvider="ollama" answerModel="qchat:latest" onAnswerSaved={vi.fn()} />);

    await user.click(screen.getByRole('button', { name: 'Como responder: qchat' }));
    expect(screen.getByRole('listbox')).toBeTruthy();
    await user.keyboard('{Escape}');

    expect(screen.queryByRole('listbox')).toBeNull();
    expect(bridgeMock.saveBackendSettings).not.toHaveBeenCalled();
  });

  it('com o Ollama desligado, mostra o aviso de conexão em vez de Nenhum modelo', async () => {
    const user = userEvent.setup();
    bridgeMock.listAnswerModels.mockResolvedValue({ provider: 'ollama', base_url: 'http://localhost:11434', status: 'offline', models: [], latency_ms: 5, cached: false, message: 'Servidor indisponivel ou timeout.' });
    render(<ChatInput onSendMessage={vi.fn()} answerProvider="ollama" answerModel="qchat:latest" onAnswerSaved={vi.fn()} />);

    await user.click(screen.getByRole('button', { name: 'Como responder: qchat' }));

    expect(await screen.findByText('Não consegui conectar ao Ollama em http://localhost:11434. Inicie o Ollama e tente de novo.')).toBeTruthy();
    expect(screen.queryByText('Nenhum modelo de conversa instalado.')).toBeNull();
  });
});
