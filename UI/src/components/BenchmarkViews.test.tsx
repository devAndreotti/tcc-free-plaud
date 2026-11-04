import { cleanup, render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';
import type { BenchmarkCompareResult, BenchmarkJobState, BenchmarkQueryRow, BenchmarkRunRow } from '../services/bridge';
import { tccTable } from '../lib/benchmarkView';
import BenchmarkHistory from './BenchmarkHistory';
import BenchmarkProgress from './BenchmarkProgress';
import BenchmarkInsights from './BenchmarkInsights';

afterEach(cleanup);

const row = (patch: Partial<BenchmarkQueryRow>): BenchmarkQueryRow => ({
  sample_id: patch.question ?? 'q',
  question: 'Pergunta?',
  retrieved: [{ rank: 1, note_id: 'nota-a' }],
  ...patch,
});

const run = (patch: Partial<BenchmarkRunRow>): BenchmarkRunRow => ({
  comparison_id: 'cmp-a',
  suite_name: 'calibrada',
  started_at: '2026-11-04T01:02:03Z',
  duration_ms: 23000,
  answer_provider: 'extractive',
  answer_model: null,
  positive_count: 39,
  negative_count: 34,
  mrr: 0.944,
  recall_at_3: 1,
  answered_positive_rate: 0.97,
  abstention_recall: 0.62,
  accuracy: 0.81,
  ...patch,
});

const ROWS = [
  row({ sample_id: 'h1', question: 'Respondida certa?', answered: true, relevant_rank: 1, answer: 'A resposta completa.', expected_note_id: 'nota-a', expected_ref: 'Seção 2' }),
  row({ sample_id: 'h2', question: 'Recusada errada?', answered: false, relevant_rank: 2, expected_note_id: 'nota-b' }),
  row({ sample_id: 'h3', question: 'Sem resposta recusada?', answered: false, category: 'negativa' }),
  row({ sample_id: 'h4', question: 'Sem resposta inventada?', answered: true, category: 'negativa' }),
];
const RESULT = { comparison_id: 'cmp-1', corpus: { queries: { hybrid: ROWS } }, negative_subtypes: { h3: 'fora-do-dominio', h4: 'quase-acerto' } } as unknown as BenchmarkCompareResult;
const acesas = () => screen.getAllByRole('button', { pressed: false }).concat(screen.getAllByRole('button', { pressed: true })).filter((b) => b.className.includes('bench-cell') && !b.className.includes('is-dim')).map((b) => b.getAttribute('aria-label')).sort();

describe('BenchmarkInsights', () => {
  it('abre na primeira pergunta errada, com o esperado e os trechos achados', () => {
    render(<BenchmarkInsights result={RESULT} />);
    const detalhe = within(screen.getByRole('region', { name: 'Pergunta selecionada' }));
    expect(detalhe.getByText('Recusada errada?')).toBeTruthy();
    expect(detalhe.getByText('Recusou, errado')).toBeTruthy();
    expect(detalhe.getByText('nota-a')).toBeTruthy();
  });

  it('clicar numa pergunta mostra a resposta dela', async () => {
    const user = userEvent.setup();
    render(<BenchmarkInsights result={RESULT} />);
    await user.click(screen.getByRole('button', { name: 'Respondida certa?' }));
    expect(screen.getByText('A resposta completa.')).toBeTruthy();
    expect(screen.getByText(/nota-a · Seção 2/)).toBeTruthy();
  });

  it('decisão certa é responder o que tem resposta e recusar o que não tem', async () => {
    const user = userEvent.setup();
    render(<BenchmarkInsights result={RESULT} />);
    await user.click(screen.getByRole('button', { name: 'Certas' }));
    expect(acesas()).toEqual(['Respondida certa?', 'Sem resposta recusada?'].sort());
    await user.click(screen.getByRole('button', { name: 'Erradas' }));
    expect(acesas()).toEqual(['Recusada errada?', 'Sem resposta inventada?'].sort());
  });

  it('por que errou separa pelos tipos, marca o mais fraco e acende as perguntas no mapa', async () => {
    const user = userEvent.setup();
    render(<BenchmarkInsights result={RESULT} />);
    const quase = screen.getByRole('button', { name: /Quase certas/ });
    expect(quase.textContent).toContain('1 de 1');
    expect(quase.textContent).toContain('mais fraco');
    expect(screen.getByRole('button', { name: /Fora do assunto/ }).textContent).toContain('0 de 1');
    await user.click(quase);
    expect(acesas()).toEqual(['Sem resposta inventada?']);
    await user.click(quase);
    expect(acesas()).toHaveLength(4);
  });

  it('suite sem tipos avisa e junta as perguntas sem resposta', () => {
    render(<BenchmarkInsights result={{ ...RESULT, negative_subtypes: {} }} />);
    expect(screen.getByRole('button', { name: /Não tinha e respondeu/ }).textContent).toContain('1 de 2');
    expect(screen.getByText(/não marca o tipo/)).toBeTruthy();
  });

  it('agrupa por nota com o placar de cada uma', async () => {
    const user = userEvent.setup();
    render(<BenchmarkInsights result={RESULT} />);
    await user.click(screen.getByRole('button', { name: 'Por nota' }));
    expect(screen.getByText('nota a')).toBeTruthy();
    expect(screen.getByText('nota b')).toBeTruthy();
    expect(screen.getByText('Sem resposta nas notas')).toBeTruthy();
    expect(screen.getByText('1/2')).toBeTruthy();
  });
});

describe('tccTable', () => {
  it('junta sem IA e com IA de cada suite e avisa do lote cego', () => {
    const tabela = tccTable([
      run({ comparison_id: 'a', suite_name: 'lote-cego-suite', mrr: 0.811, mrr_ci: [0.703, 0.905], recall_at_3: 0.946, accuracy: 0.51 }),
      run({ comparison_id: 'b', suite_name: 'lote-cego-suite', answer_provider: 'ollama', accuracy: 0.71 }),
      run({ comparison_id: 'c', suite_name: 'manual', mrr: 0.944, recall_at_3: 1, accuracy: 0.81 }),
    ]);
    expect(tabela).toContain('| lote-cego-suite | 0,811 (0,703 a 0,905) | 94,6% | 51% | 71% |');
    expect(tabela).toContain('| manual | 0,944 | 100,0% | 81% | — |');
    expect(tabela).toContain('ainda não foi revisado');
  });
});

describe('BenchmarkHistory', () => {
  const RUNS = [run({}), run({ comparison_id: 'cmp-b', suite_name: 'cega', mrr: 0.811, accuracy: 0.51 })];

  it('sem rodadas gravadas não aparece', () => {
    const { container } = render(<BenchmarkHistory runs={[]} onOpen={() => {}} />);
    expect(container.firstChild).toBeNull();
  });

  it('abre uma rodada e não reabre a que já está na tela', async () => {
    const user = userEvent.setup();
    const onOpen = vi.fn();
    render(<BenchmarkHistory runs={RUNS} currentId="cmp-a" onOpen={onOpen} />);
    const abrir = screen.getAllByRole('button', { name: /^Abrir/ });
    expect((abrir[0] as HTMLButtonElement).disabled).toBe(true);
    await user.click(abrir[1]);
    expect(onOpen).toHaveBeenCalledWith('cmp-b');
  });

  it('marcando duas rodadas, mostra a diferença entre elas', async () => {
    const user = userEvent.setup();
    render(<BenchmarkHistory runs={RUNS} onOpen={() => {}} />);
    expect(screen.queryByRole('group', { name: 'Comparação entre rodadas' })).toBeNull();
    const marcas = screen.getAllByRole('checkbox');
    await user.click(marcas[0]);
    await user.click(marcas[1]);
    const tabela = within(screen.getByRole('group', { name: 'Comparação entre rodadas' }));
    expect(tabela.getByText('-0,133')).toBeTruthy();
    expect(tabela.getByText('-30 p.p.')).toBeTruthy();
  });
});

const job = (patch: Partial<BenchmarkJobState>): BenchmarkJobState => ({
  status: 'running',
  suite_name: 'lote-cego-suite',
  answer: false,
  phase: 'corpus',
  strategy: 'hybrid',
  question: 'Pergunta atual?',
  done: 50,
  total: 200,
  elapsed_ms: 10000,
  error: null,
  result: null,
  recent: [],
  ...patch,
});

describe('BenchmarkProgress', () => {
  it('mostra o percentual, a pergunta atual e a previsão, e permite cancelar', async () => {
    const user = userEvent.setup();
    const onCancel = vi.fn();
    render(<BenchmarkProgress job={job({})} onCancel={onCancel} />);
    expect(screen.getByRole('progressbar').getAttribute('aria-valuenow')).toBe('25');
    expect(screen.getByText('Pergunta atual?')).toBeTruthy();
    expect(screen.getByText(/50 de 200 · 10 s · faltam cerca de 30 s/)).toBeTruthy();
    await user.click(screen.getByRole('button', { name: 'Cancelar' }));
    expect(onCancel).toHaveBeenCalledTimes(1);
  });

  it('no começo ainda não arrisca previsão', () => {
    render(<BenchmarkProgress job={job({ done: 2, total: 258 })} onCancel={() => {}} />);
    expect(screen.queryByText(/faltam/)).toBeNull();
  });
});
