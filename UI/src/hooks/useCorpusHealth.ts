import { useEffect, useState } from 'react';
import { bridge } from '../services/bridge';

export interface CorpusHealth {
  notes: number;
  chunks: number;
  status: 'ok' | 'warning' | 'error' | 'unknown';
  errorCount: number;
  warningCount: number;
}

const CORPUS_CHANGED = 'free-plaud:corpus-changed';

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
  }, [refreshKey, changes]);

  return health;
}
