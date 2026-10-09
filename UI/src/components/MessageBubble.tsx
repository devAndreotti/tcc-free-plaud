import { useMemo, useState } from 'react';
import type { AskCitation, AskResult, AskStrategy } from '../services/bridge';
import { AlertTriangleIcon, CopyIcon, SearchIcon } from './Icons';

export type MessageRole = 'user' | 'assistant';

export interface MessageData {
  id: string;
  role: MessageRole;
  content: string;
  timestamp: Date;
  /** Resposta estruturada do corpus, quando o backend a devolve. */
  ask?: AskResult;
}

interface MessageBubbleProps {
  message: MessageData;
  /** Pergunta de novo com outra estratégia (usado no estado "sem resposta"). */
  onRetry?: (query: string, strategy: AskStrategy) => void;
}

const STRATEGY_LABEL: Record<string, string> = {
  hybrid: 'híbrida',
  vector: 'vetorial',
  lexical: 'lexical',
};

export const TypingIndicator = () => (
  <div className="msg msg--ai fade-in" role="status" aria-label="Buscando no vault">
    <div className="msg__head">
      <span className="msg__mark" aria-hidden="true">ep</span>
      <span className="msg__searching">
        <span className="msg__spinner" aria-hidden="true" />
        <span>Buscando no vault…</span>
      </span>
    </div>
  </div>
);

function renderFormattedContent(text: string) {
  // A chave é a posição da linha no texto: a mensagem é estática, não se reordena.
  let offset = 0;
  return text.split('\n').map((line) => {
    const key = `l${offset}`;
    offset += line.length + 1;
    if (line.startsWith('- ') || line.startsWith('* ')) {
      return <div key={key} className="msg__li">{line.substring(2)}</div>;
    }
    if (line.startsWith('### ')) return <div key={key} className="msg__h3">{line.substring(4)}</div>;
    if (line.startsWith('## ')) return <div key={key} className="msg__h2">{line.substring(3)}</div>;
    if (line.startsWith('# ')) return <div key={key} className="msg__h1">{line.substring(2)}</div>;
    if (!line.trim()) return <div key={key} className="msg__gap" />;
    return <div key={key}>{line}</div>;
  });
}

const noteTitle = (citation: AskCitation) => {
  const raw = citation.source_path ?? citation.note_id;
  const base = raw.split(/[\\/]/).pop() ?? raw;
  return base.replace(/\.(md|markdown|txt|pdf)$/i, '');
};

/** Só as últimas pastas do caminho; o caminho completo fica no title. */
const shortPath = (path: string) => {
  const parts = path.split(/[\\/]/).filter(Boolean);
  return parts.length > 3 ? `…/${parts.slice(-3).join('/')}` : parts.join('/');
};

/** Numera as fontes na ordem em que aparecem e liga cada afirmação aos números. */
function useSources(ask: AskResult) {
  return useMemo(() => {
    const order: AskCitation[] = [];
    const indexOf = (c: AskCitation) => {
      const found = order.findIndex((item) => item.chunk_id === c.chunk_id);
      if (found >= 0) return found;
      order.push(c);
      return order.length - 1;
    };
    const claims = ask.claims.map((claim) => ({
      ...claim,
      refs: Array.from(new Set(claim.citations.map(indexOf))),
    }));
    ask.citations.forEach(indexOf);
    const support = order.map((c) =>
      ask.claims.some((claim) => claim.support_level === 'direct' && claim.citations.some((x) => x.chunk_id === c.chunk_id))
        ? 'direct'
        : 'partial'
    );
    return { claims, sources: order, support };
  }, [ask]);
}

const AnswerMeta = ({ ask, copyText }: { ask: AskResult; copyText?: string }) => {
  const [copied, setCopied] = useState(false);
  const parts = [
    ask.strategy ? STRATEGY_LABEL[ask.strategy] ?? ask.strategy : null,
    ask.top_k ? `top-${ask.top_k}` : null,
    ask.answer_provider ?? null,
    ask.latency_ms ? `${ask.latency_ms} ms` : null,
  ].filter(Boolean);

  const copy = async () => {
    if (!copyText) return;
    try {
      await navigator.clipboard.writeText(copyText);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1600);
    } catch {
      setCopied(false);
    }
  };

  if (parts.length === 0 && !copyText) return null;
  return (
    <div className="msg__meta mono">
      {parts.map((part, i) => (
        <span key={String(part)}>{i > 0 && <span className="msg__meta-sep">·</span>}{part}</span>
      ))}
      {copyText && (
        <button type="button" className="msg__action" onClick={copy} aria-label="Copiar resposta com as fontes">
          <CopyIcon size={14} />
          <span>{copied ? 'Copiado' : 'Copiar'}</span>
        </button>
      )}
    </div>
  );
};

// Motivos em que buscar só por palavra-chave não muda nada: nenhuma busca achou trecho algum.
const NO_LEXICAL_RETRY = new Set(['no_retrieval_hits', 'empty_corpus', 'query_without_content', 'query_term_not_in_corpus']);

