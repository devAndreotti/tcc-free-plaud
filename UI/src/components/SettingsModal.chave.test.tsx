import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
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

// Linha do catálogo com os campos que o backend manda; cada teste sobrescreve o que importa.
const linha = (campos: Record<string, unknown>) => ({
  index: 1,
  key: '',
  label: '',
  description: '',
  group: 'Índice',
  value_type: 'string',
  layer: 'simple',
  storage: 'user_settings',
  value: null,
  display_value: null,
  options: [],
  recommended: null,
  secret: false,
  placeholder: null,
  warning: null,
  local_env_path: null,
  ...campos,
});

const catalogoPadrao = [
  linha({ key: 'answer_model', label: 'Modelo de resposta', group: 'LLM', value: 'gpt-4o-mini', display_value: 'gpt-4o-mini' }),
  linha({
    index: 2,
    key: 'audio_model',
    label: 'Modelo de transcrição (voz)',
    group: 'Áudio',
    value_type: 'enum',
    value: 'whisper-small',
    display_value: 'whisper-small',
    options: [{ value: 'whisper-small', label: 'Whisper Small (multilíngue)' }],
  }),
  linha({
    index: 3,
    key: 'audio_language',
    label: 'Idioma da transcrição',
    group: 'Áudio',
    value_type: 'enum',
    value: 'pt',
    display_value: 'pt',
    options: [
      { value: 'auto', label: 'Automático (detectar idioma)' },
      { value: 'pt', label: 'Português' },
      { value: 'en', label: 'Inglês' },
    ],
  }),
];

const chaveSecreta = linha({ index: 4, key: 'answer_api_key', label: 'Chave secreta', group: 'Avançado', secret: true });
const embedding = linha({ index: 5, key: 'embedding_model', label: 'Modelo de embedding', value: 'bge-m3', display_value: 'bge-m3' });
const tamanhoTrecho = linha({ index: 6, key: 'chunk_size', label: 'Tamanho do trecho', value_type: 'int', value: 400, display_value: '400' });

// Configurações como o backend devolve; provedor com chave (openai-compatible) por padrão.
const configuracoes = (extras: Record<string, unknown> = {}) => ({
  answer_provider: 'openai-compatible',
  answer_model: 'gpt-4o-mini',
  answer_base_url: 'https://api.openai.com/v1',
  answer_api_key_configured: false,
  settings_presets: [],
  doctor: { status: 'ok', checks: [], latency_ms: 1, ok_count: 0, warning_count: 0, error_count: 0 },
  settings_catalog: catalogoPadrao,
  ...extras,
});

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

// Avançado começa escondido: 5 cliques em "Desbloquear avançado" liberam a aba.
const abrirAvancado = async (user: ReturnType<typeof userEvent.setup>) => {
  for (let clique = 0; clique < 5; clique += 1) {
    await user.click(screen.getByRole('button', { name: /Desbloquear avançado/ }));
  }
  await user.click(screen.getByRole('button', { name: 'Avançado' }));
};

