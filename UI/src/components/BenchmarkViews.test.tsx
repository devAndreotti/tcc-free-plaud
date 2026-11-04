import { cleanup, render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';
import type { BenchmarkJobState, BenchmarkQueryRow, BenchmarkRunRow } from '../services/bridge';
import BenchmarkHistory from './BenchmarkHistory';
import BenchmarkProgress from './BenchmarkProgress';
import BenchmarkQuestions from './BenchmarkQuestions';

afterEach(cleanup);

const row = (patch: Partial<BenchmarkQueryRow>): BenchmarkQueryRow => ({
  sample_id: patch.question ?? 'q',
  question: 'Pergunta?',
  retrieved: [{ rank: 1, note_id: 'nota-a' }],
  ...patch,
});

const QUERIES = {
  lexical: [row({ sample_id: 'l1', question: 'Só na léxica?', answered: true })],
  hybrid: [
    row({ sample_id: 'h1', question: 'Respondida certa?', answered: true, relevant_rank: 1, answer: 'A resposta completa.', expected_note_id: 'nota-a', expected_ref: 'Seção 2' }),
    row({ sample_id: 'h2', question: 'Recusada errada?', answered: false, relevant_rank: 2 }),
    row({ sample_id: 'h3', question: 'Sem resposta recusada?', answered: false, category: 'negativa' }),
    row({ sample_id: 'h4', question: 'Sem resposta inventada?', answered: true, category: 'negativa' }),
  ],
};

const textos = () => screen.getAllByRole('listitem').map((item) => within(item).getByText(/\?$/).textContent);

describe('BenchmarkQuestions', () => {
  it('abre na híbrida e mostra a resposta e o esperado de cada pergunta', () => {
    render(<BenchmarkQuestions queries={QUERIES} />);
    expect(textos()).toHaveLength(4);
    expect(screen.getByText('A resposta completa.')).toBeTruthy();
    expect(screen.getByText(/nota-a · Seção 2/)).toBeTruthy();
    expect(screen.getByText('nota certa em 2º')).toBeTruthy();
  });

  it('decisão certa é responder o que tem resposta e recusar o que não tem', async () => {
    const user = userEvent.setup();
    render(<BenchmarkQuestions queries={QUERIES} />);
    await user.click(screen.getByRole('button', { name: /Decisão certa/ }));
    expect(textos()).toEqual(['Respondida certa?', 'Sem resposta recusada?']);
    await user.click(screen.getByRole('button', { name: /Decisão errada/ }));
    expect(textos()).toEqual(['Recusada errada?', 'Sem resposta inventada?']);
    await user.click(screen.getByRole('button', { name: /Não têm resposta/ }));
    expect(textos()).toEqual(['Sem resposta recusada?', 'Sem resposta inventada?']);
  });

  it('troca de estratégia', async () => {
    const user = userEvent.setup();
    render(<BenchmarkQuestions queries={QUERIES} />);
    await user.click(within(screen.getByRole('group', { name: 'Estratégia' })).getAllByRole('button')[0]);
    expect(textos()).toEqual(['Só na léxica?']);
  });
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
