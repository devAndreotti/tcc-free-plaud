import { act, cleanup, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import SettingsModal from './SettingsModal';

const bridgeMock = vi.hoisted(() => ({
  getBackendSettings: vi.fn(),
  saveApiKey: vi.fn(),
  indexVault: vi.fn(),
  applySettingsPreset: vi.fn(),
  testAnswerProvider: vi.fn(),
  saveBackendSetting: vi.fn(),
  listAnswerModels: vi.fn(),
  listVoiceModels: vi.fn(),
  startVoiceModelDownload: vi.fn(),
  getVoiceModelDownload: vi.fn(),
  cancelVoiceModelDownload: vi.fn(),
}));

vi.mock('../services/bridge', () => ({
  bridge: bridgeMock,
}));

vi.mock('../hooks/useVaultContext', () => ({
  useVaultContext: () => ({
    vaultPath: String.raw`C:\Vault`,
    selectVault: vi.fn(),
    isScanning: false,
  }),
}));

const backendSettings = {
  answer_provider: 'ollama',
  answer_model: 'old-model',
  answer_base_url: 'http://localhost:11434/v1',
  answer_api_key_configured: false,
  local_env_path: String.raw`pipeline\.env`,
  default_ask_strategy: 'hybrid',
  notes_count: 1,
  sqlite_chunks_count: 2,
  vector_chunks_count: 2,
  settings_presets: [],
  doctor: {
    status: 'ok',
    checks: [],
    latency_ms: 1,
    ok_count: 1,
    warning_count: 0,
    error_count: 0,
  },
  settings_catalog: [
    {
      index: 1,
      key: 'answer_model',
      label: 'Modelo de resposta',
      description: 'Modelo LLM usado pelo provider generativo.',
      group: 'LLM',
      value_type: 'string',
      layer: 'simple',
      storage: 'user_settings',
      value: 'old-model',
      display_value: 'old-model',
      options: [],
      recommended: 'llama3.1:8b',
      secret: false,
      placeholder: 'llama3.1:8b',
      warning: null,
      local_env_path: null,
    },
    {
      index: 2,
      key: 'audio_model',
      label: 'Modelo de transcrição (voz)',
      description: 'Modelo local usado para transcrever o áudio gravado no chat.',
      group: 'Áudio',
      value_type: 'enum',
      layer: 'simple',
      storage: 'user_settings',
      value: 'whisper-small',
      display_value: 'whisper-small',
      options: [{ value: 'whisper-small', label: 'Whisper Small (multilíngue)' }],
      recommended: 'whisper-small',
      secret: false,
      placeholder: null,
      warning: null,
      local_env_path: null,
    },
  ],
};

describe('SettingsModal', () => {
  afterEach(() => {
    cleanup();
  });

  beforeEach(() => {
    bridgeMock.getBackendSettings.mockReset();
    bridgeMock.saveApiKey.mockReset();
    bridgeMock.indexVault.mockReset();
    bridgeMock.applySettingsPreset.mockReset();
    bridgeMock.testAnswerProvider.mockReset();
    bridgeMock.saveBackendSetting.mockReset();
    bridgeMock.listAnswerModels.mockReset();
    bridgeMock.listVoiceModels.mockReset();
    bridgeMock.startVoiceModelDownload.mockReset();
    bridgeMock.getVoiceModelDownload.mockReset();
    bridgeMock.cancelVoiceModelDownload.mockReset();

    bridgeMock.getBackendSettings.mockResolvedValue(backendSettings);
    bridgeMock.listVoiceModels.mockResolvedValue([]);
    bridgeMock.listAnswerModels.mockResolvedValue({
      provider: 'ollama',
      base_url: 'http://localhost:11434',
      status: 'ok',
      models: [
        { id: 'llama3.1:8b', label: 'llama3.1:8b', provider: 'ollama', details: {} },
        { id: 'mistral:7b', label: 'mistral:7b', provider: 'ollama', details: {} },
      ],
      latency_ms: 5,
      cached: false,
      message: null,
    });
  });

  it('abre por padrão na aba Voz com os campos de transcrição', async () => {
    render(<SettingsModal isOpen onClose={vi.fn()} />);

    expect(await screen.findByLabelText('Modelo de transcrição (voz)')).toBeTruthy();
    expect(screen.queryByLabelText('Modelo de resposta')).toBeNull();
  });

  it('lista modelos e preenche draft de answer_model ao clicar', async () => {
    const user = userEvent.setup();
    render(<SettingsModal isOpen onClose={vi.fn()} />);

    await user.click(screen.getByRole('button', { name: 'IA' }));
    await screen.findByLabelText('Modelo de resposta');
    await user.click(screen.getByRole('button', { name: 'Listar modelos' }));
    await screen.findByText('mistral:7b');
    await user.click(screen.getByRole('button', { name: 'Selecionar mistral:7b' }));

    await waitFor(() => {
      expect((screen.getByLabelText('Modelo de resposta') as HTMLInputElement).value).toBe('mistral:7b');
    });
    expect(bridgeMock.saveBackendSetting).not.toHaveBeenCalled();
  });

  it('baixa modelo de voz nao instalado e reflete progresso ate completed', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const user = userEvent.setup({ delay: null });

    const notInstalled = {
      id: 'moonshine-tiny-en',
      engine: 'moonshine',
      format: 'onnx',
      repo_id: 'org/moonshine',
      revision: 'rev',
      languages: ['en'],
      license: 'MIT',
      files: [{ path: 'model.onnx', size: 124_000_000, sha256: 'x' }],
      installed: false,
      size_bytes: 124_000_000,
      label: 'Moonshine Tiny',
      description: 'Só inglês, muito rápido e leve.',
      speed_tier: 'rapido' as const,
      quality_tier: 'basica' as const,
      recommended: false,
      supports_auto_language: false,
    };
    const whisperInstalled = {
      id: 'whisper-small',
      engine: 'faster-whisper',
      format: 'ctranslate2',
      repo_id: 'org/whisper',
      revision: 'rev',
      languages: ['pt', 'en'],
      license: 'MIT',
      files: [{ path: 'model.bin', size: 483_000_000, sha256: 'x' }],
      installed: true,
      size_bytes: 483_000_000,
      label: 'Whisper Small',
      description: 'Multilíngue, boa precisão geral.',
      speed_tier: 'medio' as const,
      quality_tier: 'alta' as const,
      recommended: true,
      supports_auto_language: true,
    };
    const moonshineInstalled = { ...notInstalled, installed: true };

    bridgeMock.listVoiceModels
      .mockResolvedValueOnce([whisperInstalled, notInstalled])
      .mockResolvedValue([whisperInstalled, moonshineInstalled]);
    bridgeMock.startVoiceModelDownload.mockResolvedValue({
      job_id: 'dl-1',
      model_id: 'moonshine-tiny-en',
      status: 'downloading',
      bytes_completed: 0,
      bytes_total: 124_000_000,
      error_code: null,
      message: null,
    });
    bridgeMock.getVoiceModelDownload.mockResolvedValueOnce({
      job_id: 'dl-1',
      model_id: 'moonshine-tiny-en',
      status: 'verifying',
      bytes_completed: 124_000_000,
      bytes_total: 124_000_000,
      error_code: null,
      message: null,
    }).mockResolvedValue({
      job_id: 'dl-1',
      model_id: 'moonshine-tiny-en',
      status: 'completed',
      bytes_completed: 124_000_000,
      bytes_total: 124_000_000,
      error_code: null,
      message: 'Modelo baixado e verificado.',
    });

    render(<SettingsModal isOpen onClose={vi.fn()} />);
    await screen.findByRole('combobox', { name: 'Modelo de transcrição (voz)' });

    await user.click(screen.getByRole('combobox', { name: 'Modelo de transcrição (voz)' }));
    await user.click(await screen.findByRole('option', { name: 'Moonshine Tiny' }));

    expect(await screen.findByRole('button', { name: 'Baixar modelo' })).toBeTruthy();

    await user.click(screen.getByRole('button', { name: 'Baixar modelo' }));
    await waitFor(() => {
      expect(bridgeMock.startVoiceModelDownload).toHaveBeenCalledWith('moonshine-tiny-en');
    });

    await act(async () => {
      await vi.advanceTimersByTimeAsync(1500);
    });

    expect(await screen.findByText('Modelo instalado.')).toBeTruthy();

    vi.useRealTimers();
  });

  it('mostra estado offline sem quebrar modal', async () => {
    const user = userEvent.setup();
    bridgeMock.listAnswerModels.mockResolvedValueOnce({
      provider: 'ollama',
      base_url: 'http://localhost:11434',
      status: 'offline',
      models: [],
      latency_ms: 3,
      cached: false,
      message: 'Servidor indisponivel.',
    });

    render(<SettingsModal isOpen onClose={vi.fn()} />);

    await user.click(screen.getByRole('button', { name: 'IA' }));
    await screen.findByLabelText('Modelo de resposta');
    await user.click(screen.getByRole('button', { name: 'Listar modelos' }));

    expect((await screen.findAllByText(/offline/)).length).toBeGreaterThan(0);
    expect((await screen.findAllByText(/Servidor indisponivel/)).length).toBeGreaterThan(0);
  });
});
