import { cleanup, render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { MOCK_BENCHMARK_RESULT_FULL, type BenchmarkCompareResult, type BenchmarkCoverageGroup } from '../services/bridge';
import BenchmarkPanel from './BenchmarkPanel';

// Dados ILUSTRATIVOS: só para os testes (ver comentário em bridge.ts).
const bridgeMock = vi.hoisted(() => ({
  selectBenchmarkSuite: vi.fn(),
  runBenchmarkCompare: vi.fn(),
}));

vi.mock('../services/bridge', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../services/bridge')>()),
  bridge: bridgeMock,
}));

type Field = 'reranked' | 'baseline_ci' | 'coverage' | 'faithfulness';

/** Resultado completo, sem os campos novos que a lista indicar. */
function without(...fields: Field[]): BenchmarkCompareResult {
  const out: BenchmarkCompareResult = { ...MOCK_BENCHMARK_RESULT_FULL };
  for (const field of ['reranked', 'baseline_ci', 'coverage', 'faithfulness'] as const) {
    if (!fields.includes(field)) continue;
    delete out[field];
  }
  return out;
}

const ABLATION = /Ablação do ranking/;
const COVERAGE = /Cobertura por tipo de pergunta/;
const FAITH = /^Faithfulness$/;

async function renderWith(result: BenchmarkCompareResult) {
  bridgeMock.runBenchmarkCompare.mockResolvedValueOnce(result);
  const user = userEvent.setup();
  const view = render(<BenchmarkPanel />);
  await user.type(screen.getByLabelText('suite.json'), 'suite.json');
  await user.click(screen.getByRole('button', { name: 'Rodar comparação' }));
  await screen.findByText(result.comparison_id);
  return view;
}

const region = (name: RegExp | string) => screen.queryByRole('region', { name });

