import { useState } from 'react';
import { bridge, type IndexJobFileError } from '../services/bridge';
import { notifyCorpusChanged } from '../hooks/useCorpusHealth';
import { describeIndexIssue, groupIndexIssues, splitIssuePath, technicalDetail } from '../lib/indexErrors';
import type { SettingsTab } from './SettingsModal';
import { AlertTriangleIcon, FileIcon, XCircleIcon } from './Icons';

interface JobFailuresProps {
  errors: IndexJobFileError[];
  /** Pasta indexada pelo job: os arquivos aparecem relativos a ela. */
  rootPath: string;
  onOpenSettings?: (tab?: SettingsTab) => void;
  /** Avisa a Fila que a lista de ignorados mudou. */
  onIgnoredChanged?: () => void;
}

const plural = (n: number, one: string, many: string) => `${n} ${n === 1 ? one : many}`;

/** Falhas do job agrupadas pelo motivo, em linguagem de usuário, com o que dá para fazer em cada uma. */
const JobFailures = ({ errors, rootPath, onOpenSettings, onIgnoredChanged }: JobFailuresProps) => {
  // Resolvidas nesta tela (ignoradas ou indexadas) e falhas que mudaram depois de "Tentar de novo".
  const [resolved, setResolved] = useState<Record<string, true>>({});
  const [updated, setUpdated] = useState<Record<string, IndexJobFileError>>({});
  const [busy, setBusy] = useState<Record<string, boolean>>({});
  const [notice, setNotice] = useState('');

  const pending = errors.filter((error) => !resolved[error.source_path]).map((error) => updated[error.source_path] ?? error);
  if (pending.length === 0 && Object.keys(resolved).length === 0) return null;

  const run = async (paths: string[], action: () => Promise<void>) => {
    setBusy((prev) => ({ ...prev, ...Object.fromEntries(paths.map((path) => [path, true])) }));
    try {
      await action();
    } catch (err) {
      setNotice(err instanceof Error ? err.message : 'A ação falhou.');
    } finally {
      setBusy((prev) => ({ ...prev, ...Object.fromEntries(paths.map((path) => [path, false])) }));
    }
  };

  const ignore = (paths: string[]) =>
    run(paths, async () => {
      const result = await bridge.ignoreIndexPaths(paths);
      if (!result.ok) {
        setNotice(result.message ?? 'Não foi possível ignorar.');
        return;
      }
      setResolved((prev) => ({ ...prev, ...Object.fromEntries(paths.map((path) => [path, true as const])) }));
      setNotice(`${plural(paths.length, 'arquivo ignorado', 'arquivos ignorados')} na indexação. Dá para voltar atrás em "Ignorados".`);
      onIgnoredChanged?.();
    });

  const retry = (paths: string[]) =>
    run(paths, async () => {
      const { results } = await bridge.retryIndexPaths(paths);
      const fixed = results.filter((result) => result.status !== 'failed').map((result) => result.source_path);
      const stillFailing = results.filter((result) => result.status === 'failed');
      setResolved((prev) => ({ ...prev, ...Object.fromEntries(fixed.map((path) => [path, true as const])) }));
      setUpdated((prev) => ({
        ...prev,
        ...Object.fromEntries(
          stillFailing.map((result) => [
            result.source_path,
            { source_path: result.source_path, error_code: result.error_code, message: result.message ?? 'Falha ao indexar.' },
          ])
        ),
      }));
      setNotice(
        stillFailing.length === 0
          ? `${plural(fixed.length, 'arquivo indexado', 'arquivos indexados')}.`
          : `${plural(stillFailing.length, 'arquivo continua', 'arquivos continuam')} com problema.`
      );
      if (fixed.length) notifyCorpusChanged();
    });

  const open = async (path: string, reveal: boolean) => {
    const result = await bridge.openIndexPath(path, reveal);
    if (!result.ok) setNotice(result.message ?? 'Não foi possível abrir.');
  };

  return (
    <section className="job__errors" aria-label="Arquivos com problema">
      <h2>
        Arquivos com problema <span className="card__count">{pending.length}</span>
      </h2>
      {notice && (
        <p className="issues__notice" role="status">
          {notice}
        </p>
      )}
      {pending.length === 0 && <p className="issues__done">Tudo resolvido neste job.</p>}
      {groupIndexIssues(pending).map(({ info, items }) => (
        <div key={info.kind} className={`issue-group issue-group--${info.tone}`}>
          <div className="issue-group__head">
            <span className="issue-group__icon" aria-hidden="true">
              {info.tone === 'error' ? <XCircleIcon size={16} /> : <AlertTriangleIcon size={16} />}
            </span>
            <div className="issue-group__text">
              <h3>
                {items.length === 1 ? info.title : info.plural} <span className="card__count">{items.length}</span>
              </h3>
              <p>{info.description}</p>
            </div>
            {items.length > 1 && info.actions.includes('ignore') && (
              <button
                type="button"
                className="btn btn--sm"
                onClick={() => void ignore(items.map((item) => item.source_path))}
                disabled={items.some((item) => busy[item.source_path])}
              >
                Ignorar todos
              </button>
            )}
          </div>
          <ul className="issue-group__files">
            {items.map((item) => {
              const { name, folder } = splitIssuePath(item.source_path, rootPath);
              const detail = technicalDetail(item);
              const actions = describeIndexIssue(item.error_code).actions;
              const isBusy = Boolean(busy[item.source_path]);
              return (
                <li key={item.source_path} className="issue-file" title={item.source_path}>
                  <FileIcon size={15} />
                  <span className="issue-file__text">
                    <span className="issue-file__name">{name}</span>
                    {folder && <small className="issue-file__folder">{folder}</small>}
                    {detail && <small className="issue-file__detail mono">{detail}</small>}
                  </span>
                  <span className="issue-file__actions">
                    {actions.includes('voice-settings') && onOpenSettings && (
                      <button type="button" className="btn btn--sm btn--ghost" onClick={() => onOpenSettings('voz')}>
                        Abrir Voz
                      </button>
                    )}
                    {actions.includes('open') && (
                      <button
                        type="button"
                        className="btn btn--sm btn--ghost"
                        aria-label={`Abrir ${name}`}
                        onClick={() => void open(item.source_path, false)}
                      >
                        Abrir
                      </button>
                    )}
                    {actions.includes('reveal') && (
                      <button
                        type="button"
                        className="btn btn--sm btn--ghost"
                        aria-label={`Mostrar ${name} na pasta`}
                        onClick={() => void open(item.source_path, true)}
                      >
                        Mostrar na pasta
                      </button>
                    )}
                    {actions.includes('retry') && (
                      <button
                        type="button"
                        className="btn btn--sm"
                        aria-label={`Tentar indexar ${name} de novo`}
                        disabled={isBusy}
                        onClick={() => void retry([item.source_path])}
                      >
                        {isBusy ? 'Tentando…' : 'Tentar de novo'}
                      </button>
                    )}
                    {actions.includes('ignore') && (
                      <button
                        type="button"
                        className="btn btn--sm"
                        aria-label={`Ignorar ${name} na indexação`}
                        disabled={isBusy}
                        onClick={() => void ignore([item.source_path])}
                      >
                        Ignorar
                      </button>
                    )}
                  </span>
                </li>
              );
            })}
          </ul>
        </div>
      ))}
    </section>
  );
};

export default JobFailures;
