import { useMemo, useState, type ReactNode } from 'react';
import type { AskCitation, AskResult, AskStage, AskStrategy } from '../services/bridge';
import { focusNoteInGraph } from '../lib/vaultGraph';
import { AlertTriangleIcon, CopyIcon, ExternalIcon, ListIcon, SearchIcon, SparkleIcon } from './Icons';

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
  /** Abre a nota da fonte no trecho citado (clique no card, ou Enter/Espaço com ele focado). */
  onOpenSource?: (noteId: string, chunkId: string) => void;
}

const STRATEGY_LABEL: Record<string, string> = {
  hybrid: 'híbrida',
  vector: 'vetorial',
  lexical: 'lexical',
};

interface TypingIndicatorProps {
  /** Estágio da pergunta da aba; sem ele, ou buscando, mostra a busca no vault. */
  stage?: AskStage;
  /** Texto que a IA já escreveu (estágio writing). */
  partial?: string;
  /** Modelo que escreve a resposta, para o cabeçalho. */
  model?: string;
}

export const TypingIndicator = ({ stage, partial = '', model }: TypingIndicatorProps) => {
  if (stage !== 'writing') {
    return (
      <div className="msg msg--ai fade-in" role="status" aria-label="Buscando no vault">
        <div className="msg__head">
          <span className="msg__mark" aria-hidden="true">ES</span>
          <span className="msg__searching">
            <span className="msg__spinner" aria-hidden="true" />
            <span>Buscando no vault…</span>
          </span>
        </div>
      </div>
    );
  }
  const header = model ? `Escrevendo com ${model}…` : 'Escrevendo a resposta…';
  return (
    <div className="msg msg--ai fade-in" role="status" aria-label={header}>
      <div className="msg__head">
        <span className="msg__mark" aria-hidden="true">ES</span>
        <span className="msg__searching">
          <span className="msg__spinner" aria-hidden="true" />
          <span>{header}</span>
        </span>
      </div>
      {/* aria-live off: o texto muda a cada consulta; a resposta final é anunciada pelo histórico. */}
      <div className="msg__answer" aria-live="off">
        {renderFormattedContent(partial.trimStart(), <span className="msg__cursor" aria-hidden="true" />)}
      </div>
    </div>
  );
};

function renderFormattedContent(text: string, tail: ReactNode = null, inline: (line: string) => ReactNode = (line) => line) {
  // A chave é a posição da linha no texto: a mensagem é estática, não se reordena.
  let offset = 0;
  const lines = text.split('\n');
  return lines.map((line, i) => {
    const key = `l${offset}`;
    offset += line.length + 1;
    // O trecho final (o cursor, enquanto a IA escreve) entra na última linha, colado no texto.
    const end = i === lines.length - 1 ? tail : null;
    if (line.startsWith('- ') || line.startsWith('* ')) {
      return <div key={key} className="msg__li">{inline(line.substring(2))}{end}</div>;
    }
    if (line.startsWith('### ')) return <div key={key} className="msg__h3">{inline(line.substring(4))}{end}</div>;
    if (line.startsWith('## ')) return <div key={key} className="msg__h2">{inline(line.substring(3))}{end}</div>;
    if (line.startsWith('# ')) return <div key={key} className="msg__h1">{inline(line.substring(2))}{end}</div>;
    if (!line.trim()) return <div key={key} className="msg__gap">{end}</div>;
    return <div key={key}>{inline(line)}{end}</div>;
  });
}

/** Corta o texto gerado nos marcadores [n]: `ref` é o índice da fonte; sem fonte, o marcador não aparece. */
const splitRefs = (text: string, refOf: (n: number) => number): Array<string | { ref: number }> =>
  text.split(/[ \t]*\[(\d+)\]/).flatMap((part, i): Array<string | { ref: number }> => {
    if (i % 2 === 0) return part ? [part] : [];
    const ref = refOf(Number(part));
    return ref >= 0 ? [{ ref }] : [];
  });

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