const NoAnswer = ({ ask, onRetry }: { ask: AskResult; onRetry?: MessageBubbleProps['onRetry'] }) => (
  <div className="msg__none">
    <span className="msg__none-icon" aria-hidden="true"><SearchIcon size={17} /></span>
    <div>
      <h4>{ask.reason_for_no_answer === 'empty_corpus' ? 'O corpus ainda está vazio.' : 'Não encontrei isso no vault.'}</h4>
      <p>
        {ask.reason_for_no_answer === 'empty_corpus'
          ? 'Indexe a pasta do vault na Fila; depois as perguntas são respondidas a partir das notas.'
          : ask.limitations[0] ??
            'Nenhum trecho recuperado responde à pergunta com segurança. Se a informação estiver numa nota, reindexe a pasta dela ou cite o nome da nota na pergunta.'}
      </p>
      {ask.reason_for_no_answer && <div className="msg__why mono">motivo: {ask.reason_for_no_answer}</div>}
      {onRetry && ask.strategy !== 'lexical' && !NO_LEXICAL_RETRY.has(ask.reason_for_no_answer ?? '') && (
        <button type="button" className="msg__btn" onClick={() => onRetry(ask.query, 'lexical')}>
          Buscar só por palavra-chave
        </button>
      )}
    </div>
  </div>
);

const StructuredAnswer = ({ ask }: { ask: AskResult }) => {
  const { claims, sources, support } = useSources(ask);
  const [hl, setHl] = useState<number | null>(null);
  const noteCount = new Set(sources.map((s) => s.note_id)).size;

  const copyText = [
    claims.length ? claims.map((c) => `${c.text} ${c.refs.map((r) => `[${r + 1}]`).join('')}`).join(' ') : ask.answer ?? '',
    sources.length ? `\n\nFontes:\n${sources.map((s, i) => `[${i + 1}] ${s.source_path ?? s.note_id} (${s.char_start}–${s.char_end})`).join('\n')}` : '',
  ].join('');

  return (
    <>
      <div className="msg__head">
        <span className="msg__mark" aria-hidden="true">ep</span>
        <b>Resposta</b>
        {sources.length > 0 && (
          <span className="msg__head-sub">
            · a partir de {noteCount} {noteCount === 1 ? 'nota' : 'notas'}
          </span>
        )}
      </div>

      <div className="msg__answer">
        {claims.length > 0
          ? claims.map((claim, i) => (
              <span key={i}>
                <span
                  className={`msg__claim${claim.support_level === 'partial' ? ' msg__claim--partial' : ''}${claim.refs.includes(hl ?? -1) ? ' is-hl' : ''}`}
                >
                  {claim.text}
                </span>
                {claim.refs.map((ref) => (
                  <button
                    key={ref}
                    type="button"
                    className={`msg__ref${hl === ref ? ' is-hl' : ''}`}
                    aria-label={`Fonte ${ref + 1}${claim.support_level === 'partial' ? ', apoio parcial' : ''}`}
                    onMouseEnter={() => setHl(ref)}
                    onMouseLeave={() => setHl(null)}
                    onFocus={() => setHl(ref)}
                    onBlur={() => setHl(null)}
                  >
                    {ref + 1}
                  </button>
                ))}{' '}
              </span>
            ))
          : renderFormattedContent(ask.answer ?? '')}
      </div>

      {claims.some((c) => c.support_level === 'partial') && (
        <div className="msg__legend">
          <span><i className="msg__legend-line" />apoio direto</span>
          <span><i className="msg__legend-line msg__legend-line--dotted" />apoio parcial</span>
        </div>
      )}

      {sources.length > 0 && (
        <ol className="msg__sources" aria-label="Fontes">
          {sources.map((source, i) => (
            <li
              key={source.chunk_id}
              className={`msg__source${hl === i ? ' is-hl' : ''}`}
              onMouseEnter={() => setHl(i)}
              onMouseLeave={() => setHl(null)}
            >
              <span className="msg__source-n mono">{i + 1}</span>
              <div className="msg__source-body">
                <div className="msg__source-title">{noteTitle(source)}</div>
                <div className="msg__source-path mono" title={source.source_path ?? source.note_id}>
                  {source.source_path ? shortPath(source.source_path) : source.note_id}
                </div>
                <blockquote className="msg__source-quote">{source.snippet}</blockquote>
                <div className="msg__source-meta mono">
                  <span title="Versão da nota">v{source.note_version}</span>
                  <span>{source.char_start}–{source.char_end}</span>
                  {claims.length > 0 && (
                    <span className={`msg__support msg__support--${support[i]}`}>
                      {support[i] === 'direct' ? 'apoio direto' : 'apoio parcial'}
                    </span>
                  )}
                </div>
              </div>
            </li>
          ))}
        </ol>
      )}

      {ask.limitations.length > 0 && (
        <div className="msg__limits">
          <AlertTriangleIcon size={15} />
          <div>
            <b>{ask.limitations.length === 1 ? 'Limitação' : 'Limitações'}</b>
            {ask.limitations.map((item) => <p key={item}>{item}</p>)}
          </div>
        </div>
      )}

      <AnswerMeta ask={ask} copyText={copyText} />
    </>
  );
};

const MessageBubble = ({ message, onRetry }: MessageBubbleProps) => {
  if (message.role === 'user') {
    return (
      <article className="msg msg--user fade-in" aria-label="Sua pergunta">
        <div className="msg__bubble">{message.content}</div>
      </article>
    );
  }

  const { ask } = message;
  return (
    <article className="msg msg--ai fade-in" aria-label="Resposta">
      {ask?.no_answer ? (
        <>
          <div className="msg__head">
            <span className="msg__mark" aria-hidden="true">ep</span>
            <b>Sem resposta</b>
          </div>
          <NoAnswer ask={ask} onRetry={onRetry} />
          <AnswerMeta ask={ask} />
        </>
      ) : ask ? (
        <StructuredAnswer ask={ask} />
      ) : (
        <>
          <div className="msg__head">
            <span className="msg__mark" aria-hidden="true">ep</span>
            <b>Resposta</b>
          </div>
          <div className="msg__answer">{renderFormattedContent(message.content)}</div>
        </>
      )}
    </article>
  );
};

export default MessageBubble;
