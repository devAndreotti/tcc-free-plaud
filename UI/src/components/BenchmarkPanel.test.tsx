import { cleanup, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import BenchmarkPanel from './BenchmarkPanel';

const bridgeMock = vi.hoisted(() => ({
  selectBenchmarkSuite: vi.fn(),
  runBenchmarkCompare: vi.fn(),
}));

vi.mock('../services/bridge', () => ({
  bridge: bridgeMock,
}));

const benchmarkResult = {
  ok: true,
  comparison_id: 'cmp-ui',
  suite_name: 'suite-ui',
  summaries: {
    lexical: {
      strategy: 'lexical',
      case_count: 1,
      query_count: 2,
      mrr: 0.5,
      recall_at_3: 0.5,
      recall_at_5: 0.5,
      recall_at_10: 0.5,
      duration_ms: 20,
      avg_query_latency_ms: 3,
    },
    vector: {
      strategy: 'vector',
      case_count: 1,
      query_count: 2,
      mrr: 1,
      recall_at_3: 1,
      recall_at_5: 1,
      recall_at_10: 1,
      duration_ms: 40,
      avg_query_latency_ms: 5,
    },
    hybrid: {
      strategy: 'hybrid',
      case_count: 1,
      query_count: 2,
      mrr: 1,
      recall_at_3: 1,
      recall_at_5: 1,
      recall_at_10: 1,
      duration_ms: 44,
      avg_query_latency_ms: 6,
    },
  },
  json_report_path: 'data/results/cmp-ui.json',
  csv_report_path: 'data/results/cmp-ui.csv',
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

describe('BenchmarkPanel', () => {
  afterEach(() => {
    cleanup();
  });

  beforeEach(() => {
    bridgeMock.selectBenchmarkSuite.mockReset();
    bridgeMock.runBenchmarkCompare.mockReset();
    bridgeMock.selectBenchmarkSuite.mockResolvedValue('data/datasets/suite-ui.json');
    bridgeMock.runBenchmarkCompare.mockResolvedValue(benchmarkResult);
  });

  it('seleciona suite e mostra metricas, exports e snapshot', async () => {
    const user = userEvent.setup();
    render(<BenchmarkPanel />);

    await user.click(screen.getByRole('button', { name: 'Selecionar suite' }));
    expect((screen.getByLabelText('suite.json') as HTMLInputElement).value).toBe('data/datasets/suite-ui.json');

    await user.click(screen.getByRole('button', { name: 'Rodar comparação' }));

    await waitFor(() => {
      expect(bridgeMock.runBenchmarkCompare).toHaveBeenCalledWith('data/datasets/suite-ui.json');
    });
    expect(await screen.findByText('cmp-ui')).toBeTruthy();
    expect(screen.getAllByText('Híbrida').length).toBeGreaterThan(0);
    expect(screen.getByText('data/results/cmp-ui.json')).toBeTruthy();
    expect(screen.getByText('fake-hash')).toBeTruthy();
    expect(screen.getByText('Comparação cmp-ui concluída.')).toBeTruthy();
    // Empate em Recall@5 e MRR entre vetorial e híbrida: vence a de menor latência.
    expect(
      screen.getByText(
        'A vetorial traz a fonte certa entre os 5 primeiros trechos em 100% das perguntas, 50 pontos acima da lexical, e custa 2 ms a mais por consulta.'
      )
    ).toBeTruthy();
    // Melhor latência da coluna destacada.
    expect(screen.getByText('3 ms').className).toBe('bench__best');
    expect(screen.getByRole('img', { name: /Recall@3, @5 e @10/ })).toBeTruthy();
  });

  it('mostra erro e estado vazio quando compare falha', async () => {
    const user = userEvent.setup();
    bridgeMock.runBenchmarkCompare.mockRejectedValueOnce(new Error('Suite invalida'));
    render(<BenchmarkPanel />);

    await user.type(screen.getByLabelText('suite.json'), 'suite.json');
    await user.click(screen.getByRole('button', { name: 'Rodar comparação' }));

    expect(await screen.findByText('Suite invalida')).toBeTruthy();
    expect(screen.getByText('Nenhum benchmark executado nesta sessão.')).toBeTruthy();
  });
});
