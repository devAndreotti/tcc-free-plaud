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

let lastReport: DoctorReport | null = null;
let lastStats: DoctorStats | null = null;
let pending: Promise<DoctorReport | null> | null = null;

export const lastDoctorReport = (): DoctorReport | null => lastReport;
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
  pending ??= Promise.resolve(bridge.getDoctor?.())
    .then((report) => {
      if (report) lastReport = report;
      return report ?? null;
    })
    .finally(() => {
      pending = null;
    });
  return pending;
};

export const resetDoctorReport = (): void => {
  lastReport = null;
  lastStats = null;
  pending = null;
};
