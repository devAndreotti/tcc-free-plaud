import { useEffect, useRef, useState, type ReactNode } from 'react';
import { type NoteDetail } from '../services/bridge';
import { ChevronRightIcon, CopyIcon, MoreIcon, RefreshIcon, TrashIcon } from './Icons';
import { NoteChunks } from './NoteChunks';
import { NoteTitle } from './NoteTitle';
import { Segmented } from './ui/Controls';
import { formatDate, typeLabel } from '../lib/notes';

interface NoteDetailViewProps {
  detail: NoteDetail;
  /** Caminho relativo ao vault, já quebrado em pastas (o último item é o arquivo). */
  crumbs: string[];
  isMutating: boolean;
  isLoadingDetail: boolean;
  isReindexing?: boolean;
  onReindex: () => void;
  onDelete: () => void;
  /** Trecho citado numa resposta do chat: abre os chunks, rola até ele e o destaca. */
  highlightChunkId?: string | null;
}

/** `código`, **negrito** e [links](https://…) dentro de uma linha; o React escapa o resto. */
function renderInline(text: string): ReactNode[] {
  // A chave é a posição do trecho na linha: o texto é estático, não se reordena.
  let offset = 0;
  return text.split(/(`[^`]+`|\*\*[^*]+\*\*|\[[^\]]+\]\([^)\s]+\))/g).map((part) => {
    const key = `i${offset}`;
    offset += part.length;
    if (part.startsWith('`') && part.endsWith('`') && part.length > 2) return <code key={key}>{part.slice(1, -1)}</code>;
    if (part.startsWith('**') && part.endsWith('**') && part.length > 4) return <strong key={key}>{part.slice(2, -2)}</strong>;
    const link = /^\[([^\]]+)\]\(([^)\s]+)\)$/.exec(part);
    if (link) {
      // Só http(s) vira link, e abre no navegador: o conteúdo da nota não navega dentro do app.
      return /^https?:\/\//i.test(link[2]) ? <a key={key} href={link[2]} target="_blank" rel="noreferrer">{link[1]}</a> : link[1];
    }
    return part;
  });
}

/**
 * Markdown de leitura: frontmatter, títulos, listas, tabelas, citações, blocos de código e parágrafos.
 * ponytail: subconjunto do Markdown suficiente para notas do vault; o resto vira texto.
 */
interface MarkdownState {
  out: ReactNode[];
  para: string[];
  list: { ordered: boolean; items: { key: string; text: string }[] } | null;
  code: string[] | null;
  table: string[];
}

const TABLE_RULE = /^\s*\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)*\|?\s*$/;

const tableCells = (row: string) =>
  row
    .trim()
    .replace(/^\||\|$/g, '')
    .split(/(?<!\\)\|/)
    .map((cell) => cell.trim().replaceAll('\\|', '|'));

/** Linhas com | seguidas: tabela se a segunda for a régua; senão, texto comum. */
function flushTable(s: MarkdownState) {
  const [head, rule, ...body] = s.table;
  if (head === undefined) return;
  if (rule === undefined || !TABLE_RULE.test(rule)) {
    s.para.push(...s.table);
    s.table = [];
    flushPara(s);
    return;
  }
  s.table = [];
  // Chave por posição: a tabela é estática, não se reordena.
  const cells = (row: string, Cell: 'th' | 'td') =>
    tableCells(row).map((cell, i) => {
      const key = `${Cell}${i}`;
      return <Cell key={key}>{renderInline(cell)}</Cell>;
    });
  s.out.push(
    <div key={`t${s.out.length}`} className="reader__table">
      <table>
        <thead><tr>{cells(head, 'th')}</tr></thead>
        <tbody>
          {body.map((row, i) => {
            const key = `r${i}`;
            return <tr key={key}>{cells(row, 'td')}</tr>;
          })}
        </tbody>
      </table>
    </div>
  );
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
  flushTable(s);
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
  // O título no começo da nota, em # ou ##, já está no cabeçalho do leitor.
  if (heading[1].length <= 2 && s.out.length <= 1 && text === title) return true;
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
  const s: MarkdownState = { out: node ? [node] : [], para: [], list: null, code: null, table: [] };
  for (const raw of rest) {
    const line = raw.trimEnd();
    if (readCodeLine(s, line, raw)) continue;
    if (line.trimStart().startsWith('|')) {
      flushPara(s);
      flushList(s);
      s.table.push(line);
      continue;
    }
    flushTable(s);
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
  const text = start < 0 ? body : body.slice(body.indexOf('\n', start) + 1);
  const end = start < 0 ? -1 : text.search(/^## Raw Text\s*$/m);
  // Comentário HTML (<!-- ai-memory:start -->) não aparece em nenhum leitor de Markdown.
  return (end < 0 ? text : text.slice(0, end)).replace(/<!--[\s\S]*?-->/g, '');
}

export const NoteDetailView = ({ detail, crumbs, isMutating, isLoadingDetail, isReindexing = false, onReindex, onDelete, highlightChunkId = null }: NoteDetailViewProps) => {
  const chunks = detail.chunks ?? [];
  // Trecho citado: a nota abre em Trechos; se ela não tiver mais esse trecho, abre a leitura normal.
  const [view, setView] = useState<'read' | 'chunks'>(() => (chunks.some((c) => c.chunk_id === highlightChunkId) ? 'chunks' : 'read'));
  const [menu, setMenu] = useState<'closed' | 'menu' | 'confirm'>('closed');
  const [copied, setCopied] = useState(false);
  const actionsRef = useRef<HTMLDivElement>(null);
  const cancelRef = useRef<HTMLButtonElement>(null);

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
              <NoteTitle text={part} />
              <ChevronRightIcon size={12} />
            </span>
          ))}
          <b><NoteTitle text={crumbs.at(-1) ?? detail.title} /></b>
          {copied && <span className="nd__copied">caminho copiado</span>}
        </nav>

        <div className="nd__actions" ref={actionsRef}>
          <Segmented
            label="Como ver a nota"
            value={view}
            onChange={setView}
            options={[
              { value: 'read', label: 'Ler' },
              { value: 'chunks', label: 'Trechos' },
            ]}
          />
          <button type="button" className="btn btn--sm" onClick={onReindex} disabled={busy}>
            <span className={`nd__reindex-icon${isReindexing ? ' ui-spin' : ''}`}>
              <RefreshIcon size={14} />
            </span>
            {isReindexing ? 'Reindexando…' : 'Reindexar'}
          </button>
          <button
            type="button"
            className="btn-icon"
            aria-label="Mais ações"
            aria-expanded={menu !== 'closed'}
            onClick={() => setMenu((prev) => (prev === 'closed' ? 'menu' : 'closed'))}
          >
            <MoreIcon size={17} />
          </button>

          {menu === 'menu' && (
            <div className="popover nd__menu">
              <button type="button" className="popover__item" onClick={copyPath}>
                <CopyIcon size={15} />
                Copiar caminho
              </button>
              <hr />
              <button
                type="button"
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
                Remove <b><NoteTitle text={detail.title} /></b> e {chunks.length === 1 ? 'seu trecho' : `seus ${chunks.length} trechos`} do SQLite e do
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
        <article className="reader">
          <h1 className="reader__title"><NoteTitle text={detail.title} /></h1>
          <div className="reader__meta">
            <span className="reader__fact">{typeLabel(detail.source_type)}</span>
            <span className="reader__fact">{chunks.length} {chunks.length === 1 ? 'trecho' : 'trechos'}</span>
            {tokens > 0 && <span className="reader__fact">{tokens.toLocaleString('pt-BR')} tokens</span>}
            {created && <span className="reader__fact">indexada em {created}</span>}
            {(detail.tags ?? []).filter((tag) => tag !== detail.source_type).map((tag) => (
              <span key={tag} className="reader__fact reader__tag">#{tag}</span>
            ))}
          </div>

          {view === 'chunks' ? (
            <NoteChunks chunks={chunks} highlightChunkId={highlightChunkId} />
          ) : (
            <div className="reader__body">{renderMarkdown(readableMarkdown(detail.structured_markdown ?? ''), detail.title)}</div>
          )}
        </article>
      </div>
    </>
  );
};
