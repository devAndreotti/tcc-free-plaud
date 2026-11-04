/**
 * doctorReport.ts
 * O Diagnóstico leva segundos: a barra lateral e as Configurações dividem a mesma execução,
 * e quem abre a tela vê o último resultado na hora enquanto o novo chega.
 */
import { bridge, type BackendSettings, type DoctorReport } from '../services/bridge';

export interface DoctorStats {
  notes: number;
  sqlite: number;
  vectors: number;
}

export interface DoctorSnapshot {
  report: DoctorReport | null;
  running: boolean;
}

const EMPTY: DoctorSnapshot = { report: null, running: false };
let snapshot = EMPTY;
let lastStats: DoctorStats | null = null;
let pending: Promise<DoctorReport | null> | null = null;
const listeners = new Set<() => void>();

const publish = (patch: Partial<DoctorSnapshot>) => {
  snapshot = { ...snapshot, ...patch };
  listeners.forEach((listener) => listener());
};

export const subscribeDoctor = (listener: () => void): (() => void) => {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
};
export const getDoctorSnapshot = (): DoctorSnapshot => snapshot;
export const lastDoctorReport = (): DoctorReport | null => snapshot.report;
export const lastDoctorStats = (): DoctorStats | null => lastStats;

export const rememberDoctorStats = (settings: BackendSettings): void => {
  lastStats = {
    notes: settings.notes_count,
    sqlite: settings.sqlite_chunks_count,
    vectors: settings.vector_chunks_count,
  };
};

/** Roda o Diagnóstico; chamadas durante uma execução recebem essa mesma execução. */
export const refreshDoctor = (): Promise<DoctorReport | null> => {
  if (!pending) {
    publish({ running: true });
    pending = Promise.resolve(bridge.getDoctor?.())
      .then((report) => {
        if (report) publish({ report });
        return report ?? null;
      })
      .finally(() => {
        pending = null;
        publish({ running: false });
      });
  }
  return pending;
};

export const resetDoctorReport = (): void => {
  snapshot = EMPTY;
  lastStats = null;
  pending = null;
};