describe('SettingsModal: chave de API, remoção e rótulos do catálogo', () => {
  afterEach(() => {
    cleanup();
  });

  beforeEach(() => {
    // A liberação da aba Avançado fica no localStorage: cada teste começa com ela escondida.
    window.localStorage.clear();
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

    bridgeMock.getBackendSettings.mockResolvedValue(configuracoes());
    bridgeMock.listVaults.mockResolvedValue(notasList);
    bridgeMock.listVoiceModels.mockResolvedValue([]);
  });

  it('salvar chave: envia o valor digitado ao backend e avisa que foi salva', async () => {
    const user = userEvent.setup();
    bridgeMock.saveApiKey.mockResolvedValue({ configured: true });
    renderModal(<SettingsModal isOpen onClose={vi.fn()} initialTab="ia" />);

    await user.type(await screen.findByLabelText('API key'), 'sk-teste-123');
    await user.click(screen.getByRole('button', { name: 'Salvar API key' }));

    expect(bridgeMock.saveApiKey).toHaveBeenCalledWith('sk-teste-123');
    expect(await screen.findByText('API key salva no .env local.')).toBeTruthy();
    expect((screen.getByLabelText('API key') as HTMLInputElement).value).toBe('');
  });

  it('Salvar API key fica desativado com o campo vazio ou só com espaços', async () => {
    const user = userEvent.setup();
    renderModal(<SettingsModal isOpen onClose={vi.fn()} initialTab="ia" />);
    const campo = await screen.findByLabelText('API key');

    expect((screen.getByRole('button', { name: 'Salvar API key' }) as HTMLButtonElement).disabled).toBe(true);

    await user.type(campo, '   ');
    expect((screen.getByRole('button', { name: 'Salvar API key' }) as HTMLButtonElement).disabled).toBe(true);

    await user.type(campo, 'sk-1');
    expect((screen.getByRole('button', { name: 'Salvar API key' }) as HTMLButtonElement).disabled).toBe(false);
    expect(bridgeMock.saveApiKey).not.toHaveBeenCalled();
  });

  it('Salvar API key fica desativado e mostra Salvando… enquanto a chave é enviada', async () => {
    const user = userEvent.setup();
    let concluirSalvamento!: (resultado: { configured: boolean }) => void;
    bridgeMock.saveApiKey.mockReturnValue(new Promise((resolve) => {
      concluirSalvamento = resolve;
    }));
    renderModal(<SettingsModal isOpen onClose={vi.fn()} initialTab="ia" />);

    await user.type(await screen.findByLabelText('API key'), 'sk-teste-123');
    await user.click(screen.getByRole('button', { name: 'Salvar API key' }));

    const salvando = screen.getByRole('button', { name: 'Salvar API key' }) as HTMLButtonElement;
    expect(salvando.textContent).toBe('Salvando…');
    expect(salvando.disabled).toBe(true);

    await act(async () => {
      concluirSalvamento({ configured: true });
    });
    expect(await screen.findByText('API key salva no .env local.')).toBeTruthy();
    await waitFor(() => expect(screen.getByRole('button', { name: 'Salvar API key' }).textContent).toBe('Salvar'));
  });

  it('Remover chave: o primeiro clique pede confirmação e só o segundo apaga a chave', async () => {
    const user = userEvent.setup();
    bridgeMock.getBackendSettings.mockResolvedValue(configuracoes({ answer_api_key_configured: true }));
    bridgeMock.saveApiKey.mockResolvedValue({ configured: false });
    renderModal(<SettingsModal isOpen onClose={vi.fn()} initialTab="ia" />);

    const remover = await screen.findByRole('button', { name: 'Remover chave' });
    expect(remover.className).not.toContain('btn--danger');

    await user.click(remover);
    const confirmar = screen.getByRole('button', { name: 'Confirmar remoção' });
    expect(confirmar.className).toContain('btn--danger');
    expect(bridgeMock.saveApiKey).not.toHaveBeenCalled();

    await user.click(confirmar);
    expect(bridgeMock.saveApiKey).toHaveBeenCalledWith('');
    expect(await screen.findByText('API key removida do .env local.')).toBeTruthy();
    await waitFor(() => expect(screen.getByRole('button', { name: 'Remover chave' })).toBeTruthy());
  });

  it('Remover chave: tirar o foco do botão cancela a confirmação sem apagar a chave', async () => {
    const user = userEvent.setup();
    bridgeMock.getBackendSettings.mockResolvedValue(configuracoes({ answer_api_key_configured: true }));
    renderModal(<SettingsModal isOpen onClose={vi.fn()} initialTab="ia" />);

    await user.click(await screen.findByRole('button', { name: 'Remover chave' }));
    fireEvent.blur(screen.getByRole('button', { name: 'Confirmar remoção' }));

    expect(screen.getByRole('button', { name: 'Remover chave' })).toBeTruthy();
    expect(bridgeMock.saveApiKey).not.toHaveBeenCalled();
  });

  it('Remover chave só aparece quando já existe uma chave salva', async () => {
    renderModal(<SettingsModal isOpen onClose={vi.fn()} initialTab="ia" />);

    await screen.findByLabelText('API key');
    expect(screen.queryByRole('button', { name: 'Remover chave' })).toBeNull();
  });

  it('Avançado: presets mostram o rótulo do catálogo, ou a chave crua quando ela não existe no catálogo', async () => {
    const user = userEvent.setup();
    bridgeMock.getBackendSettings.mockResolvedValue(configuracoes({
      settings_catalog: [...catalogoPadrao, tamanhoTrecho],
      settings_presets: [
        {
          key: 'equilibrado',
          label: 'Equilibrado',
          description: 'Meio-termo entre velocidade e precisão.',
          values: { chunk_size: 400, chave_fora_do_catalogo: 'sim' },
        },
      ],
    }));
    renderModal(<SettingsModal isOpen onClose={vi.fn()} />);

    await abrirAvancado(user);

    expect(await screen.findByRole('button', { name: 'Aplicar preset Equilibrado' })).toBeTruthy();
    expect(screen.getByText('Tamanho do trecho', { selector: 'dt' })).toBeTruthy();
    expect(screen.getByText('400', { selector: 'dd' })).toBeTruthy();
    expect(screen.getByText('chave_fora_do_catalogo', { selector: 'dt' })).toBeTruthy();
    expect(screen.getByText('sim', { selector: 'dd' })).toBeTruthy();
  });

  it('Avançado lista só o que não é de IA, de Áudio, secreto nem oculto no desktop', async () => {
    const user = userEvent.setup();
    bridgeMock.getBackendSettings.mockResolvedValue(configuracoes({
      settings_catalog: [...catalogoPadrao, chaveSecreta, embedding, tamanhoTrecho],
    }));
    renderModal(<SettingsModal isOpen onClose={vi.fn()} />);

    await abrirAvancado(user);

    expect(await screen.findByLabelText('Tamanho do trecho')).toBeTruthy();
    expect(screen.queryByLabelText('Chave secreta')).toBeNull();
    expect(screen.queryByLabelText('Modelo de embedding')).toBeNull();
    expect(screen.queryByLabelText('Modelo de resposta')).toBeNull();
    expect(screen.queryByLabelText('Idioma da transcrição')).toBeNull();
  });
});
