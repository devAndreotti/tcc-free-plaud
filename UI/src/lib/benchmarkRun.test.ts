import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { BenchmarkCompareResult, BenchmarkJobState } from '../services/bridge';

const bridgeMock = vi.hoisted(() => ({
  startBenchmarkCompare: vi.fn(),
  getBenchmarkJob: vi.fn(),
  cancelBenchmarkJob: vi.fn(),
  runBenchmarkCompare: vi.fn(),
  loadBenchmarkRun: vi.fn(),
}));
vi.mock('../services/bridge', () => ({ bridge: bridgeMock }));

import {
  cancelBenchmarkRun,
  getBenchmarkRun,
  openBenchmarkRun,
  resetBenchmarkRun,
  startBenchmarkRun,
} from './benchmarkRun';

const result = (id: string) => ({ comparison_id: id }) as unknown as BenchmarkCompareResult;
const job = (patch: Partial<BenchmarkJobState>): BenchmarkJobState => ({
  status: 'running',
  suite_name: 's',
  answer: false,
  phase: 'corpus',
  strategy: 'hybrid',
  question: 'Q?',
  done: 1,
  total: 10,
  elapsed_ms: 100,
  error: null,
  result: null,
  recent: [],
  ...patch,
});

const avanca = () => vi.advanceTimersByTimeAsync(450);

describe('benchmarkRun', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    resetBenchmarkRun();
    Object.values(bridgeMock).forEach((fn) => fn.mockReset());
  });
  afterEach(() => vi.useRealTimers());

  it('tira o resultado anterior da tela assim que uma nova comparação começa', async () => {
    bridgeMock.startBenchmarkCompare.mockResolvedValue(null);
    bridgeMock.runBenchmarkCompare.mockResolvedValueOnce(result('cmp-1'));
    await startBenchmarkRun('a.json', { answer: false, model: null });
    expect(getBenchmarkRun().result?.comparison_id).toBe('cmp-1');

    let libera: (value: BenchmarkCompareResult) => void = () => {};
    bridgeMock.runBenchmarkCompare.mockReturnValueOnce(new Promise((resolve) => { libera = resolve; }));
    const rodada = startBenchmarkRun('b.json', { answer: false, model: null });
    expect(getBenchmarkRun().result).toBeNull();
    expect(getBenchmarkRun().isRunning).toBe(true);

    libera(result('cmp-2'));
    await rodada;
    expect(getBenchmarkRun().result?.comparison_id).toBe('cmp-2');
    expect(getBenchmarkRun().isRunning).toBe(false);
  });

  it('acompanha o progresso em segundo plano até o resultado', async () => {
    bridgeMock.startBenchmarkCompare.mockResolvedValue(job({ done: 0 }));
    bridgeMock.getBenchmarkJob
      .mockResolvedValueOnce(job({ done: 5, question: 'Segunda?' }))
      .mockResolvedValueOnce(job({ status: 'done', done: 10, result: result('cmp-3') }));

    const rodada = startBenchmarkRun('a.json', { answer: true, model: 'qchat' });
    await avanca();
    expect(getBenchmarkRun().job?.question).toBe('Segunda?');
    await avanca();
    await rodada;

    expect(bridgeMock.runBenchmarkCompare).not.toHaveBeenCalled();
    expect(getBenchmarkRun().result?.comparison_id).toBe('cmp-3');
    expect(getBenchmarkRun().ranModel).toBe('qchat');
    expect(getBenchmarkRun().job).toBeNull();
  });

  it('cancelar não deixa resultado nem erro', async () => {
    bridgeMock.startBenchmarkCompare.mockResolvedValue(job({}));
    bridgeMock.getBenchmarkJob.mockResolvedValue(job({ status: 'cancelled' }));
    bridgeMock.cancelBenchmarkJob.mockResolvedValue(job({}));

    const rodada = startBenchmarkRun('a.json', { answer: false, model: null });
    await vi.advanceTimersByTimeAsync(0);
    await cancelBenchmarkRun();
    await avanca();
    await rodada;

    expect(bridgeMock.cancelBenchmarkJob).toHaveBeenCalledTimes(1);
    expect(getBenchmarkRun().status).toBe('Comparação cancelada.');
    expect(getBenchmarkRun().result).toBeNull();
    expect(getBenchmarkRun().isRunning).toBe(false);
  });

  it('falha do backend aparece como mensagem', async () => {
    bridgeMock.startBenchmarkCompare.mockResolvedValue(job({}));
    bridgeMock.getBenchmarkJob.mockResolvedValue(job({ status: 'error', error: 'suite ruim' }));
    const rodada = startBenchmarkRun('a.json', { answer: false, model: null });
    await avanca();
    await rodada;
    expect(getBenchmarkRun().status).toBe('suite ruim');
    expect(getBenchmarkRun().isRunning).toBe(false);
  });

  it('não inicia outra comparação com uma em andamento', async () => {
    bridgeMock.startBenchmarkCompare.mockResolvedValue(job({}));
    bridgeMock.getBenchmarkJob.mockResolvedValue(job({ status: 'running' }));
    void startBenchmarkRun('a.json', { answer: false, model: null });
    await vi.advanceTimersByTimeAsync(0);
    await startBenchmarkRun('b.json', { answer: false, model: null });
    expect(bridgeMock.startBenchmarkCompare).toHaveBeenCalledTimes(1);
    expect(getBenchmarkRun().suitePath).toBe('a.json');
  });

  it('abre uma rodada gravada sem rodar nada', async () => {
    bridgeMock.loadBenchmarkRun.mockResolvedValue(result('cmp-antiga'));
    await openBenchmarkRun('cmp-antiga');
    expect(getBenchmarkRun().result?.comparison_id).toBe('cmp-antiga');
    expect(bridgeMock.runBenchmarkCompare).not.toHaveBeenCalled();
  });
});
