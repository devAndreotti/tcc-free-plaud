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
  /** Trecho citado numa resposta do chat: abre os chunks, rola até ele e o destaca. */
  highlightChunkId?: string | null;
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
interface MarkdownState {
  out: ReactNode[];
  para: string[];
  list: { ordered: boolean; items: { key: string; text: string }[] } | null;
  code: string[] | null;
}

/** Frontmatter do usuário vira uma lista de definição; devolve o resto das linhas. */
function readFrontmatter(lines: string[]): { node: ReactNode | null; rest: string[] } {
  const end = lines[0]?.trim() === '---' ? lines.indexOf('---', 1) : -1;
  if (end <= 0) return { node: null, rest: lines };
  const pairs = lines.slice(1, end).map((line) => line.split(/:(.*)/s)).filter((p) => p.length > 1 && p[0].trim());
  const node = pairs.length ? (
    <dl key="fm" className="reader__fm">
      {pairs.map(([k, v]) => (
        <div key={k}><dt>{k.trim()}</dt><dd>{v.trim().replace(/^\[(.*)\]$/, '$1') || '—'}</dd></div>
      ))}
    </dl>
  ) : null;
  return { node, rest: lines.slice(end + 1) };
}

function flushPara(s: MarkdownState) {
  if (s.para.length) s.out.push(<p key={`p${s.out.length}`}>{renderInline(s.para.join(' '))}</p>);
  s.para = [];
}

function flushList(s: MarkdownState) {
  if (!s.list) return;
  const items = s.list.items.map((item) => <li key={item.key}>{renderInline(item.text)}</li>);
  s.out.push(s.list.ordered ? <ol key={`l${s.out.length}`}>{items}</ol> : <ul key={`l${s.out.length}`}>{items}</ul>);
  s.list = null;
}

function flushBlocks(s: MarkdownState) {
  flushPara(s);
  flushList(s);
}

/** Dentro de um bloco de código, toda linha é literal até o ``` de fechamento. */
function readCodeLine(s: MarkdownState, line: string, raw: string): boolean {
  if (!s.code) return false;
  if (line.startsWith('```')) {
    s.out.push(<pre key={`c${s.out.length}`}><code>{s.code.join('\n')}</code></pre>);
    s.code = null;
  } else {
    s.code.push(raw);
  }
  return true;
}

function readHeading(s: MarkdownState, line: string, title: string): boolean {
  const heading = /^(#{1,4})\s(.*)$/.exec(line);
  if (!heading) return false;
  flushBlocks(s);
  const text = heading[2].trim();
  // O H1 igual ao título já está no cabeçalho do leitor.
  if (heading[1].length === 1 && s.out.length <= 1 && text === title) return true;
  const content = renderInline(text);
  s.out.push(heading[1].length <= 2 ? <h2 key={`h${s.out.length}`}>{content}</h2> : <h3 key={`h${s.out.length}`}>{content}</h3>);
  return true;
}

function readListItem(s: MarkdownState, line: string): boolean {
  const bullet = /^\s*[-*]\s(.*)$/.exec(line);
  const numbered = bullet ? null : /^\s*\d+[.)]\s(.*)$/.exec(line);
  const match = bullet ?? numbered;
  if (!match) return false;
  flushPara(s);
  const ordered = Boolean(numbered);
  if (s.list?.ordered !== ordered) {
    flushList(s);
    s.list = { ordered, items: [] };
  }
  s.list!.items.push({ key: `li${s.list!.items.length}`, text: match[1].trim() });
  return true;
}

function readQuote(s: MarkdownState, line: string): boolean {
  if (!line.startsWith('>')) return false;
  flushBlocks(s);
  s.out.push(<blockquote key={`q${s.out.length}`}>{renderInline(line.replace(/^>\s?/, ''))}</blockquote>);
  return true;
}

