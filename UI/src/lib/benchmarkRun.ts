/**
 * benchmarkRun.ts
 * A comparação e o resultado ficam fora da tela: trocar de aba não perde nada, e voltar mostra
 * o progresso de onde está. O resultado anterior sai assim que uma nova comparação começa.
 */
import { bridge, type BenchmarkCompareResult, type BenchmarkJobState } from '../services/bridge';

export interface BenchmarkRunState {
  suitePath: string;
  isRunning: boolean;
  job: BenchmarkJobState | null;
  result: BenchmarkCompareResult | null;
  status: string;
  ranModel: string | null;
}

const INITIAL: BenchmarkRunState = {
  suitePath: '',
  isRunning: false,
  job: null,
  result: null,
  status: '',
  ranModel: null,
};

const POLL_MS = 400;
let state = INITIAL;
let generation = 0;
const listeners = new Set<() => void>();

const update = (patch: Partial<BenchmarkRunState>) => {
  state = { ...state, ...patch };
  listeners.forEach((listener) => listener());
};

export const subscribeBenchmarkRun = (listener: () => void): (() => void) => {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
};
export const getBenchmarkRun = (): BenchmarkRunState => state;
export const setBenchmarkSuitePath = (suitePath: string): void => update({ suitePath });
export const setBenchmarkStatus = (status: string): void => update({ status });

export const resetBenchmarkRun = (): void => {
  generation += 1;
  state = INITIAL;
};

const errorText = (error: unknown): string =>
  error instanceof Error && error.message ? error.message : 'Falha ao rodar benchmark.';

const followJob = async (run: number): Promise<BenchmarkJobState | null> => {
  for (;;) {
    await new Promise((resolve) => setTimeout(resolve, POLL_MS));
    if (run !== generation) return null;
    const job = await bridge.getBenchmarkJob();
    if (run !== generation) return null;
    if (!job || job.status !== 'running') return job;
    update({ job });
  }
};

/** Roda a comparação: em segundo plano quando o backend sabe, numa chamada só quando não. */
export const startBenchmarkRun = async (
  suitePath: string,
  { answer, model }: { answer: boolean; model: string | null },
): Promise<void> => {
  if (state.isRunning) return;
  generation += 1;
  const run = generation;
  update({ suitePath, isRunning: true, job: null, result: null, status: '', ranModel: null });
  try {
    const started = await bridge.startBenchmarkCompare?.(suitePath, { answer });
    let result: BenchmarkCompareResult | null;
    if (started) {
      update({ job: started });
      const finished = await followJob(run);
      if (run !== generation) return;
      if (finished?.status === 'cancelled') {
        update({ isRunning: false, job: null, status: 'Comparação cancelada.' });
        return;
      }
      if (!finished?.result) throw new Error(finished?.error ?? 'Falha ao rodar benchmark.');
      result = finished.result;
    } else {
      result = answer
        ? await bridge.runBenchmarkCompare(suitePath, { answer: true })
        : await bridge.runBenchmarkCompare(suitePath);
    }
    if (run !== generation) return;
    update({
      isRunning: false,
      job: null,
      result,
      ranModel: answer ? model : null,
      status: `Comparação ${result.comparison_id} concluída.`,
    });
  } catch (error) {
    if (run === generation) update({ isRunning: false, job: null, result: null, status: errorText(error) });
  }
};

export const cancelBenchmarkRun = async (): Promise<void> => {
  try {
    await bridge.cancelBenchmarkJob();
  } catch (error) {
    update({ status: errorText(error) });
  }
};

/** Abre uma rodada gravada, com o mesmo esqueleto de uma comparação nova. */
export const openBenchmarkRun = async (comparisonId: string): Promise<void> => {
  if (state.isRunning) return;
  generation += 1;
  const run = generation;
  update({ isRunning: true, job: null, result: null, status: '', ranModel: null });
  try {
    const result = await bridge.loadBenchmarkRun(comparisonId);
    if (run !== generation) return;
    update({
      isRunning: false,
      result,
      ranModel: result.answer_provider && result.answer_provider !== 'extractive' ? result.answer_model ?? null : null,
      status: `Rodada ${comparisonId} aberta.`,
    });
  } catch (error) {
    if (run === generation) update({ isRunning: false, status: errorText(error) });
  }
};