// Motivos do descarte da IA, em português (o código bruto fica nos detalhes técnicos).
const DISCARD_TEXT = new Map<string, string>([
  ['generated_no_answer_sentinel', 'A IA disse que os trechos não respondem'],
  ['generated_generic_no_answer', 'A IA disse que os trechos não respondem'],
  ['echoed_context_metadata', 'A IA repetiu o cabeçalho da nota'],
  ['unsupported_number', 'A IA citou algo que não está nos trechos'],
  ['unsupported_anchor', 'A IA citou algo que não está nos trechos'],
  ['low_claim_overlap', 'A IA escreveu longe dos trechos'],
  ['empty_generated_answer', 'A IA devolveu só [n], sem texto'],
  ['echoed_title', 'A IA copiou um título em vez de responder'],
  ['provider_error', 'A IA falhou; mostramos o trecho'],
]);

// Limitações que vêm da tentativa do modelo (descarte, falha do provedor): vão para os detalhes técnicos.
const MODEL_LIMITATION = /^(Resposta generativa ignorada|Provider de resposta falhou|unsupported_)/;

/** Quem escreveu a resposta, sempre visível: a IA, só os trechos, ou a IA que foi descartada. */
const AnswerFooter = ({ ask }: { ask: AskResult }) => {
  if (ask.generated) {
    return (
      <div className="msg__footer">
        <span className="msg__seal msg__seal--ai">
          <SparkleIcon size={13} />
          Escrita pela IA · {ask.answer_model ?? 'IA'}
        </span>
      </div>
    );
  }
  if (!ask.answer_provider || ask.answer_provider === 'extractive') {
    return (
      <div className="msg__footer">
        <span className="msg__seal">
          <ListIcon size={13} />
          Só trechos · sem IA
        </span>
      </div>
    );
  }
  const modelLimits = ask.limitations.filter((item) => MODEL_LIMITATION.test(item));
  return (
    <div className="msg__footer">
      <span className="msg__seal msg__seal--warn">
        <AlertTriangleIcon size={13} />
        IA descartada · mostramos o trecho
      </span>
      <p className="msg__discard-why">
        {(ask.answer_discard_reason && DISCARD_TEXT.get(ask.answer_discard_reason)) ||
          'A IA não respondeu com texto a partir dos trechos.'}
      </p>
      <details className="msg__details">
        <summary>Detalhes técnicos</summary>
        <div className="mono">
          <div>{ask.answer_discard_reason ?? 'sem código'}</div>
          {modelLimits.map((item) => (
            <div key={item}>{item}</div>
          ))}
        </div>
      </details>
    </div>
  );
};

