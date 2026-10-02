import { useEffect, useRef, useState, type ReactNode } from 'react';
import { type NoteDetail } from '../services/bridge';
import { ChevronRightIcon, CopyIcon, MoreIcon, RefreshIcon, TrashIcon } from './Icons';
import { formatDate, typeLabel } from '../lib/notes';

interface NoteDetailViewProps {
  detail: NoteDetail;
  /** Caminho relativo ao vault, já quebrado em pastas (o último item é o arquivo). */
  crumbs: string[];
  isMutating: boolean;
  isLoadingDetail: boolean;
  onReindex: () => void;
  onDelete: () => void;
}

/** `código` e **negrito** dentro de uma linha; o React escapa o resto. */
function renderInline(text: string): ReactNode[] {
  // A chave é a posição do trecho na linha: o texto é estático, não se reordena.
  let offset = 0;
  return text.split(/(`[^`]+`|\*\*[^*]+\*\*)/g).map((part) => {
    const key = `i${offset}`;
    offset += part.length;
    if (part.startsWith('`') && part.endsWith('`') && part.length > 2) return <code key={key}>{part.slice(1, -1)}</code>;
    if (part.startsWith('**') && part.endsWith('**') && part.length > 4) return <strong key={key}>{part.slice(2, -2)}</strong>;
    return part;
  });
}

/**
 * Markdown de leitura: frontmatter, títulos, listas, citações, blocos de código e parágrafos.
 * ponytail: subconjunto do Markdown suficiente para notas do vault; tabelas e links viram texto.
 */
function renderMarkdown(source: string, title: string): ReactNode[] {
  const out: ReactNode[] = [];
  let lines = source.replace(/\r\n/g, '\n').split('\n');

  if (lines[0]?.trim() === '---') {
    const end = lines.indexOf('---', 1);
    if (end > 0) {
      const pairs = lines.slice(1, end).map((line) => line.split(/:(.*)/s)).filter((p) => p.length > 1 && p[0].trim());
      if (pairs.length) {
        out.push(
          <dl key="fm" className="reader__fm">
            {pairs.map(([k, v]) => (
              <div key={k}><dt>{k.trim()}</dt><dd>{v.trim() || '—'}</dd></div>
            ))}
          </dl>
        );
      }
      lines = lines.slice(end + 1);
    }
  }

  let para: string[] = [];
  let list: { ordered: boolean; items: { key: string; text: string }[] } | null = null;
  let code: string[] | null = null;
  const flushPara = () => {
    if (para.length) out.push(<p key={`p${out.length}`}>{renderInline(para.join(' '))}</p>);
    para = [];
  };
  const flushList = () => {
    if (!list) return;
    const items = list.items.map((item) => <li key={item.key}>{renderInline(item.text)}</li>);
    out.push(list.ordered ? <ol key={`l${out.length}`}>{items}</ol> : <ul key={`l${out.length}`}>{items}</ul>);
    list = null;
  };

  for (const raw of lines) {
    const line = raw.trimEnd();
    if (code) {
      if (line.startsWith('```')) {
        out.push(<pre key={`c${out.length}`}><code>{code.join('\n')}</code></pre>);
        code = null;
      } else {
        code.push(raw);
      }
      continue;
    }
    if (line.startsWith('```')) { flushPara(); flushList(); code = []; continue; }
    const heading = /^(#{1,4})\s(.*)$/.exec(line);
    if (heading) {
      flushPara(); flushList();
      const text = heading[2].trim();
      if (heading[1].length === 1 && out.length <= 1 && text === title) continue;
      out.push(heading[1].length <= 2
        ? <h2 key={`h${out.length}`}>{renderInline(text)}</h2>
        : <h3 key={`h${out.length}`}>{renderInline(text)}</h3>);
      continue;
    }
    const bullet = /^\s*[-*]\s+(.*)$/.exec(line);
    const numbered = /^\s*\d+[.)]\s+(.*)$/.exec(line);
    if (bullet || numbered) {
      flushPara();
      const ordered = Boolean(numbered);
      if (!list || list.ordered !== ordered) { flushList(); list = { ordered, items: [] }; }
      list.items.push({ key: `li${list.items.length}`, text: (bullet ?? numbered)![1] });
      continue;
    }
    if (line.startsWith('>')) {
      flushPara(); flushList();
      out.push(<blockquote key={`q${out.length}`}>{renderInline(line.replace(/^>\s?/, ''))}</blockquote>);
      continue;
    }
    if (!line.trim()) { flushPara(); flushList(); continue; }
    flushList();
    para.push(line.trim());
  }
  if (code) out.push(<pre key={`c${out.length}`}><code>{(code as string[]).join('\n')}</code></pre>);
  flushPara();
  flushList();
  return out;
}

