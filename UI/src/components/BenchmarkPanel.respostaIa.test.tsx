import { cleanup, render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import BenchmarkPanel from './BenchmarkPanel';
import type { BenchmarkAnswerMetrics, BenchmarkCompareResult, BenchmarkStrategySummary } from '../services/bridge';
import { resetBenchmarkRun } from '../lib/benchmarkRun';

const bridgeMock = vi.hoisted(() => ({
  selectBenchmarkSuite: vi.fn(),
  runBenchmarkCompare: vi.fn(),
  getBackendSettings: vi.fn(),
}));

vi.mock('../services/bridge', () => ({ bridge: bridgeMock }));

const summary = (strategy: string, answer_metrics: BenchmarkAnswerMetrics | null): BenchmarkStrategySummary => ({
  strategy,
  case_count: 1,
  query_count: 73,
  mrr: 0.9,
  recall_at_3: 0.9,
  recall_at_5: 0.9,
  recall_at_10: 0.9,
  duration_ms: 100,
  avg_query_latency_ms: 10,
  answer_metrics,
});

// Números da rodada qchat_antes_onda3 do experimento 17.
const hybrid: BenchmarkAnswerMetrics = {
  answer_count: 38,
  accepted_count: 37,
  accepted_rate: 37 / 38,
  discard_reasons: { unsupported_anchor: 1, generated_no_answer_sentinel: 13 },
  question_p50_ms: 3127,
  question_p95_ms: 3903.8,
};
const lexical: BenchmarkAnswerMetrics = {
  answer_count: 39,
  accepted_count: 36,
  accepted_rate: 36 / 39,
  discard_reasons: { echoed_context_metadata: 1, generated_no_answer_sentinel: 13, unsupported_anchor: 2 },
  question_p50_ms: 3157,
  question_p95_ms: 3838.6,
};

const compare = (summaries: Record<string, BenchmarkStrategySummary>): BenchmarkCompareResult => ({
  ok: true,
  comparison_id: 'cmp-ia',
  suite_name: 'suite',
  summaries,
  corpus: { note_count: 10, positive_count: 39, negative_count: 34, retrieval_depth: 10, summaries },
  json_report_path: 'r.json',
  csv_report_path: 'r.csv',
  settings_snapshot: null,
});

const withAi = () => bridgeMock.getBackendSettings.mockResolvedValue({ answer_provider: 'ollama', answer_model: 'qchat:latest' });

describe('Benchmark: medir também a resposta da IA', () => {
  beforeEach(() => resetBenchmarkRun());
  beforeEach(() => vi.clearAllMocks());
  afterEach(() => cleanup());

  const run = async (user: ReturnType<typeof userEvent.setup>) => {
    await user.type(screen.getByLabelText('suite.json'), 'suite.json');
    await user.click(screen.getByRole('button', { name: 'Rodar comparação' }));
    await screen.findByText('cmp-ia', { exact: false });
  };

  it('só com Só trechos a opção não aparece e a comparação roda só com a busca', async () => {
    const user = userEvent.setup();
    bridgeMock.getBackendSettings.mockResolvedValue({ answer_provider: 'extractive', answer_model: 'qwen2.5:3b' });
    bridgeMock.runBenchmarkCompare.mockResolvedValue(compare({ hybrid: summary('hybrid', null) }));
    render(<BenchmarkPanel />);
    await waitFor(() => expect(bridgeMock.getBackendSettings).toHaveBeenCalledWith({ doctor: false }));

    await run(user);

    expect(screen.queryByRole('checkbox', { name: /Medir também/ })).toBeNull();
    expect(bridgeMock.runBenchmarkCompare).toHaveBeenCalledWith('suite.json');
    expect(screen.queryByRole('region', { name: 'Resposta da IA' })).toBeNull();
  });

  it('com a opção ligada pede a medição e mostra aceitas, tempos e motivos do maior para o menor', async () => {
    const user = userEvent.setup();
    withAi();
    bridgeMock.runBenchmarkCompare.mockResolvedValue(compare({ hybrid: summary('hybrid', hybrid), lexical: summary('lexical', lexical) }));
    render(<BenchmarkPanel />);

    await user.click(await screen.findByRole('checkbox', { name: /Medir também a resposta da IA/ }));
    await run(user);

    expect(bridgeMock.runBenchmarkCompare).toHaveBeenCalledWith('suite.json', { answer: true });
    const section = screen.getByRole('region', { name: 'Resposta da IA' });
    expect(section.textContent).toContain('qchat:latest');
    expect(section.textContent).toContain('37 de 38');
    expect(section.textContent).toContain('3,1 s');
    const rows = within(section).getAllByRole('listitem').map((row) => row.textContent ?? '');
    expect(rows[0]).toContain('A IA disse que os trechos não respondem');
    expect(rows[0]).toContain('generated_no_answer_sentinel');
    expect(rows[0]).toContain('Inclui as perguntas sem resposta');
    expect(rows[1]).toContain('A IA citou algo que não está nos trechos');

    await user.click(within(section).getByRole('radio', { name: 'Lexical' }));
    expect(section.textContent).toContain('36 de 39');
    expect(section.textContent).toContain('echoed_context_metadata');
  });

  it('com a opção desligada, a comparação não paga o tempo da IA', async () => {
    const user = userEvent.setup();
    withAi();
    bridgeMock.runBenchmarkCompare.mockResolvedValue(compare({ hybrid: summary('hybrid', null) }));
    render(<BenchmarkPanel />);
    await screen.findByRole('checkbox', { name: /Medir também/ });

    await run(user);

    expect(bridgeMock.runBenchmarkCompare).toHaveBeenCalledWith('suite.json');
  });

  it('sem descarte nenhum, a seção diz isso em vez de ficar vazia', async () => {
    const user = userEvent.setup();
    withAi();
    bridgeMock.runBenchmarkCompare.mockResolvedValue(compare({ hybrid: summary('hybrid', { ...hybrid, accepted_count: 38, discard_reasons: {} }) }));
    render(<BenchmarkPanel />);
    await screen.findByRole('checkbox', { name: /Medir também/ });

    await run(user);

    expect(screen.getByText('Nenhuma resposta da IA foi descartada nesta estratégia.')).toBeTruthy();
  });
});