function renderMarkdown(source: string, title: string): ReactNode[] {
  const { node, rest } = readFrontmatter(source.replaceAll('\r\n', '\n').split('\n'));
  const s: MarkdownState = { out: node ? [node] : [], para: [], list: null, code: null };
  for (const raw of rest) {
    const line = raw.trimEnd();
    if (readCodeLine(s, line, raw)) continue;
    if (line.startsWith('```')) {
      flushBlocks(s);
      s.code = [];
    } else if (!readHeading(s, line, title) && !readListItem(s, line) && !readQuote(s, line)) {
      if (line.trim()) {
        flushList(s);
        s.para.push(line.trim());
      } else {
        flushBlocks(s);
      }
    }
  }
  if (s.code) s.out.push(<pre key={`c${s.out.length}`}><code>{s.code.join('\n')}</code></pre>);
  flushBlocks(s);
  return s.out;
}

/**
 * O backend guarda a nota como: frontmatter interno, "## Summary" (o começo do texto),
 * "## Normalized Text" (a nota inteira) e "## Raw Text" (a nota inteira de novo).
 * A leitura mostra só o texto normalizado; sem essa seção, o markdown sem o frontmatter interno.
 */
function readableMarkdown(source: string): string {
  const md = source.replaceAll('\r\n', '\n');
  const body = md.startsWith('---\n') ? md.slice(md.indexOf('\n---', 4) + 4) : md;
  const start = body.search(/^## Normalized Text\s*$/m);
  if (start < 0) return body;
  const text = body.slice(body.indexOf('\n', start) + 1);
  const end = text.search(/^## Raw Text\s*$/m);
  return end < 0 ? text : text.slice(0, end);
}

export const NoteDetailView = ({ detail, crumbs, isMutating, isLoadingDetail, onReindex, onDelete, highlightChunkId = null }: NoteDetailViewProps) => {
  const chunks = detail.chunks ?? [];
  // Trecho citado: a lista abre com os chunks visíveis; se a nota não tiver mais esse trecho, abre a leitura normal.
  const [showChunks, setShowChunks] = useState(() => chunks.some((c) => c.chunk_id === highlightChunkId));
  const [menu, setMenu] = useState<'closed' | 'menu' | 'confirm'>('closed');
  const [copied, setCopied] = useState(false);
  const actionsRef = useRef<HTMLDivElement>(null);
  const cancelRef = useRef<HTMLButtonElement>(null);
  const citedRef = useRef<HTMLLIElement>(null);

  const tokens = chunks.reduce((sum, c) => sum + (c.token_count ?? 0), 0);
  const created = formatDate(detail.created_at);
  const busy = isMutating || isLoadingDetail;

  // Rola até o trecho citado uma vez, ao abrir: a nota só monta depois de carregada.
  useEffect(() => {
    citedRef.current?.scrollIntoView({ block: 'center' });
  }, []);

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
          <b>{crumbs.at(-1) ?? detail.title}</b>
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
            {(detail.tags ?? []).filter((tag) => tag !== detail.source_type).map((tag) => (
              <span key={tag} className="reader__tag mono">#{tag}</span>
            ))}
          </div>

          {showChunks ? (
            <ol className="reader__chunks" aria-label="Chunks indexados">
              {chunks.map((chunk, i) => {
                const overlap = i > 0 ? chunks[i - 1].char_end - chunk.char_start : 0;
                const cited = chunk.chunk_id === highlightChunkId;
                return (
                  <li
                    key={chunk.chunk_id}
                    ref={cited ? citedRef : undefined}
                    className={`reader__chunk${cited ? ' reader__chunk--cited' : ''}`}
                    title={chunk.chunk_id}
                  >
                    <span className="reader__chunk-label mono">
                      {cited && <span className="pill pill--accent">trecho citado</span>}
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
            <div className="reader__body">{renderMarkdown(readableMarkdown(detail.structured_markdown ?? ''), detail.title)}</div>
          )}
        </article>
      </div>
    </>
  );
};
