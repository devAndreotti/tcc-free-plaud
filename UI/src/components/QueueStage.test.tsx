import { cleanup, render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';
import type { IndexJobSnapshot } from '../services/bridge';
import QueueStage from './QueueStage';

const job = (overrides: Partial<IndexJobSnapshot> = {}, progress: Partial<NonNullable<IndexJobSnapshot['progress']>> = {}): IndexJobSnapshot => ({
  job_id: 'job-1',
  status: 'running',
  source_path: 'C:\\Vault',
  started_at: '2026-11-01T19:00:00Z',
  finished_at: null,
  result: null,
  error_code: null,
  message: null,
  last_errors: [],
  cancel_requested: false,
  files_per_second: 12.5,
  chunks_per_second: 80,
  eta_seconds: 9,
  progress: {
    phase: 'embedding',
    current_path: 'C:\\Vault\\Redes\\OSPF.md',
    total_found: 10,
    processed_count: 4,
    indexed_count: 3,
    unchanged_count: 1,
    failed_count: 0,
    skipped_count: 0,
    elapsed_ms: 1200,
    warmup_ms: 0,
    embedding_ms: 800,
    writing_ms: 100,
    committed_count: 3,
    commit_mode_requested: 'auto',
    commit_mode_resolved: 'atomic',
    batch_index: 1,
    batch_total: 2,
    message: null,
    recent_files: [
      { source_path: 'C:\\Vault\\Redes\\BGP.md', status: 'success', chunks: 7 },
      { source_path: 'C:\\Vault\\Diário.md', status: 'unchanged', chunks: 0 },
    ],
    ...progress,
  },
  ...overrides,
});

const renderStage = (snapshot: IndexJobSnapshot | null, onAsk = vi.fn()) =>
  render(
    <QueueStage
      job={snapshot}
      busy={false}
      canReindex
      reindexLabel="Reindexar Vault"
      onReindex={vi.fn()}
      onChooseFolder={vi.fn()}
      onCancel={vi.fn()}
      onAsk={onAsk}
      onIgnoredChanged={vi.fn()}
    />,
  );

describe('QueueStage', () => {
  afterEach(cleanup);

  it('sem job mostra a arte e o convite para indexar', () => {
    renderStage(null);

    expect(screen.getByRole('heading', { name: 'Nada indexando agora' })).toBeTruthy();
    expect(screen.getByRole('button', { name: 'Reindexar Vault' })).toBeTruthy();
    expect(screen.queryByRole('article', { name: 'Job atual' })).toBeNull();
  });

  it('job rodando lista os arquivos que o backend acabou de processar, relativos à pasta', () => {
    renderStage(job());

    const feed = screen.getByRole('region', { name: 'Arquivos processados agora' });
    expect(within(feed).getByText('Redes\\BGP.md')).toBeTruthy();
    expect(within(feed).getByText('7 trechos')).toBeTruthy();
    expect(within(feed).getByText('inalterada')).toBeTruthy();
    expect(within(feed).getByText('Redes\\OSPF.md')).toBeTruthy();
    expect(screen.getByText('Modelo de busca semântica').closest('li')?.getAttribute('aria-current')).toBe('step');
  });

  it('job concluído oferece perguntar à vault e Fechar volta para a arte', async () => {
    const user = userEvent.setup();
    const onAsk = vi.fn();
    renderStage(job({ status: 'success', finished_at: '2026-11-01T19:01:00Z' }, { phase: 'finished', processed_count: 10 }), onAsk);

    expect(screen.getByText('Vault pronta para perguntas')).toBeTruthy();
    await user.click(screen.getByRole('button', { name: 'Perguntar à vault' }));
    expect(onAsk).toHaveBeenCalled();

    await user.click(screen.getByRole('button', { name: 'Fechar' }));
    expect(screen.queryByRole('article', { name: 'Job atual' })).toBeNull();
    expect(screen.getByRole('heading', { name: 'Nada indexando agora' })).toBeTruthy();
  });
});
