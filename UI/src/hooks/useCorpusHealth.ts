import { useEffect, useState } from 'react';
import { bridge } from '../services/bridge';

export interface CorpusHealth {
  notes: number;
  chunks: number;
  status: 'ok' | 'warning' | 'error' | 'unknown';
  errorCount: number;
  warningCount: number;
}

/** Resumo do corpus e do Doctor para a sidebar. Recarrega quando `refreshKey` muda. */
export function useCorpusHealth(refreshKey: unknown): CorpusHealth | null {
  const [health, setHealth] = useState<CorpusHealth | null>(null);

  useEffect(() => {
    let cancelled = false;
    bridge
      .getBackendSettings()
      .then((settings) => {
        if (cancelled) return;
        setHealth({
          notes: settings.notes_count ?? 0,
          chunks: settings.sqlite_chunks_count ?? 0,
          status: settings.doctor?.status ?? 'unknown',
          errorCount: settings.doctor?.error_count ?? 0,
          warningCount: settings.doctor?.warning_count ?? 0,
        });
      })
      .catch(() => {
        if (!cancelled) setHealth(null);
      });
    return () => {
      cancelled = true;
    };
  }, [refreshKey]);

  return health;
}
