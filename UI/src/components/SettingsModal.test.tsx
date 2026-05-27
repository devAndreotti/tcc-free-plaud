import { cleanup, render, screen, waitFor } from '@testing-library/react';
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

    bridgeMock.getBackendSettings.mockResolvedValue(backendSettings);
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

  it('lista modelos e preenche draft de answer_model ao clicar', async () => {
    const user = userEvent.setup();
    render(<SettingsModal isOpen onClose={vi.fn()} />);

    await screen.findByLabelText('Modelo de resposta');
    await user.click(screen.getByRole('button', { name: 'Listar modelos' }));
    await screen.findByText('mistral:7b');
    await user.click(screen.getByRole('button', { name: 'Selecionar mistral:7b' }));

    await waitFor(() => {
      expect((screen.getByLabelText('Modelo de resposta') as HTMLInputElement).value).toBe('mistral:7b');
    });
    expect(bridgeMock.saveBackendSetting).not.toHaveBeenCalled();
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

    await screen.findByLabelText('Modelo de resposta');
    await user.click(screen.getByRole('button', { name: 'Listar modelos' }));

    expect((await screen.findAllByText(/offline/)).length).toBeGreaterThan(0);
    expect((await screen.findAllByText(/Servidor indisponivel/)).length).toBeGreaterThan(0);
  });
});
