import { useState, type ReactNode } from 'react';
import { act, cleanup, render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import QueuePanel from './QueuePanel';
import { QueueProvider } from '../contexts/QueueContext';
import { VaultProvider } from '../contexts/VaultContext';

// QueuePanel agora depende do QueueContext — todo render precisa do Provider.
// QueueProvider consome o VaultContext, por isso fica dentro do VaultProvider (como em App.tsx).
const Providers = ({ children }: { children: ReactNode }) => (
  <VaultProvider><QueueProvider>{children}</QueueProvider></VaultProvider>
);
const renderQueuePanel = () => render(<Providers><QueuePanel /></Providers>);

const bridgeMock = vi.hoisted(() => ({
  selectFolder: vi.fn(),
  startIndexJob: vi.fn(),
  getIndexJob: vi.fn(),
  cancelIndexJob: vi.fn(),
  startWatcher: vi.fn(),
  stopWatcher: vi.fn(),
  loadVaultPath: vi.fn(),
  saveVaultPath: vi.fn(),
  scanVault: vi.fn(),
  listCorpusRoots: vi.fn(),
  removeCorpusRoot: vi.fn(),
}));

vi.mock('../services/bridge', () => ({
  bridge: bridgeMock,
}));

const runningJob = {
  job_id: 'job-queue-1',
  status: 'running',
  source_path: 'C:\\Vault',
  started_at: '2026-05-26T10:00:00+00:00',
  finished_at: null,
  progress: {
    phase: 'embedding',
    current_path: 'C:\\Vault\\nota.md',
    total_found: 3,
    processed_count: 1,
    indexed_count: 1,
    unchanged_count: 0,
    failed_count: 0,
    skipped_count: 0,
    elapsed_ms: 100,
    warmup_ms: 0,
    embedding_ms: 40,
    writing_ms: 0,
    committed_count: 0,
    commit_mode_requested: 'auto',
    commit_mode_resolved: 'microbatch',
    batch_index: 1,
    batch_total: 2,
    message: 'Processando nota.md',
  },
  result: null,
  error_code: null,
  message: null,
  last_errors: [],
  cancel_requested: false,
  files_per_second: 10,
  chunks_per_second: 20,
  eta_seconds: 1,
};

const CORPUS_ROOTS = [
  { root: 'D:\\Notas\\Obsidian', notes_count: 42 },
  { root: 'D:\\Notas\\Culinaria', notes_count: 7 },
];

describe('QueuePanel', () => {
  afterEach(() => {
    cleanup();
  });

  beforeEach(() => {
    bridgeMock.selectFolder.mockReset();
    bridgeMock.startIndexJob.mockReset();
    bridgeMock.getIndexJob.mockReset();
    bridgeMock.cancelIndexJob.mockReset();
    bridgeMock.startWatcher.mockReset();
    bridgeMock.stopWatcher.mockReset();
    bridgeMock.loadVaultPath.mockReset();
    bridgeMock.saveVaultPath.mockReset();
    bridgeMock.scanVault.mockReset();
    bridgeMock.loadVaultPath.mockResolvedValue('');
    bridgeMock.saveVaultPath.mockResolvedValue(true);
    bridgeMock.scanVault.mockResolvedValue([]);
    bridgeMock.listCorpusRoots.mockResolvedValue([]);
    bridgeMock.removeCorpusRoot.mockReset();

    bridgeMock.selectFolder.mockResolvedValue('C:\\Vault');
    bridgeMock.startIndexJob.mockResolvedValue(runningJob);
    bridgeMock.getIndexJob.mockResolvedValue(runningJob);
    bridgeMock.cancelIndexJob.mockResolvedValue({ ...runningJob, status: 'cancelled', cancel_requested: true });
    bridgeMock.startWatcher.mockResolvedValue({ ok: true, active: true, directory: 'C:\\Vault' });
    bridgeMock.stopWatcher.mockResolvedValue({ ok: true, active: false, directory: null });
  });

  it('cria job e mostra progresso consultado do backend', async () => {
    const user = userEvent.setup();
    renderQueuePanel();

    await user.click(screen.getByRole('button', { name: 'Escolher pasta' }));
    await user.click(screen.getByRole('button', { name: 'Indexar' }));

    await waitFor(() => {
      expect(bridgeMock.startIndexJob).toHaveBeenCalledWith('C:\\Vault', false);
    });

    expect(await screen.findByText('job-queue-1')).toBeTruthy();
    // Etapa atual marcada, com o lote do embedding.
    expect(screen.getByText('Embedding').closest('li')?.getAttribute('aria-current')).toBe('step');
    expect(screen.getByText('lote 1 de 2')).toBeTruthy();
    expect(screen.getByText('de 3 arquivos')).toBeTruthy();
    expect(screen.getByText('10,0')).toBeTruthy();
    expect(screen.getByText('auto → microbatch')).toBeTruthy();
    expect(screen.getByRole('progressbar', { name: 'Progresso do job' }).getAttribute('aria-valuenow')).toBe('33');
  });

  it('cancela job ativo sem iniciar outro', async () => {
    const user = userEvent.setup();
    renderQueuePanel();

    await user.click(screen.getByRole('button', { name: 'Escolher pasta' }));
    await user.click(screen.getByRole('button', { name: 'Indexar' }));
    await screen.findByText('job-queue-1');
    await user.click(screen.getByRole('button', { name: 'Cancelar' }));

    await waitFor(() => {
      expect(bridgeMock.cancelIndexJob).toHaveBeenCalledWith('job-queue-1');
    });
  });

  it('mostra últimos erros do job como alertas', async () => {
    const user = userEvent.setup();
    bridgeMock.getIndexJob.mockResolvedValue({
      ...runningJob,
      last_errors: [
        { source_path: 'data\\corpus\\notes\\rascunho.md', message: 'Encoding inválido.', error_code: 'BAD_ENCODING' },
      ],
    });
    renderQueuePanel();

    await user.click(screen.getByRole('button', { name: 'Escolher pasta' }));
    await user.click(screen.getByRole('button', { name: 'Indexar' }));

    expect(await screen.findByRole('alert')).toBeTruthy();
    expect(screen.getByText('data\\corpus\\notes\\rascunho.md')).toBeTruthy();
    expect(screen.getByText('Encoding inválido.')).toBeTruthy();
  });

  it('falha de modelo de voz leva direto para Configurações › Voz', async () => {
    const user = userEvent.setup();
    const onOpenSettings = vi.fn();
    bridgeMock.getIndexJob.mockResolvedValue({
      ...runningJob,
      last_errors: [
        { source_path: 'Audio/aula-07.m4a', message: 'Modelo de voz não instalado.', error_code: 'AUDIO_MODEL_NOT_READY' },
      ],
    });
    render(<Providers><QueuePanel onOpenSettings={onOpenSettings} /></Providers>);

    await user.click(screen.getByRole('button', { name: 'Escolher pasta' }));
    await user.click(screen.getByRole('button', { name: 'Indexar' }));
    await user.click(await screen.findByRole('button', { name: 'Abrir Voz' }));

    expect(onOpenSettings).toHaveBeenCalledWith('voz');
  });

  it('liga e desliga o watcher de pasta', async () => {
    const user = userEvent.setup();
    renderQueuePanel();

    await user.click(screen.getByRole('button', { name: 'Escolher pasta' }));
    await user.click(screen.getByRole('checkbox', { name: 'Monitorar pasta' }));

    await waitFor(() => {
      expect(bridgeMock.startWatcher).toHaveBeenCalledWith('C:\\Vault');
    });
    await waitFor(() => {
      expect((screen.getByRole('checkbox', { name: 'Monitorar pasta' }) as HTMLInputElement).checked).toBe(true);
    });

    await user.click(screen.getByRole('checkbox', { name: 'Monitorar pasta' }));
    await waitFor(() => {
      expect(bridgeMock.stopWatcher).toHaveBeenCalled();
    });
    await waitFor(() => {
      expect((screen.getByRole('checkbox', { name: 'Monitorar pasta' }) as HTMLInputElement).checked).toBe(false);
    });
  });

  it('continua consultando o job mesmo depois de QueuePanel ser desmontado (troca de aba)', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const user = userEvent.setup({ delay: null });

    // Simula a troca de aba do App: QueueProvider fica montado o tempo
    // todo, mas QueuePanel é desmontado/remontado conforme um toggle,
    // exatamente como {workspaceView === 'queue' && <QueuePanel/>} em App.tsx.
    const Harness = () => {
      const [showQueue, setShowQueue] = useState(true);
      return (
        <Providers>
          <button type="button" onClick={() => setShowQueue((prev) => !prev)}>
            alternar aba
          </button>
          {showQueue && <QueuePanel />}
        </Providers>
      );
    };

    render(<Harness />);

    await user.click(screen.getByRole('button', { name: 'Escolher pasta' }));
    await screen.findByDisplayValue('C:\\Vault');
    await user.click(screen.getByRole('button', { name: 'Indexar' }));
    await waitFor(() => {
      expect(bridgeMock.startIndexJob).toHaveBeenCalled();
    });

    const callsBeforeLeaving = bridgeMock.getIndexJob.mock.calls.length;

    // Sai da aba (desmonta QueuePanel, mas o QueueProvider continua montado).
    await user.click(screen.getByRole('button', { name: 'alternar aba' }));
    expect(screen.queryByText('job-queue-1')).toBeNull();

    // Avança o tempo do polling (1s) sem QueuePanel montado.
    await act(async () => {
      await vi.advanceTimersByTimeAsync(3000);
    });

    expect(bridgeMock.getIndexJob.mock.calls.length).toBeGreaterThan(callsBeforeLeaving);

    // Volta para a aba: o job continua lá, sem precisar recriar nada.
    await user.click(screen.getByRole('button', { name: 'alternar aba' }));
    expect(await screen.findByText('job-queue-1')).toBeTruthy();

    vi.useRealTimers();
  });

  it('indexar com vault vazio adota a pasta indexada como vault', async () => {
    const user = userEvent.setup();
    renderQueuePanel();

    await user.click(screen.getByRole('button', { name: 'Escolher pasta' }));
    await user.click(screen.getByRole('button', { name: 'Indexar' }));

    await waitFor(() => expect(bridgeMock.startIndexJob).toHaveBeenCalled());
    expect(bridgeMock.saveVaultPath).toHaveBeenCalledWith('C:\\Vault');
    expect(bridgeMock.scanVault).toHaveBeenCalledWith('C:\\Vault');
  });

  it('indexar não troca um vault já configurado em Configurações', async () => {
    bridgeMock.loadVaultPath.mockResolvedValue('D:\\Escolhido');
    const user = userEvent.setup();
    renderQueuePanel();
    await waitFor(() => expect(bridgeMock.scanVault).toHaveBeenCalledWith('D:\\Escolhido'));

    await user.click(screen.getByRole('button', { name: 'Escolher pasta' }));
    await user.click(screen.getByRole('button', { name: 'Indexar' }));

    await waitFor(() => expect(bridgeMock.startIndexJob).toHaveBeenCalled());
    expect(bridgeMock.saveVaultPath).not.toHaveBeenCalled();
  });

  it('reescaneia o vault quando o job da pasta do vault conclui', async () => {
    bridgeMock.loadVaultPath.mockResolvedValue('C:\\Vault');
    bridgeMock.getIndexJob.mockResolvedValue({ ...runningJob, status: 'success', finished_at: '2026-05-26T10:01:00+00:00' });
    const user = userEvent.setup();
    renderQueuePanel();
    await waitFor(() => expect(bridgeMock.scanVault).toHaveBeenCalledTimes(1));

    await user.click(screen.getByRole('button', { name: 'Escolher pasta' }));
    await user.click(screen.getByRole('button', { name: 'Indexar' }));

    await waitFor(() => expect(bridgeMock.scanVault).toHaveBeenCalledTimes(2), { timeout: 3000 });
    expect(bridgeMock.saveVaultPath).not.toHaveBeenCalled();
  });

  it('regressao: lista as pastas indexadas no corpus com a contagem de notas', async () => {
    bridgeMock.listCorpusRoots.mockResolvedValue(CORPUS_ROOTS);
    renderQueuePanel();

    expect(await screen.findByText('Obsidian')).toBeTruthy();
    expect(screen.getByText('42 notas')).toBeTruthy();
    expect(screen.getByText('Culinaria')).toBeTruthy();
    expect(screen.getByText('7 notas')).toBeTruthy();
    expect(screen.getByTitle('D:\\Notas\\Culinaria')).toBeTruthy();
  });

  it('regressao: Reindexar usa a raiz da linha e chama startIndexJob com ela', async () => {
    bridgeMock.listCorpusRoots.mockResolvedValue(CORPUS_ROOTS);
    const user = userEvent.setup();
    renderQueuePanel();

    const row = (await screen.findByText('Culinaria')).closest('li') as HTMLElement;
    await user.click(within(row).getByRole('button', { name: 'Reindexar' }));

    await waitFor(() => {
      expect(bridgeMock.startIndexJob).toHaveBeenCalledWith('D:\\Notas\\Culinaria', false);
    });
  });

  it('regressao: Remover do corpus só chama removeCorpusRoot depois de digitar REMOVER e recarrega a lista', async () => {
    bridgeMock.listCorpusRoots.mockResolvedValueOnce(CORPUS_ROOTS).mockResolvedValue([CORPUS_ROOTS[0]]);
    bridgeMock.removeCorpusRoot.mockResolvedValue({ ok: true, removed_notes: 7 });
    const user = userEvent.setup();
    renderQueuePanel();

    const row = (await screen.findByText('Culinaria')).closest('li') as HTMLElement;
    await user.click(within(row).getByRole('button', { name: 'Remover' }));
    expect((within(row).getByRole('button', { name: 'Remover do corpus' }) as HTMLButtonElement).disabled).toBe(true);
    expect(bridgeMock.removeCorpusRoot).not.toHaveBeenCalled();

    await user.type(within(row).getByLabelText('Digite REMOVER para confirmar'), 'REMOVER');
    await user.click(within(row).getByRole('button', { name: 'Remover do corpus' }));

    await waitFor(() => {
      expect(bridgeMock.removeCorpusRoot).toHaveBeenCalledWith('D:\\Notas\\Culinaria', 'REMOVER');
    });
    await waitFor(() => {
      expect(screen.queryByText('Culinaria')).toBeNull();
    });
    expect(bridgeMock.listCorpusRoots).toHaveBeenCalledTimes(2);
  });

  it('regressao: Remover do corpus mostra Removendo… e desabilita o painel enquanto a remoção roda', async () => {
    bridgeMock.listCorpusRoots.mockResolvedValue(CORPUS_ROOTS);
    bridgeMock.removeCorpusRoot.mockReturnValue(new Promise(() => {}));
    const user = userEvent.setup();
    renderQueuePanel();

    const row = (await screen.findByText('Culinaria')).closest('li') as HTMLElement;
    await user.click(within(row).getByRole('button', { name: 'Remover' }));
    await user.type(within(row).getByLabelText('Digite REMOVER para confirmar'), 'REMOVER');
    await user.click(within(row).getByRole('button', { name: 'Remover do corpus' }));

    const pending = await within(row).findByRole('button', { name: 'Removendo…' });
    expect((pending as HTMLButtonElement).disabled).toBe(true);
    expect((within(row).getByLabelText('Digite REMOVER para confirmar') as HTMLInputElement).disabled).toBe(true);
    expect((within(row).getByRole('button', { name: 'Cancelar' }) as HTMLButtonElement).disabled).toBe(true);
  });

  it('regressao: Remover do corpus mostra N notas removidas, avisa a sidebar e recarrega a lista', async () => {
    bridgeMock.listCorpusRoots.mockResolvedValueOnce(CORPUS_ROOTS).mockResolvedValue([CORPUS_ROOTS[0]]);
    bridgeMock.removeCorpusRoot.mockResolvedValue({ ok: true, removed_notes: 7 });
    const onCorpusChanged = vi.fn();
    window.addEventListener('escolio:corpus-changed', onCorpusChanged);
    const user = userEvent.setup();
    renderQueuePanel();

    const row = (await screen.findByText('Culinaria')).closest('li') as HTMLElement;
    await user.click(within(row).getByRole('button', { name: 'Remover' }));
    await user.type(within(row).getByLabelText('Digite REMOVER para confirmar'), 'REMOVER');
    await user.click(within(row).getByRole('button', { name: 'Remover do corpus' }));

    expect(await screen.findByText('Culinaria saiu do corpus: 7 notas removidas.')).toBeTruthy();
    await waitFor(() => {
      expect(screen.queryByText('Culinaria')).toBeNull();
    });
    expect(bridgeMock.listCorpusRoots).toHaveBeenCalledTimes(2);
    expect(onCorpusChanged).toHaveBeenCalled();
    window.removeEventListener('escolio:corpus-changed', onCorpusChanged);
  });

  it('regressao: Remover do corpus sai de Removendo… e mostra o erro quando o bridge rejeita', async () => {
    bridgeMock.listCorpusRoots.mockResolvedValue(CORPUS_ROOTS);
    bridgeMock.removeCorpusRoot.mockRejectedValue(new Error('Backend indisponível'));
    const user = userEvent.setup();
    renderQueuePanel();

    const row = (await screen.findByText('Culinaria')).closest('li') as HTMLElement;
    await user.click(within(row).getByRole('button', { name: 'Remover' }));
    await user.type(within(row).getByLabelText('Digite REMOVER para confirmar'), 'REMOVER');
    await user.click(within(row).getByRole('button', { name: 'Remover do corpus' }));

    expect(await screen.findByText('Backend indisponível')).toBeTruthy();
    expect(within(row).queryByRole('button', { name: 'Removendo…' })).toBeNull();
    expect((within(row).getByRole('button', { name: 'Remover do corpus' }) as HTMLButtonElement).disabled).toBe(false);
  });
});
