import { cleanup, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import BenchmarkPanel from './BenchmarkPanel';

// Regressão: um resultado SEM os campos novos (reranked, baseline_ci, coverage, faithfulness)
// tem que produzir exatamente o mesmo painel de antes.

const bridgeMock = vi.hoisted(() => ({
  selectBenchmarkSuite: vi.fn(),
  runBenchmarkCompare: vi.fn(),
}));

vi.mock('../services/bridge', () => ({
  bridge: bridgeMock,
}));

const legacyResult = {
  ok: true,
  comparison_id: 'cmp-legacy',
  suite_name: 'suite-legacy',
  summaries: {
    lexical: {
      strategy: 'lexical',
      case_count: 2,
      query_count: 4,
      mrr: 0.75,
      recall_at_3: 0.75,
      recall_at_5: 0.75,
      recall_at_10: 0.75,
      duration_ms: 20,
      avg_query_latency_ms: 3,
    },
    hybrid: {
      strategy: 'hybrid',
      case_count: 2,
      query_count: 4,
      mrr: 0.9,
      recall_at_3: 1,
      recall_at_5: 1,
      recall_at_10: 1,
      duration_ms: 44,
      avg_query_latency_ms: 6,
    },
  },
  corpus: {
    note_count: 2,
    positive_count: 4,
    negative_count: 2,
    retrieval_depth: 10,
    summaries: {
      lexical: {
        strategy: 'lexical', case_count: 2, query_count: 4, mrr: 0.75, recall_at_3: 0.75, recall_at_5: 0.75,
        recall_at_10: 0.75, duration_ms: 20, avg_query_latency_ms: 3, p50_query_latency_ms: 3,
        p95_query_latency_ms: 5, mrr_ci: [0.5, 1],
        abstention: { accuracy: 0.5, precision: 1, recall: 0, f1: 0, support: 2, answered_positive_rate: 0.75 },
      },
      hybrid: {
        strategy: 'hybrid', case_count: 2, query_count: 4, mrr: 0.9, recall_at_3: 1, recall_at_5: 1,
        recall_at_10: 1, duration_ms: 44, avg_query_latency_ms: 6, p50_query_latency_ms: 6,
        p95_query_latency_ms: 8, mrr_ci: [0.7, 1],
        abstention: { accuracy: 0.75, precision: 1, recall: 0.5, f1: 0.66, support: 2, answered_positive_rate: 1 },
      },
    },
  },
  json_report_path: 'data/results/cmp-legacy.json',
  csv_report_path: 'data/results/cmp-legacy.csv',
  settings_snapshot: {
    embedding_model: 'fake-hash',
    embedding_device: 'cpu',
    default_ask_strategy: 'hybrid',
    retrieval_top_k: 4,
    default_chunk_size: 800,
    default_chunk_overlap: 120,
    answer_provider: 'extractive',
  },
};

describe('BenchmarkPanel sem os campos novos (regressão)', () => {
  beforeEach(() => {
    bridgeMock.selectBenchmarkSuite.mockReset();
    bridgeMock.runBenchmarkCompare.mockReset();
    bridgeMock.runBenchmarkCompare.mockResolvedValue(legacyResult);
  });

  afterEach(() => {
    cleanup();
  });

  it('renderiza o mesmo DOM de antes e não cria as seções novas', async () => {
    const user = userEvent.setup();
    const { container } = render(<BenchmarkPanel />);

    await user.type(screen.getByLabelText('suite.json'), 'suite.json');
    await user.click(screen.getByRole('button', { name: 'Rodar comparação' }));
    await screen.findByText('cmp-legacy');

    expect(screen.queryByRole('region', { name: 'Ablação do ranking' })).toBeNull();
    expect(screen.queryByRole('region', { name: 'Cobertura por tipo de pergunta' })).toBeNull();
    expect(screen.queryByRole('region', { name: 'Faithfulness' })).toBeNull();
    expect(screen.queryByText(/Ablação do ranking/)).toBeNull();
    expect(screen.queryByText(/Cobertura por tipo de pergunta/)).toBeNull();
    expect(container.querySelector('.bench__pair')).toBeNull();
    expect(container.querySelector('.bench__abl-row')).toBeNull();
    expect(container.querySelector('.bench__faith-value')).toBeNull();

    expect(container.querySelector('#benchmark-panel')?.innerHTML).toMatchSnapshot();
  });

  it('continua mostrando a comparação por documento sem as seções novas', async () => {
    const user = userEvent.setup();
    render(<BenchmarkPanel />);

    await user.type(screen.getByLabelText('suite.json'), 'suite.json');
    await user.click(screen.getByRole('button', { name: 'Rodar comparação' }));
    await waitFor(() => expect(bridgeMock.runBenchmarkCompare).toHaveBeenCalled());
    expect(await screen.findByText('cmp-legacy')).toBeTruthy();
    expect(screen.getByRole('region', { name: 'Responder ou se abster' })).toBeTruthy();
  });
});
