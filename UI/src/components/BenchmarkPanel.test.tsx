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
        'A vetorial e a híbrida trazem a fonte certa entre os 5 primeiros trechos em 100% das perguntas, 50 pontos acima da lexical; a vetorial desempata pela latência (5 ms por consulta, com o mesmo MRR).'
      )
    ).toBeTruthy();
    // Melhor latência da coluna destacada.
    expect(screen.getByText('3 ms').className).toBe('bench__best');
    expect(screen.getByRole('img', { name: /Recall@3, @5 e @10/ })).toBeTruthy();
  });

  const summary = (strategy: string, recall: number, mrr: number, latency: number) => ({
    ...benchmarkResult.summaries.lexical,
    strategy,
    mrr,
    recall_at_3: recall,
    recall_at_5: recall,
    recall_at_10: recall,
    avg_query_latency_ms: latency,
  });

  it.each([
    {
      caso: 'empate de duas, decidido pelo MRR',
      summaries: { lexical: summary('lexical', 0.5, 0.4, 3), vector: summary('vector', 1, 0.8, 5), hybrid: summary('hybrid', 1, 0.9, 6) },
      frase: /^A híbrida e a vetorial .* 50 pontos acima da lexical; a híbrida desempata pelo MRR/,
    },
    {
      caso: 'vencedora mais lenta',
      summaries: { lexical: summary('lexical', 0.5, 0.5, 3), hybrid: summary('hybrid', 0.9, 0.9, 8) },
      frase: /^A híbrida traz .* 40 pontos acima da lexical, e custa 5 ms a mais por consulta\.$/,
    },
    {
      caso: 'vencedora mais rápida',
      summaries: { lexical: summary('lexical', 0.9, 0.9, 3), vector: summary('vector', 0.6, 0.6, 7) },
      frase: /^A lexical traz .* e ainda responde 4 ms mais rápido por consulta\.$/,
    },
    {
      caso: 'uma estratégia só',
      summaries: { hybrid: summary('hybrid', 0.75, 0.7, 4) },
      frase: /^A híbrida traz a fonte certa entre os 5 primeiros trechos em 75% das perguntas\.$/,
    },
  ])('resume a comparação em uma frase: $caso', async ({ summaries, frase }) => {
    const user = userEvent.setup();
    bridgeMock.runBenchmarkCompare.mockResolvedValueOnce({ ...benchmarkResult, summaries });
    render(<BenchmarkPanel />);

    await user.type(screen.getByLabelText('suite.json'), 'suite.json');
    await user.click(screen.getByRole('button', { name: 'Rodar comparação' }));

    expect(await screen.findByText(frase)).toBeTruthy();
  });

  it('abre no corpus inteiro, com intervalo de confiança e abstenção, e troca para por documento', async () => {
    const user = userEvent.setup();
    const corpusSummary = (strategy: string, mrr: number, abstainRecall: number) => ({
      ...benchmarkResult.summaries.lexical,
      strategy,
      case_count: 2,
      query_count: 4,
      mrr,
      ndcg_at_10: mrr,
      p50_query_latency_ms: 7,
      p95_query_latency_ms: 12,
      mrr_ci: [0.5, 1],
      abstention: { accuracy: 0.8, precision: 1, recall: abstainRecall, f1: 0.5, support: 6, answered_positive_rate: 0.75 },
    });
    bridgeMock.runBenchmarkCompare.mockResolvedValueOnce({
      ...benchmarkResult,
      corpus: {
        note_count: 2,
        positive_count: 4,
        negative_count: 2,
        retrieval_depth: 10,
        summaries: {
          lexical: corpusSummary('lexical', 0.75, 0),
          vector: corpusSummary('vector', 0.8, 0.5),
          hybrid: corpusSummary('hybrid', 0.9, 0.5),
        },
      },
    });
    render(<BenchmarkPanel />);

    await user.type(screen.getByLabelText('suite.json'), 'suite.json');
    await user.click(screen.getByRole('button', { name: 'Rodar comparação' }));

    expect(await screen.findByText('4 perguntas')).toBeTruthy();
    expect(screen.getAllByText('0,50–1,00')).toHaveLength(3);
    expect(
      screen.getByText(
        'Na híbrida, 1 de 2 perguntas sem resposta no corpus recebem uma resposta mesmo assim, e 25% das que têm resposta ficam sem ela.'
      )
    ).toBeTruthy();

    await user.click(screen.getByRole('button', { name: 'Por documento' }));
    expect(screen.getByText('2 perguntas')).toBeTruthy();
    expect(screen.queryByRole('region', { name: 'Responder ou se abster' })).toBeNull();
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
