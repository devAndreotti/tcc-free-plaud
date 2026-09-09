import { cleanup, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import QueuePanel from './QueuePanel';

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
    render(<QueuePanel />);

    await user.click(screen.getByRole('button', { name: 'Escolher pasta' }));
    await user.click(screen.getByRole('button', { name: 'Indexar' }));

    await waitFor(() => {
      expect(bridgeMock.startIndexJob).toHaveBeenCalledWith('C:\\Vault', false);
    });

    expect(await screen.findByText('job-queue-1')).toBeTruthy();
    expect(screen.getByText('embedding')).toBeTruthy();
    expect(screen.getByText('1/3')).toBeTruthy();
    expect(screen.getByText('10.00 arquivos/s')).toBeTruthy();
    expect(screen.getByRole('progressbar', { name: 'Progresso do job' }).getAttribute('aria-valuenow')).toBe('33');
  });

  it('cancela job ativo sem iniciar outro', async () => {
    const user = userEvent.setup();
    render(<QueuePanel />);

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
    render(<QueuePanel />);

    await user.click(screen.getByRole('button', { name: 'Escolher pasta' }));
    await user.click(screen.getByRole('button', { name: 'Indexar' }));

    expect(await screen.findByRole('alert')).toBeTruthy();
    expect(screen.getByText('data\\corpus\\notes\\rascunho.md')).toBeTruthy();
    expect(screen.getByText('Encoding inválido.')).toBeTruthy();
  });

  it('liga e desliga o watcher de pasta', async () => {
    const user = userEvent.setup();
    render(<QueuePanel />);

    await user.click(screen.getByRole('button', { name: 'Escolher pasta' }));
    await user.click(screen.getByRole('button', { name: 'Monitorar pasta' }));

    await waitFor(() => {
      expect(bridgeMock.startWatcher).toHaveBeenCalledWith('C:\\Vault');
    });
    expect(await screen.findByRole('button', { name: 'Parar monitoramento' })).toBeTruthy();

    await user.click(screen.getByRole('button', { name: 'Parar monitoramento' }));
    await waitFor(() => {
      expect(bridgeMock.stopWatcher).toHaveBeenCalled();
    });
    expect(await screen.findByRole('button', { name: 'Monitorar pasta' })).toBeTruthy();
  });
});