export const NoteDetailView = ({ detail, crumbs, isMutating, isLoadingDetail, onReindex, onDelete }: NoteDetailViewProps) => {
  const [showChunks, setShowChunks] = useState(false);
  const [menu, setMenu] = useState<'closed' | 'menu' | 'confirm'>('closed');
  const [copied, setCopied] = useState(false);
  const actionsRef = useRef<HTMLDivElement>(null);
  const cancelRef = useRef<HTMLButtonElement>(null);

  const chunks = detail.chunks ?? [];
  const tokens = chunks.reduce((sum, c) => sum + (c.token_count ?? 0), 0);
  const created = formatDate(detail.created_at);
  const busy = isMutating || isLoadingDetail;

  useEffect(() => {
    if (menu === 'closed') return undefined;
    if (menu === 'confirm') cancelRef.current?.focus();
    const onDown = (event: MouseEvent) => {
      if (!actionsRef.current?.contains(event.target as Node)) setMenu('closed');
    };
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setMenu('closed');
    };
    document.addEventListener('mousedown', onDown);
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('mousedown', onDown);
      document.removeEventListener('keydown', onKey);
    };
  }, [menu]);

  const copyPath = async () => {
    setMenu('closed');
    try {
      await navigator.clipboard.writeText(detail.source_path ?? '');
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1600);
    } catch {
      setCopied(false);
    }
  };

  return (
    <>
      <div className="nd__bar">
        <nav className="nd__crumbs" aria-label="Local no vault">
          {crumbs.slice(0, -1).map((part, depth) => ({ part, path: crumbs.slice(0, depth + 1).join('/') })).map(({ part, path }) => (
            <span key={path} className="nd__crumb">
              {part}
              <ChevronRightIcon size={12} />
            </span>
          ))}
          <b>{crumbs[crumbs.length - 1] ?? detail.title}</b>
          {copied && <span className="nd__copied">caminho copiado</span>}
        </nav>

        <div className="nd__actions" ref={actionsRef}>
          <label className="switch">
            <input
              type="checkbox"
              checked={showChunks}
              onChange={(event) => setShowChunks(event.target.checked)}
            />
            <span className="switch__track" aria-hidden="true" />
            <span>Mostrar chunks</span>
          </label>
          <span className="nd__vr" aria-hidden="true" />
          <button type="button" className="btn btn--sm" onClick={onReindex} disabled={busy}>
            <RefreshIcon size={14} />
            Reindexar
          </button>
          <button
            type="button"
            className="btn-icon"
            aria-label="Mais ações"
            aria-haspopup="menu"
            aria-expanded={menu !== 'closed'}
            onClick={() => setMenu((prev) => (prev === 'closed' ? 'menu' : 'closed'))}
          >
            <MoreIcon size={17} />
          </button>

          {menu === 'menu' && (
            <div className="popover nd__menu" role="menu">
              <button type="button" role="menuitem" className="popover__item" onClick={copyPath}>
                <CopyIcon size={15} />
                Copiar caminho
              </button>
              <hr />
              <button
                type="button"
                role="menuitem"
                className="popover__item popover__item--danger"
                onClick={() => setMenu('confirm')}
                disabled={busy}
              >
                <TrashIcon size={15} />
                Apagar do corpus…
              </button>
            </div>
          )}

          {menu === 'confirm' && (
            <div className="popover nd__confirm" role="alertdialog" aria-labelledby="nd-confirm-title" aria-describedby="nd-confirm-desc">
              <h4 id="nd-confirm-title">Apagar do corpus?</h4>
              <p id="nd-confirm-desc">
                Remove <b>{detail.title}</b> e {chunks.length === 1 ? 'seu chunk' : `seus ${chunks.length} chunks`} do SQLite e do
                Chroma. O arquivo no vault não é alterado.
              </p>
              <div className="nd__confirm-actions">
                <button ref={cancelRef} type="button" className="btn btn--sm btn--ghost" onClick={() => setMenu('closed')}>
                  Cancelar
                </button>
                <button
                  type="button"
                  className="btn btn--sm btn--danger"
                  onClick={() => {
                    setMenu('closed');
                    onDelete();
                  }}
                >
                  Apagar do corpus
                </button>
              </div>
            </div>
          )}
        </div>
      </div>

      <div className="nd__scroll">
        <article className={`reader${showChunks ? ' reader--chunks' : ''}`}>
          <h1 className="reader__title">{detail.title}</h1>
          <div className="reader__meta">
            <span>{typeLabel(detail.source_type)}</span>
            <span className="reader__sep">·</span>
            <span>{chunks.length} {chunks.length === 1 ? 'chunk' : 'chunks'}</span>
            {tokens > 0 && (
              <>
                <span className="reader__sep">·</span>
                <span className="mono">{tokens.toLocaleString('pt-BR')} tokens</span>
              </>
            )}
            {created && (
              <>
                <span className="reader__sep">·</span>
                <span>indexada em {created}</span>
              </>
            )}
            {(detail.tags ?? []).map((tag) => (
              <span key={tag} className="reader__tag mono">#{tag}</span>
            ))}
          </div>

          {showChunks ? (
            <ol className="reader__chunks" aria-label="Chunks indexados">
              {chunks.map((chunk, i) => {
                const overlap = i > 0 ? chunks[i - 1].char_end - chunk.char_start : 0;
                return (
                  <li key={chunk.chunk_id} className="reader__chunk" title={chunk.chunk_id}>
                    <span className="reader__chunk-label mono">
                      <b>#{chunk.chunk_index} · {chunk.token_count} tok</b>
                      {chunk.char_start}–{chunk.char_end}
                      {overlap > 0 && <><br />↥ {overlap} sobrepostos</>}
                    </span>
                    <p>{chunk.snippet}</p>
                  </li>
                );
              })}
            </ol>
          ) : (
            <div className="reader__body">{renderMarkdown(detail.structured_markdown ?? '', detail.title)}</div>
          )}
        </article>
      </div>
    </>
  );
};
