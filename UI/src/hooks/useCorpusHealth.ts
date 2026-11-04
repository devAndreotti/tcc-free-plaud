import { useEffect, useState } from 'react';
import { CORPUS_CHANGED, CORPUS_PROGRESS_EVENT } from '../lib/corpusEvents';
import { bridge } from '../services/bridge';
import { lastDoctorReport, refreshDoctor, rememberDoctorStats } from '../lib/doctorReport';

export interface CorpusHealth {
  notes: number;
  chunks: number;
  status: 'ok' | 'warning' | 'error' | 'unknown';
  errorCount: number;
  warningCount: number;
}

/** Avisa quem mostra números do corpus (a sidebar) que algo foi indexado, reindexado ou apagado. */
export function notifyCorpusChanged(): void {
  window.dispatchEvent(new Event(CORPUS_CHANGED));
}

/** Resumo do corpus e do Doctor para a sidebar. Recarrega quando `refreshKey` muda ou o corpus avisa. */
export function useCorpusHealth(refreshKey: unknown): CorpusHealth | null {
  const [health, setHealth] = useState<CorpusHealth | null>(null);
  const [changes, setChanges] = useState(0);

  useEffect(() => {
    const onChange = () => setChanges((n) => n + 1);
    window.addEventListener(CORPUS_CHANGED, onChange);
    return () => window.removeEventListener(CORPUS_CHANGED, onChange);
  }, []);

  // Durante a indexação, só as contagens: o Doctor pesa e competiria com o job; o estado dele fica como está.
  useEffect(() => {
    let cancelled = false;
    const onProgress = () => {
      bridge
        .getBackendSettings({ doctor: false })
        .then((settings) => {
          if (cancelled) return;
          setHealth((prev) => prev && {
            ...prev,
            notes: settings.notes_count ?? prev.notes,
            chunks: settings.sqlite_chunks_count ?? prev.chunks,
          });
        })
        .catch(() => {
          // Contagem ao vivo é opcional: o fim do job recarrega tudo.
        });
    };
    window.addEventListener(CORPUS_PROGRESS_EVENT, onProgress);
    return () => {
      cancelled = true;
      window.removeEventListener(CORPUS_PROGRESS_EVENT, onProgress);
    };
  }, []);

  useEffect(() => {
    let cancelled = false;
    // As contagens chegam primeiro; o estado do Diagnóstico leva segundos e vem à parte.
    bridge
      .getBackendSettings({ doctor: false })
      .then((settings) => {
        if (cancelled) return;
        rememberDoctorStats(settings);
        const report = settings.doctor ?? lastDoctorReport();
        setHealth((prev) => ({
          notes: settings.notes_count ?? 0,
          chunks: settings.sqlite_chunks_count ?? 0,
          status: report?.status ?? prev?.status ?? 'unknown',
          errorCount: report?.error_count ?? prev?.errorCount ?? 0,
          warningCount: report?.warning_count ?? prev?.warningCount ?? 0,
        }));
      })
      .catch(() => {
        if (!cancelled) setHealth(null);
      });
    refreshDoctor()
      .then((report) => {
        if (cancelled || !report) return;
        setHealth((prev) => prev && {
          ...prev,
          status: report.status,
          errorCount: report.error_count,
          warningCount: report.warning_count,
        });
      })
      .catch(() => {
        // Sem Diagnóstico, a barra lateral fica só com as contagens.
      });
    return () => {
      cancelled = true;
    };
  }, [refreshKey, changes]);

  return health;
}
