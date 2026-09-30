import { useState } from 'react';
import { act, cleanup, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import QueuePanel from './QueuePanel';
import { QueueProvider } from '../contexts/QueueContext';

// QueuePanel agora depende do QueueContext — todo render precisa do Provider.
const renderQueuePanel = () => render(<QueueProvider><QueuePanel /></QueueProvider>);

const bridgeMock = vi.hoisted(() => ({
  selectFolder: vi.fn(),
  startIndexJob: vi.fn(),
  getIndexJob: vi.fn(),
  cancelIndexJob: vi.fn(),
  startWatcher: vi.fn(),
  stopWatcher: vi.fn(),
  pollWatcherEvents: vi.fn(),
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
    bridgeMock.pollWatcherEvents.mockReset();

    bridgeMock.selectFolder.mockResolvedValue('C:\\Vault');
    bridgeMock.startIndexJob.mockResolvedValue(runningJob);
    bridgeMock.getIndexJob.mockResolvedValue(runningJob);
    bridgeMock.cancelIndexJob.mockResolvedValue({ ...runningJob, status: 'cancelled', cancel_requested: true });
    bridgeMock.startWatcher.mockResolvedValue({ ok: true, active: true, directory: 'C:\\Vault' });
    bridgeMock.stopWatcher.mockResolvedValue({ ok: true, active: false, directory: null });
    bridgeMock.pollWatcherEvents.mockResolvedValue([]);
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
        { source_path: 'Audio\aula-07.m4a', message: 'Modelo de voz não instalado.', error_code: 'AUDIO_MODEL_NOT_READY' },
      ],
    });
    render(<QueueProvider><QueuePanel onOpenSettings={onOpenSettings} /></QueueProvider>);

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
        <QueueProvider>
          <button type="button" onClick={() => setShowQueue((prev) => !prev)}>
            alternar aba
          </button>
          {showQueue && <QueuePanel />}
        </QueueProvider>
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
});