const StructuredAnswer = ({ ask, onOpenSource }: { ask: AskResult; onOpenSource?: MessageBubbleProps['onOpenSource'] }) => {
  const { claims, sources, support } = useSources(ask);
  const limits = ask.limitations.filter((item) => !MODEL_LIMITATION.test(item));
  const [hl, setHl] = useState<number | null>(null);
  const noteCount = new Set(sources.map((s) => s.note_id)).size;
  // Resposta escrita pela IA (validada contra os trechos): mostra o texto dela no lugar dos claims.
  const showClaims = claims.length > 0 && !(ask.generated && ask.answer);
  // Com answer_sources, os [n] do texto viram botões da fonte (índice em `sources`); sem fonte, somem.
  const withRefs = Boolean(ask.generated && ask.answer && ask.answer_sources?.length);
  const refOf = (n: number) => sources.findIndex((s) => s.chunk_id === ask.answer_sources?.[n - 1]);

  // A fonte em destaque aqui também aparece no grafo ao lado: a nota e as pastas de onde veio.
  const highlight = (i: number | null) => {
    setHl(i);
    focusNoteInGraph(i === null ? null : sources[i]?.note_id ?? null);
  };

  const refButton = (ref: number, key: number, partial = false) => (
    <button
      key={key}
      type="button"
      className={`msg__ref${hl === ref ? ' is-hl' : ''}`}
      aria-label={`Fonte ${ref + 1}${partial ? ', apoio parcial' : ''}`}
      onMouseEnter={() => highlight(ref)}
      onMouseLeave={() => highlight(null)}
      onFocus={() => highlight(ref)}
      onBlur={() => highlight(null)}
    >
      {ref + 1}
    </button>
  );

  const copyText = [
    showClaims
      ? claims.map((c) => `${c.text} ${c.refs.map((r) => `[${r + 1}]`).join('')}`).join(' ')
      : withRefs
        ? splitRefs(ask.answer ?? '', refOf).map((part) => (typeof part === 'string' ? part : ` [${part.ref + 1}]`)).join('')
        : ask.answer ?? '',
    sources.length ? `\n\nFontes:\n${sources.map((s, i) => `[${i + 1}] ${s.source_path ?? s.note_id} (${s.char_start}–${s.char_end})`).join('\n')}` : '',
  ].join('');

  return (
    <>
      <div className="msg__head">
        <span className="msg__mark" aria-hidden="true">ES</span>
        <b>Resposta</b>
        {sources.length > 0 && (
          <span className="msg__head-sub">
            · a partir de {noteCount} {noteCount === 1 ? 'nota' : 'notas'}
          </span>
        )}
      </div>

      <div className="msg__answer">
        {showClaims
          ? claims.map((claim) => (
              <span key={`${claim.refs.join(',')}:${claim.text}`}>
                <span
                  className={`msg__claim${claim.support_level === 'partial' ? ' msg__claim--partial' : ''}${claim.refs.includes(hl ?? -1) ? ' is-hl' : ''}`}
                >
                  {claim.text}
                </span>
                {claim.refs.map((ref) => refButton(ref, ref, claim.support_level === 'partial'))}{' '}
              </span>
            ))
          : renderFormattedContent(ask.answer ?? '', null, withRefs
              ? (line) => splitRefs(line, refOf).map((part, i) => (typeof part === 'string' ? part : refButton(part.ref, i)))
              : undefined)}
      </div>

      {showClaims && claims.some((c) => c.support_level === 'partial') && (
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
              onMouseEnter={() => highlight(i)}
              onMouseLeave={() => highlight(null)}
              onClick={() => {
                // Quem selecionou texto do trecho para copiar não quer sair do chat.
                if (window.getSelection()?.toString()) return;
                onOpenSource?.(source.note_id, source.chunk_id);
              }}
              onKeyDown={(event) => {
                // Só com o próprio card focado: Enter ou Espaço no título (botão) já dispara o clique.
                if (event.target !== event.currentTarget || (event.key !== 'Enter' && event.key !== ' ')) return;
                event.preventDefault();
                onOpenSource?.(source.note_id, source.chunk_id);
              }}
              tabIndex={onOpenSource ? 0 : undefined}
            >
              <span className="msg__source-n mono">{i + 1}</span>
              <div className="msg__source-body">
                <div className="msg__source-title">
                  <button type="button" className="msg__source-open" aria-label={`Abrir ${noteTitle(source)} no trecho citado`}>
                    {noteTitle(source)}
                    <ExternalIcon size={12} />
                  </button>
                </div>
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

      {limits.length > 0 && (
        <div className="msg__limits">
          <AlertTriangleIcon size={15} />
          <div>
            <b>{limits.length === 1 ? 'Limitação' : 'Limitações'}</b>
            {limits.map((item) => <p key={item}>{item}</p>)}
          </div>
        </div>
      )}

      <AnswerFooter ask={ask} />
      <AnswerMeta ask={ask} copyText={copyText} />
    </>
  );
};

const MessageBubble = ({ message, onRetry, onOpenSource }: MessageBubbleProps) => {
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
            <span className="msg__mark" aria-hidden="true">ES</span>
            <b>Sem resposta</b>
          </div>
          <NoAnswer ask={ask} onRetry={onRetry} />
          <AnswerMeta ask={ask} />
        </>
      ) : ask ? (
        <StructuredAnswer ask={ask} onOpenSource={onOpenSource} />
      ) : (
        <>
          <div className="msg__head">
            <span className="msg__mark" aria-hidden="true">ES</span>
            <b>Resposta</b>
          </div>
          <div className="msg__answer">{renderFormattedContent(message.content)}</div>
        </>
      )}
    </article>
  );
};

export default MessageBubble;
