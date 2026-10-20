import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import SettingsModal from './SettingsModal';
import { VaultsProvider } from '../contexts/VaultsContext';

const bridgeMock = vi.hoisted(() => ({
  getBackendSettings: vi.fn(),
  saveApiKey: vi.fn(),
  indexVault: vi.fn(),
  applySettingsPreset: vi.fn(),
  testAnswerProvider: vi.fn(),
  saveBackendSetting: vi.fn(),
  saveBackendSettings: vi.fn(),
  listAnswerModels: vi.fn(),
  listVoiceModels: vi.fn(),
  startVoiceModelDownload: vi.fn(),
  getVoiceModelDownload: vi.fn(),
  cancelVoiceModelDownload: vi.fn(),
  listVaults: vi.fn(),
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
    status: 'error',
    checks: [
      { code: 'sqlite', status: 'ok', message: '2 chunks no SQLite.', action: null, latency_ms: 3, details: {} },
      { code: 'api_key', status: 'error', message: 'Chave de API não configurada.', action: 'Configure a chave em IA.', latency_ms: null, details: {} },
      { code: 'audio.device', status: 'warning', message: 'Sem GPU disponível; transcrição em CPU.', action: null, latency_ms: 150, details: {} },
    ],
    latency_ms: 1,
    ok_count: 1,
    warning_count: 1,
    error_count: 1,
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
    {
      index: 3,
      key: 'audio_language',
      label: 'Idioma da transcrição',
      description: 'Idioma usado pelo modelo de voz.',
      group: 'Áudio',
      value_type: 'enum',
      layer: 'simple',
      storage: 'user_settings',
      value: 'pt',
      display_value: 'pt',
      options: [
        { value: 'auto', label: 'Automático (detectar idioma)' },
        { value: 'pt', label: 'Português' },
        { value: 'en', label: 'Inglês' },
      ],
      recommended: 'pt',
      secret: false,
      placeholder: null,
      warning: null,
      local_env_path: null,
    },
  ],
};

const whisperModel = {
  id: 'whisper-small',
  engine: 'faster-whisper',
  format: 'ctranslate2',
  repo_id: 'org/whisper',
  revision: 'rev',
  languages: ['pt', 'en'],
  license: 'MIT',
  files: [{ path: 'model.bin', size: 1000, sha256: 'x' }],
  installed: true,
  size_bytes: 1000,
  label: 'Whisper Small',
  description: 'Multilíngue, boa precisão geral.',
  speed_tier: 'medio' as const,
  quality_tier: 'alta' as const,
  recommended: true,
  supports_auto_language: true,
  selectable: true,
};

const moonshineModel = {
  id: 'moonshine-tiny-en',
  engine: 'moonshine',
  format: 'onnx',
  repo_id: 'org/moonshine',
  revision: 'rev',
  languages: ['en'],
  license: 'MIT',
  files: [{ path: 'model.onnx', size: 1000, sha256: 'x' }],
  installed: true,
  size_bytes: 1000,
  label: 'Moonshine Tiny',
  description: 'Só inglês, muito rápido e leve.',
  speed_tier: 'rapido' as const,
  quality_tier: 'basica' as const,
  recommended: false,
  supports_auto_language: false,
  selectable: true,
};

const notasList = {
  active: 'notas',
  vaults: [
    {
      id: 'notas',
      name: 'Notas pessoais',
      icon: 'notes',
      color: 'violet',
      folders: [],
      embedding_model: null,
      created_at: '2026-10-18T12:00:00-03:00',
      sqlite_path: null,
      vector_store_dir: null,
    },
  ],
};

// O modal lê a vault ativa pelo VaultsProvider, como no app.
const renderModal = (ui: React.ReactNode) => render(<VaultsProvider>{ui}</VaultsProvider>);

describe('SettingsModal', () => {
  afterEach(() => {
    cleanup();
    window.localStorage.removeItem('escolio.avancadoLiberado');
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
    bridgeMock.listVaults.mockReset();

    bridgeMock.getBackendSettings.mockResolvedValue(backendSettings);
    bridgeMock.listVaults.mockResolvedValue(notasList);
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
    renderModal(<SettingsModal isOpen onClose={vi.fn()} />);

    expect(await screen.findByLabelText('Modelo de transcrição (voz)')).toBeTruthy();
    expect(screen.queryByLabelText('Modelo de resposta')).toBeNull();
  });

  it('na aba Vaults não há barra de salvar: a aba explica que as mudanças valem na hora', async () => {
    renderModal(<SettingsModal isOpen onClose={vi.fn()} initialTab="vaults" />);

    expect(await screen.findByText(/Mudanças aqui valem na\s+hora/)).toBeTruthy();
    expect(screen.queryByRole('region', { name: 'Alterações não salvas' })).toBeNull();
    expect(screen.queryByText('Nenhuma alteração')).toBeNull();
  });

  it('explica cada opção técnica no dropdown e abaixo do select (ex.: Auto, CPU, CUDA)', async () => {
    const user = userEvent.setup();
    const deviceRow = {
      ...backendSettings.settings_catalog[2],
      index: 4,
      key: 'audio_device',
      label: 'Device de transcrição',
      description: 'Onde roda o modelo de voz.',
      value: 'auto',
      display_value: 'auto',
      recommended: 'auto',
      options: [
        { value: 'auto', label: 'Auto', description: 'Usa a placa de vídeo NVIDIA (CUDA) se houver; senão, o processador.' },
        { value: 'cpu', label: 'CPU', description: 'Roda no processador. Funciona em qualquer PC.' },
        { value: 'cuda', label: 'CUDA', description: 'Roda na placa de vídeo NVIDIA.' },
      ],
    };
    bridgeMock.getBackendSettings.mockResolvedValue({
      ...backendSettings,
      settings_catalog: [...backendSettings.settings_catalog, deviceRow],
    });

    renderModal(<SettingsModal isOpen onClose={vi.fn()} />);
    expect(await screen.findByText('Usa a placa de vídeo NVIDIA (CUDA) se houver; senão, o processador.')).toBeTruthy();
    expect(screen.getAllByText('Recomendado: Auto').length).toBeGreaterThan(0);

    await user.click(screen.getByRole('combobox', { name: 'Device de transcrição' }));
    const listbox = screen.getByRole('listbox', { name: 'Device de transcrição' });
    expect(within(listbox).getByText('Roda na placa de vídeo NVIDIA.')).toBeTruthy();
    await user.click(within(listbox).getByRole('option', { name: 'CPU' }));

    expect(screen.getByText('Roda no processador. Funciona em qualquer PC.')).toBeTruthy();
  });

  it('IA local: lista os modelos instalados ao abrir a aba e o campo Modelo vira lista', async () => {
    const user = userEvent.setup();
    renderModal(<SettingsModal isOpen onClose={vi.fn()} />);

    await user.click(screen.getByRole('button', { name: 'IA' }));
    const model = await screen.findByRole('combobox', { name: 'Modelo de resposta' });
    expect(bridgeMock.listAnswerModels).toHaveBeenCalledWith({ provider: 'ollama', baseUrl: '' });
    // O modelo salvo não está instalado: continua na lista, com o aviso
    expect(screen.getByText('Não está instalado no Ollama: escolha um da lista.')).toBeTruthy();
    // IA local não pede API key
    expect(screen.queryByLabelText('API key')).toBeNull();

    await user.click(model);
    await user.click(within(screen.getByRole('listbox', { name: 'Modelo de resposta' })).getByRole('option', { name: 'mistral:7b' }));

    expect(await screen.findByRole('region', { name: 'Alterações não salvas' })).toBeTruthy();
    expect(bridgeMock.saveBackendSetting).not.toHaveBeenCalled();
  });

  it('Testar usa o provedor e o modelo que estão na tela, mesmo sem salvar', async () => {
    const user = userEvent.setup();
    bridgeMock.testAnswerProvider.mockResolvedValue({
      provider: 'ollama', model: 'mistral:7b', base_url: null, status: 'ok', latency_ms: 812, error: null,
    });
    renderModal(<SettingsModal isOpen onClose={vi.fn()} initialTab="ia" />);

    await user.click(await screen.findByRole('combobox', { name: 'Modelo de resposta' }));
    await user.click(within(screen.getByRole('listbox', { name: 'Modelo de resposta' })).getByRole('option', { name: 'mistral:7b' }));
    await user.click(screen.getByRole('button', { name: 'Testar provider' }));

    expect(bridgeMock.testAnswerProvider).toHaveBeenCalledWith({ provider: 'ollama', model: 'mistral:7b', baseUrl: '' });
    expect(await screen.findByText('Ollama respondeu em 812 ms com mistral:7b.')).toBeTruthy();
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
      selectable: true,
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
      selectable: true,
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

    renderModal(<SettingsModal isOpen onClose={vi.fn()} />);
    await screen.findByRole('radiogroup', { name: 'Modelo de transcrição (voz)' });

    await user.click(screen.getByRole('radio', { name: 'Moonshine Tiny' }));

    expect(await screen.findByRole('button', { name: 'Baixar modelo' })).toBeTruthy();

    await user.click(screen.getByRole('button', { name: 'Baixar modelo' }));
    await waitFor(() => {
      expect(bridgeMock.startVoiceModelDownload).toHaveBeenCalledWith('moonshine-tiny-en');
    });

    await act(async () => {
      await vi.advanceTimersByTimeAsync(1500);
    });

    const moonshineCard = screen.getByRole('radio', { name: 'Moonshine Tiny' });
    await waitFor(() => expect(within(moonshineCard).queryByText('Instalado.')).toBeTruthy());

    vi.useRealTimers();
  });

  it('baixa o componente silero-vad pela aba Voz sem oferece-lo como modelo de transcricao', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const user = userEvent.setup({ delay: null });

    const sileroVad = {
      id: 'silero-vad',
      engine: 'silero',
      format: 'onnx',
      repo_id: 'snakers4/silero-vad',
      revision: 'rev',
      languages: [],
      license: 'MIT',
      files: [{ path: 'silero_vad.onnx', size: 1_800_000, sha256: 'x' }],
      installed: false,
      size_bytes: 1_800_000,
      label: 'Detector de fala (VAD)',
      description: 'Componente interno usado para detectar trechos com fala antes de transcrever.',
      speed_tier: 'rapido' as const,
      quality_tier: 'alta' as const,
      recommended: false,
      supports_auto_language: false,
      selectable: false,
    };

    bridgeMock.listVoiceModels
      .mockResolvedValueOnce([whisperModel, sileroVad])
      .mockResolvedValue([whisperModel, { ...sileroVad, installed: true }]);
    bridgeMock.startVoiceModelDownload.mockResolvedValue({
      job_id: 'dl-vad',
      model_id: 'silero-vad',
      status: 'downloading',
      bytes_completed: 0,
      bytes_total: 1_800_000,
      error_code: null,
      message: null,
    });
    bridgeMock.getVoiceModelDownload.mockResolvedValue({
      job_id: 'dl-vad',
      model_id: 'silero-vad',
      status: 'completed',
      bytes_completed: 1_800_000,
      bytes_total: 1_800_000,
      error_code: null,
      message: 'Modelo baixado e verificado.',
    });

    renderModal(<SettingsModal isOpen onClose={vi.fn()} />);
    await screen.findByRole('radiogroup', { name: 'Modelo de transcrição (voz)' });

    // silero-vad nunca aparece como opcao de modelo de transcricao.
    expect(screen.queryByRole('radio', { name: 'Detector de fala (VAD)' })).toBeNull();

    const vadSection = (await screen.findByText('Componente do sistema')).closest('div.settings-item') as HTMLElement;
    await user.click(within(vadSection).getByRole('button', { name: 'Baixar modelo' }));

    await waitFor(() => {
      expect(bridgeMock.startVoiceModelDownload).toHaveBeenCalledWith('silero-vad');
    });

    await act(async () => {
      await vi.advanceTimersByTimeAsync(1500);
    });

    expect(within(vadSection).queryByText('Instalado.')).toBeTruthy();

    vi.useRealTimers();
  });

  it('desabilita idiomas nao suportados pelo modelo selecionado', async () => {
    const user = userEvent.setup();
    bridgeMock.listVoiceModels.mockResolvedValue([whisperModel, moonshineModel]);

    renderModal(<SettingsModal isOpen onClose={vi.fn()} />);
    await screen.findByRole('radiogroup', { name: 'Modelo de transcrição (voz)' });

    // Com Whisper Small selecionado (default do draft), todo idioma esta habilitado.
    // O campo de idioma depende de listVoiceModels, que resolve depois do campo de modelo.
    await user.click(await screen.findByRole('combobox', { name: 'Idioma da transcrição' }));
    expect(screen.getByRole('option', { name: 'Automático (detectar idioma)' }).getAttribute('aria-disabled')).toBeNull();
    expect(screen.getByRole('option', { name: 'Português' }).getAttribute('aria-disabled')).toBeNull();
    await user.keyboard('{Escape}');

    // Troca para Moonshine Tiny (so ingles, sem auto-detect).
    await user.click(screen.getByRole('radio', { name: 'Moonshine Tiny' }));

    await user.click(screen.getByRole('combobox', { name: 'Idioma da transcrição' }));
    expect(screen.getByRole('option', { name: 'Automático (detectar idioma)' }).getAttribute('aria-disabled')).toBe('true');
    expect(screen.getByRole('option', { name: 'Português' }).getAttribute('aria-disabled')).toBe('true');
    expect(screen.getByRole('option', { name: 'Inglês' }).getAttribute('aria-disabled')).toBeNull();
  });

  it('corrige o idioma no draft ao trocar para um modelo que nao suporta o idioma atual', async () => {
    const user = userEvent.setup();
    bridgeMock.listVoiceModels.mockResolvedValue([whisperModel, moonshineModel]);

    renderModal(<SettingsModal isOpen onClose={vi.fn()} />);
    await screen.findByRole('radiogroup', { name: 'Modelo de transcrição (voz)' });

    // Draft comeca em "pt" (Whisper Small); trocar para Moonshine (so "en")
    // deve corrigir o draft de idioma automaticamente para "en".
    await user.click(screen.getByRole('radio', { name: 'Moonshine Tiny' }));

    expect(screen.getByRole('combobox', { name: 'Idioma da transcrição' }).textContent).toBe('Inglês');
  });

  it('a barra de salvar só aparece com alteração pendente; Descartar volta ao que estava salvo', async () => {
    const user = userEvent.setup();
    bridgeMock.listVoiceModels.mockResolvedValue([whisperModel, moonshineModel]);

    renderModal(<SettingsModal isOpen onClose={vi.fn()} />);
    await screen.findByRole('radiogroup', { name: 'Modelo de transcrição (voz)' });
    expect(screen.queryByRole('region', { name: 'Alterações não salvas' })).toBeNull();

    await user.click(screen.getByRole('radio', { name: 'Moonshine Tiny' }));

    // Modelo e idioma (corrigido para en) mudaram.
    const bar = screen.getByRole('region', { name: 'Alterações não salvas' });
    expect(within(bar).getByText('2 alterações não salvas')).toBeTruthy();
    expect(within(bar).getByRole('button', { name: 'Salvar configurações do backend' })).toBeTruthy();

    await user.click(within(bar).getByRole('button', { name: 'Descartar' }));
    expect(screen.queryByRole('region', { name: 'Alterações não salvas' })).toBeNull();
    expect(screen.getByRole('radio', { name: 'Whisper Small' }).getAttribute('aria-checked')).toBe('true');
  });

  it('salvar fecha a barra e mostra o aviso flutuante de salvo', async () => {
    const user = userEvent.setup();
    bridgeMock.listVoiceModels.mockResolvedValue([whisperModel, moonshineModel]);
    const saved = {
      ...backendSettings,
      settings_catalog: backendSettings.settings_catalog.map((row) =>
        row.key === 'audio_model' ? { ...row, value: 'moonshine-tiny-en' } : row.key === 'audio_language' ? { ...row, value: 'en' } : row
      ),
    };
    bridgeMock.saveBackendSettings.mockResolvedValue(saved);

    renderModal(<SettingsModal isOpen onClose={vi.fn()} />);
    await user.click(await screen.findByRole('radio', { name: 'Moonshine Tiny' }));
    await user.click(screen.getByRole('button', { name: 'Salvar configurações do backend' }));

    expect((await screen.findByRole('status')).textContent).toContain('Configurações salvas.');
    expect(screen.queryByRole('region', { name: 'Alterações não salvas' })).toBeNull();
  });

  it('modelo salvo sem a tag (qchat) é o mesmo que qchat:latest da lista: nada de "não instalado"', async () => {
    bridgeMock.getBackendSettings.mockResolvedValue({
      ...backendSettings,
      settings_catalog: [{ ...backendSettings.settings_catalog[0], value: 'qchat', display_value: 'qchat' }, ...backendSettings.settings_catalog.slice(1)],
    });
    bridgeMock.listAnswerModels.mockResolvedValue({
      provider: 'ollama', base_url: 'http://localhost:11434', status: 'ok', latency_ms: 5, cached: false, message: null,
      models: [{ id: 'qchat:latest', label: 'qchat:latest', provider: 'ollama', details: { parameter_size: '3.1B', quantization_level: 'Q4_K_M' } }],
    });

    renderModal(<SettingsModal isOpen onClose={vi.fn()} initialTab="ia" />);

    expect((await screen.findByRole('combobox', { name: 'Modelo de resposta' })).textContent).toContain('qchat:latest');
    expect(screen.getByText('3.1B · Q4_K_M')).toBeTruthy();
    expect(screen.queryByText(/Não está instalado/)).toBeNull();
  });

  it('IA local desligada: pede para abrir o app e deixa digitar o modelo', async () => {
    bridgeMock.listAnswerModels.mockResolvedValue({
      provider: 'ollama',
      base_url: 'http://localhost:11434',
      status: 'offline',
      models: [],
      latency_ms: 3,
      cached: false,
      message: 'Servidor indisponivel.',
    });

    renderModal(<SettingsModal isOpen onClose={vi.fn()} initialTab="ia" />);

    expect(await screen.findByText(/O Ollama não respondeu em http:\/\/localhost:11434/)).toBeTruthy();
    expect(screen.getAllByText(/offline/).length).toBeGreaterThan(0);
    expect((screen.getByLabelText('Modelo de resposta') as HTMLInputElement).value).toBe('old-model');
  });

  it('regressão: clique no overlay fora do card chama onClose', async () => {
    const user = userEvent.setup();
    const onClose = vi.fn();
    renderModal(<SettingsModal isOpen onClose={onClose} />);

    await user.click(screen.getByRole('button', { name: 'Fechar configurações clicando fora' }));

    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it('regressão: clique dentro do card não chama onClose', async () => {
    const user = userEvent.setup();
    const onClose = vi.fn();
    renderModal(<SettingsModal isOpen onClose={onClose} />);

    await user.click(screen.getByRole('dialog'));

    expect(onClose).not.toHaveBeenCalled();
  });

  it('regressão: mousedown no card e click no overlay não chama onClose', async () => {
    const onClose = vi.fn();
    renderModal(<SettingsModal isOpen onClose={onClose} />);

    fireEvent.mouseDown(screen.getByRole('dialog'));
    fireEvent.click(screen.getByRole('dialog').parentElement as HTMLElement);

    expect(onClose).not.toHaveBeenCalled();
  });

  it('diagnóstico: título com a vault ativa, grupos, rótulos traduzidos e ação do erro', async () => {
    renderModal(<SettingsModal isOpen initialTab="geral" onClose={vi.fn()} />);

    expect(await screen.findByText('Banco de notas (SQLite)')).toBeTruthy();
    expect(await screen.findByRole('heading', { level: 3, name: /Diagnóstico da vault\s*Notas pessoais/ })).toBeTruthy();
    for (const title of ['Índice', 'IA', 'Voz']) {
      expect(screen.getByRole('heading', { level: 4, name: title })).toBeTruthy();
    }
    expect(screen.getByText('Configure a chave em IA.')).toBeTruthy();
    expect(screen.getByText('3 verificações · 1 ms')).toBeTruthy();
    expect(screen.queryByText(/Corpus:/)).toBeNull();
  });

  it('diagnóstico: sem vault ativa, o título fica só em Diagnóstico', async () => {
    bridgeMock.listVaults.mockResolvedValue({ active: '', vaults: [] });
    renderModal(<SettingsModal isOpen initialTab="geral" onClose={vi.fn()} />);

    await screen.findByText('Banco de notas (SQLite)');
    expect(screen.getByRole('heading', { level: 3, name: 'Diagnóstico' })).toBeTruthy();
  });

  it('a pasta padrão do corpus não aparece no Avançado do desktop', async () => {
    window.localStorage.setItem('escolio.avancadoLiberado', '1');
    const corpusRow = {
      index: 4,
      key: 'default_corpus_path',
      label: 'Pasta padrão do corpus',
      description: 'Pasta usada como default para indexar e reconstruir corpus.',
      group: 'Corpus',
      value_type: 'path',
      value: null,
      display_value: null,
      options: [],
      recommended: null,
      secret: false,
      placeholder: null,
      warning: null,
      local_env_path: null,
    };
    const topKRow = {
      index: 5,
      key: 'retrieval_top_k',
      label: 'Trechos por pergunta',
      description: 'Quantos trechos a busca recupera.',
      group: 'Busca',
      value_type: 'int',
      value: 5,
      display_value: '5',
      options: [],
      recommended: 5,
      secret: false,
      placeholder: null,
      warning: null,
      local_env_path: null,
    };
    bridgeMock.getBackendSettings.mockResolvedValue({
      ...backendSettings,
      settings_catalog: [...backendSettings.settings_catalog, corpusRow, topKRow],
    });

    renderModal(<SettingsModal isOpen onClose={vi.fn()} initialTab="avancado" />);

    expect(await screen.findByLabelText('Trechos por pergunta')).toBeTruthy();
    expect(screen.queryByLabelText('Pasta padrão do corpus')).toBeNull();
  });

  it('Aplicar preset fica desligado com rascunho pendente e volta quando o rascunho é descartado', async () => {
    const user = userEvent.setup();
    window.localStorage.setItem('escolio.avancadoLiberado', '1');
    bridgeMock.listVoiceModels.mockResolvedValue([whisperModel, moonshineModel]);
    bridgeMock.getBackendSettings.mockResolvedValue({
      ...backendSettings,
      settings_presets: [{ key: 'cpu_rapido', label: 'CPU rápido', description: 'Busca local sem GPU.', values: { default_ask_strategy: 'lexical' } }],
    });

    renderModal(<SettingsModal isOpen onClose={vi.fn()} />);
    await user.click(await screen.findByRole('radio', { name: 'Moonshine Tiny' }));
    await user.click(screen.getByRole('button', { name: 'Avançado' }));

    const apply = screen.getByRole('button', { name: 'Aplicar preset CPU rápido' });
    expect(apply.hasAttribute('disabled')).toBe(true);
    expect(apply.getAttribute('title')).toBe('Salve ou descarte antes de aplicar');

    await user.click(within(screen.getByRole('region', { name: 'Alterações não salvas' })).getByRole('button', { name: 'Descartar' }));
    expect(screen.getByRole('button', { name: 'Aplicar preset CPU rápido' }).hasAttribute('disabled')).toBe(false);
  });

  it('o card do preset não mostra embedding_model: o desktop não grava esse valor', async () => {
    window.localStorage.setItem('escolio.avancadoLiberado', '1');
    bridgeMock.getBackendSettings.mockResolvedValue({
      ...backendSettings,
      settings_presets: [
        { key: 'cpu_rapido', label: 'CPU rápido', description: 'Busca local sem GPU.', values: { default_ask_strategy: 'lexical', embedding_model: 'chroma-default' } },
      ],
    });

    renderModal(<SettingsModal isOpen onClose={vi.fn()} initialTab="avancado" />);

    expect(await screen.findByText('default_ask_strategy')).toBeTruthy();
    expect(screen.queryByText('embedding_model')).toBeNull();
  });

  it('fechar com rascunho pendente (Esc, fundo ou X) pede confirmação; Continuar editando mantém o modal aberto', async () => {
    const user = userEvent.setup();
    bridgeMock.listVoiceModels.mockResolvedValue([whisperModel, moonshineModel]);
    const onClose = vi.fn();
    renderModal(<SettingsModal isOpen onClose={onClose} />);
    await user.click(await screen.findByRole('radio', { name: 'Moonshine Tiny' }));

    await user.keyboard('{Escape}');
    expect(screen.getByRole('button', { name: 'Descartar alterações' })).toBeTruthy();
    await user.click(screen.getByRole('button', { name: 'Continuar editando' }));

    await user.click(screen.getByRole('button', { name: 'Fechar configurações clicando fora' }));
    expect(screen.getByRole('button', { name: 'Descartar alterações' })).toBeTruthy();
    await user.click(screen.getByRole('button', { name: 'Continuar editando' }));

    await user.click(screen.getByRole('button', { name: 'Fechar configurações' }));
    expect(screen.getByRole('button', { name: 'Descartar alterações' })).toBeTruthy();
    await user.click(screen.getByRole('button', { name: 'Continuar editando' }));

    expect(onClose).not.toHaveBeenCalled();
    expect(screen.getByRole('dialog')).toBeTruthy();
  });

  it('Descartar alterações descarta os rascunhos e fecha', async () => {
    const user = userEvent.setup();
    bridgeMock.listVoiceModels.mockResolvedValue([whisperModel, moonshineModel]);
    const onClose = vi.fn();
    renderModal(<SettingsModal isOpen onClose={onClose} />);
    await user.click(await screen.findByRole('radio', { name: 'Moonshine Tiny' }));
    await user.keyboard('{Escape}');

    await user.click(screen.getByRole('button', { name: 'Descartar alterações' }));

    expect(onClose).toHaveBeenCalledTimes(1);
    expect(screen.getByRole('radio', { name: 'Whisper Small' }).getAttribute('aria-checked')).toBe('true');
  });

  it('sem rascunho pendente, Esc fecha direto', async () => {
    const user = userEvent.setup();
    const onClose = vi.fn();
    renderModal(<SettingsModal isOpen onClose={onClose} />);
    await screen.findByRole('combobox', { name: 'Idioma da transcrição' });

    await user.keyboard('{Escape}');

    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it('Ocultar Avançado tira a aba e a liberação gravada; desbloquear de novo não abre a aba sozinha', async () => {
    const user = userEvent.setup();
    window.localStorage.setItem('escolio.avancadoLiberado', '1');
    renderModal(<SettingsModal isOpen onClose={vi.fn()} initialTab="avancado" />);

    await user.click(await screen.findByRole('button', { name: 'Ocultar Avançado' }));

    expect(screen.queryByRole('button', { name: 'Avançado' })).toBeNull();
    expect(window.localStorage.getItem('escolio.avancadoLiberado')).toBeNull();
    expect(screen.getByRole('button', { name: /Geral/ }).getAttribute('aria-current')).toBe('page');

    for (let i = 0; i < 5; i += 1) {
      await user.click(screen.getByRole('button', { name: /Desbloquear avançado/ }));
    }
    expect(screen.getByRole('button', { name: /Geral/ }).getAttribute('aria-current')).toBe('page');
  });
});
