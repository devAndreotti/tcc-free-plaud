import { useEffect, useState } from 'react';
import { bridge, type IgnoredPath } from '../services/bridge';
import { notifyCorpusChanged } from '../hooks/useCorpusHealth';

const fileName = (path: string) => path.split(/[\\/]/).filter(Boolean).pop() ?? path;

/** Arquivos que a indexação desta vault pula, com "Voltar a indexar" (desfaz o "Ignorar" das falhas). */
const IgnoredFiles = ({ version }: { version: number }) => {
  const [items, setItems] = useState<IgnoredPath[]>([]);
  const [reload, setReload] = useState(0);
  const [busy, setBusy] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    bridge.listIgnoredPaths().then(
      (list) => {
        if (active) setItems(list);
      },
      () => {
        if (active) setItems([]);
      }
    );
    return () => {
      active = false;
    };
  }, [version, reload]);

  if (items.length === 0) return null;

  const restore = async (path: string) => {
    setBusy(path);
    try {
      await bridge.unignoreIndexPaths([path]);
      notifyCorpusChanged();
      setReload((value) => value + 1);
    } finally {
      setBusy(null);
    }
  };

  return (
    <details className="card queue__ignored">
      <summary>
        Ignorados na indexação <span className="card__count">{items.length}</span>
        <small>Arquivos que você mandou pular. Voltar a indexar põe o arquivo na fila de novo.</small>
      </summary>
      <ul aria-label="Arquivos ignorados">
        {items.map((item) => (
          <li key={item.path} className="issue-file" title={item.path}>
            <span className="issue-file__text">
              <span className="issue-file__name">{fileName(item.path)}</span>
              <small className="issue-file__folder mono">{item.path}</small>
            </span>
            <button
              type="button"
              className="btn btn--sm"
              aria-label={`Voltar a indexar ${fileName(item.path)}`}
              disabled={busy === item.path}
              onClick={() => void restore(item.path)}
            >
              Voltar a indexar
            </button>
          </li>
        ))}
      </ul>
    </details>
  );
};

export default IgnoredFiles;