describe('BenchmarkPanel: seções opcionais (ablação, cobertura, faithfulness)', () => {
  beforeEach(() => {
    bridgeMock.selectBenchmarkSuite.mockReset();
    bridgeMock.runBenchmarkCompare.mockReset();
  });

  afterEach(() => {
    cleanup();
  });

  describe('cada campo isolado', () => {
    it('só reranked: mostra a ablação e nada das outras duas seções', async () => {
      await renderWith(without('baseline_ci', 'coverage', 'faithfulness'));
      expect(region(ABLATION)).not.toBeNull();
      expect(region(COVERAGE)).toBeNull();
      expect(region(FAITH)).toBeNull();
    });

    it('só baseline_ci, sem reranked: não cria ablação', async () => {
      await renderWith(without('reranked', 'coverage', 'faithfulness'));
      expect(region(ABLATION)).toBeNull();
      expect(region(COVERAGE)).toBeNull();
      expect(region(FAITH)).toBeNull();
    });

    it('só coverage: mostra cobertura e nada das outras', async () => {
      await renderWith(without('reranked', 'baseline_ci', 'faithfulness'));
      expect(region(COVERAGE)).not.toBeNull();
      expect(region(ABLATION)).toBeNull();
      expect(region(FAITH)).toBeNull();
    });

    it('só faithfulness: mostra faithfulness e nada das outras', async () => {
      await renderWith(without('reranked', 'baseline_ci', 'coverage'));
      expect(region(FAITH)).not.toBeNull();
      expect(region(ABLATION)).toBeNull();
      expect(region(COVERAGE)).toBeNull();
    });
  });

  it('com todos os campos: mostra as três seções na ordem do desenho', async () => {
    await renderWith(MOCK_BENCHMARK_RESULT_FULL);
    const ablation = region(ABLATION);
    const abstention = region('Responder ou se abster');
    const coverage = region(COVERAGE);
    const faith = region(FAITH);
    const reports = region('Relatórios');
    for (const el of [ablation, abstention, coverage, faith, reports]) expect(el).not.toBeNull();

    const order = [ablation, abstention, coverage, faith, reports] as HTMLElement[];
    for (let i = 1; i < order.length; i += 1) {
      expect(order[i - 1].compareDocumentPosition(order[i]) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    }
  });

  describe('ablação', () => {
    it('mostra MRR sem e com o reranker, com IC, e o nome do modelo', async () => {
      await renderWith(MOCK_BENCHMARK_RESULT_FULL);
      const ablation = within(region(ABLATION)!);
      expect(ablation.getByText('Ablação do ranking · MRR')).toBeTruthy();
      expect(
        ablation.getByText('RRF sozinho contra RRF + cross-encoder. Traço fino: intervalo de confiança de 95%.')
      ).toBeTruthy();
      expect(ablation.getByText('Sem reranker')).toBeTruthy();
      expect(ablation.getByText('+ BAAI/bge-reranker-v2-m3')).toBeTruthy();
      expect(ablation.getByRole('img', {
        name: 'Lexical: MRR sem reranker 0,914, IC 95% 0,86–0,96; com BAAI/bge-reranker-v2-m3 0,931, IC 95% 0,88–0,97',
      })).toBeTruthy();
      expect(ablation.getByText('IC 0,86–0,96')).toBeTruthy();
    });

    it('desenha o traço de IC só onde há intervalo', async () => {
      const result = without('baseline_ci');
      result.reranked = {
        ...MOCK_BENCHMARK_RESULT_FULL.reranked!,
        ci: { lexical: { mrr_lower: 0.88, mrr_upper: 0.97 } },
      };
      const { container } = await renderWith(result);
      // Só a linha léxica tem IC, e só na barra com reranker.
      expect(container.querySelectorAll('.bench__whisker')).toHaveLength(1);
      expect(container.querySelectorAll('.bench__whisker--rr')).toHaveLength(1);
    });
  });

  describe('IC ausente', () => {
    it('sem ci e sem baseline_ci: mostra os valores, sem traço e sem texto de IC na ablação', async () => {
      const result = without('baseline_ci');
      result.reranked = { model: 'modelo-x', summaries: MOCK_BENCHMARK_RESULT_FULL.reranked!.summaries };
      const { container } = await renderWith(result);
      const ablation = within(region(ABLATION)!);
      expect(ablation.getByRole('img', { name: 'Lexical: MRR sem reranker 0,914; com modelo-x 0,931' })).toBeTruthy();
      expect(container.querySelectorAll('.bench__whisker')).toHaveLength(0);
      expect(ablation.queryByText(/^IC /)).toBeNull();
    });

    it('intervalo invertido (inferior maior que superior) é ignorado', async () => {
      const result = without('baseline_ci');
      result.reranked = {
        ...MOCK_BENCHMARK_RESULT_FULL.reranked!,
        ci: { lexical: { mrr_lower: 0.97, mrr_upper: 0.88 } },
      };
      const { container } = await renderWith(result);
      expect(container.querySelectorAll('.bench__whisker')).toHaveLength(0);
    });
  });

  describe('NaN e grupos vazios na cobertura', () => {
    const coverageWith = (groups: BenchmarkCoverageGroup[], k = 5) => ({ k, groups });

    it('grupo com n = 0 ou n = NaN mostra "—" e "sem perguntas", sem barra', async () => {
      const result = without('reranked', 'baseline_ci', 'faithfulness');
      result.coverage = coverageWith([
        { id: 'vazio', label: 'Grupo vazio', n: 0, single_chunk: 0, across_chunks: 0 },
        { id: 'nan', label: 'Grupo NaN', n: Number.NaN, single_chunk: Number.NaN, across_chunks: 2 },
        { id: 'ok', label: 'Grupo medido', n: 4, single_chunk: 1, across_chunks: 3 },
      ]);
      const { container } = await renderWith(result);
      const coverage = within(region(COVERAGE)!);
      expect(coverage.getByRole('img', { name: 'Grupo vazio: sem perguntas neste grupo' })).toBeTruthy();
      expect(coverage.getByRole('img', { name: 'Grupo NaN: sem perguntas neste grupo' })).toBeTruthy();
      expect(coverage.getByRole('img', { name: 'Grupo medido: num trecho 0,250, entre trechos 0,750, 4 perguntas' })).toBeTruthy();
      expect(coverage.getAllByText('—').length).toBeGreaterThanOrEqual(4);
      expect(coverage.getAllByText('0 perguntas')).toHaveLength(2);
      // Só o grupo medido tem duas barras preenchidas.
      expect(container.querySelectorAll('.bench__cov-group .bench__fill')).toHaveLength(2);
    });

    it('taxa maior que 1 (contagem inconsistente) não vira barra', async () => {
      const result = without('reranked', 'baseline_ci', 'faithfulness');
      result.coverage = coverageWith([{ id: 'x', label: 'Inconsistente', n: 4, single_chunk: 5, across_chunks: 4 }]);
      const { container } = await renderWith(result);
      expect(within(region(COVERAGE)!).getByRole('img', { name: /Inconsistente: num trecho não medido, entre trechos 1,000/ })).toBeTruthy();
      expect(container.querySelectorAll('.bench__cov-group .bench__fill')).toHaveLength(1);
    });

    it('singular em 1 pergunta', async () => {
      const result = without('reranked', 'baseline_ci', 'faithfulness');
      result.coverage = coverageWith([{ id: 'um', label: 'Uma', n: 1, single_chunk: 1, across_chunks: 1 }]);
      await renderWith(result);
      expect(within(region(COVERAGE)!).getByText('1 pergunta')).toBeTruthy();
    });

    it('sem grupos, a seção não aparece', async () => {
      const result = without('reranked', 'baseline_ci', 'faithfulness');
      result.coverage = coverageWith([]);
      await renderWith(result);
      expect(region(COVERAGE)).toBeNull();
    });

    it('k inválido cai no texto genérico, sem número', async () => {
      const result = without('reranked', 'baseline_ci', 'faithfulness');
      result.coverage = coverageWith([{ id: 'a', label: 'A', n: 2, single_chunk: 1, across_chunks: 2 }], Number.NaN);
      await renderWith(result);
      expect(within(region(COVERAGE)!).getByText(/Termos esperados presentes nos primeiros trechos/)).toBeTruthy();
    });

    it('usa k no texto explicativo', async () => {
      await renderWith(MOCK_BENCHMARK_RESULT_FULL);
      expect(
        within(region(COVERAGE)!).getByText('Termos esperados presentes nos 5 primeiros trechos. A régua antiga exige tudo num trecho só.')
      ).toBeTruthy();
    });
  });

  describe('faithfulness', () => {
    it('mostra valor grande, IC, afirmações, ilegíveis, juiz e a nota de profundidade', async () => {
      await renderWith(MOCK_BENCHMARK_RESULT_FULL);
      const faith = within(region(FAITH)!);
      expect(faith.getByText('0,874')).toBeTruthy();
      expect(faith.getByText('IC 95% [0,81 – 0,93]')).toBeTruthy();
      expect(faith.getByText('Afirmações avaliadas')).toBeTruthy();
      expect(faith.getByText('112')).toBeTruthy();
      expect(faith.getByText('Veredito ilegível')).toBeTruthy();
      expect(faith.getByText('3')).toBeTruthy();
      expect(faith.getByText('Juiz')).toBeTruthy();
      expect(faith.getByText('modelo-juiz-ilustrativo')).toBeTruthy();
      expect(faith.getByText(/Mede suporte no trecho citado, não verdade no mundo\. Um chunk citado fora dos 10 primeiros/)).toBeTruthy();
      expect(faith.getByRole('img', { name: 'Faithfulness 0,874, IC 95% [0,81 – 0,93]' })).toBeTruthy();
    });

    it('sem corpus, a nota de profundidade some e a faithfulness continua', async () => {
      const result = without('reranked', 'baseline_ci', 'coverage');
      delete result.corpus;
      await renderWith(result);
      const faith = within(region(FAITH)!);
      expect(faith.getByText('0,874')).toBeTruthy();
      expect(faith.getByText('Mede suporte no trecho citado, não verdade no mundo.')).toBeTruthy();
    });

    it('score, IC e contagens NaN viram "—" e "intervalo indisponível", sem quebrar', async () => {
      const result = without('reranked', 'baseline_ci', 'coverage');
      result.faithfulness = {
        score: Number.NaN,
        ci_lower: Number.NaN,
        ci_upper: Number.NaN,
        claims: Number.NaN,
        unparsed: 0,
        judge_model: '  ',
      };
      const { container } = await renderWith(result);
      const faith = within(region(FAITH)!);
      expect(faith.getByText('intervalo indisponível')).toBeTruthy();
      expect(faith.getAllByText('—').length).toBeGreaterThanOrEqual(3);
      expect(faith.getByText('0')).toBeTruthy();
      expect(container.querySelector('.bench__faith .bench__fill')).toBeNull();
    });
  });

  it('a regressão de seções existentes continua com todos os campos novos', async () => {
    await renderWith(MOCK_BENCHMARK_RESULT_FULL);
    expect(screen.getByRole('img', { name: /Recall@3, @5 e @10/ })).toBeTruthy();
    expect(screen.getByRole('region', { name: 'Responder ou se abster' })).toBeTruthy();
    expect(screen.getByText('Relatórios desta comparação')).toBeTruthy();
  });
});
