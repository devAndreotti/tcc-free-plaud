import { useMemo, useState, type ReactNode } from 'react';
import type { AskCitation, AskResult, AskStage, AskStrategy } from '../services/bridge';
import { discardText } from '../lib/discardReasons';
import { focusNoteInGraph } from '../lib/vaultGraph';
import { ExternalIcon, SearchIcon } from './Icons';
import { Glyph, GlyphBadge, type GlyphName } from './ui/Glyph';

export type MessageRole = 'user' | 'assistant';

export interface MessageData {
  id: string;
  role: MessageRole;
  content: string;
  timestamp: Date;
  /** Resposta estruturada do corpus, quando o backend a devolve. */
  ask?: AskResult;
  /** Pergunta que falhou: "Tentar de novo" a repete com a mesma estratégia. */
  retry?: { query: string; strategy: AskStrategy };
  /** Resposta dada com um job da Fila rodando: quanto daquela pasta já estava no corpus naquele momento. */
  indexing?: { jobId: string; ready: number; total: number };
}

interface MessageBubbleProps {
  message: MessageData;
  /** Pergunta de novo com outra estratégia (usado no estado "sem resposta"). */
  onRetry?: (query: string, strategy: AskStrategy) => void;
  /** Abre a nota da fonte no trecho citado (clique no card, ou Enter/Espaço com ele focado). */
  onOpenSource?: (noteId: string, chunkId: string) => void;
  /** Job da Fila rodando agora: enquanto for o da resposta, o aviso diz "durante a indexação"; depois, oferece perguntar de novo. */
  runningJobId?: string | null;
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
  /** Provedor da resposta: com IA (diferente de extractive), a trilha já mostra a etapa de escrita. */
  provider?: string | null;
}

type StepState = 'on' | 'done' | 'wait';

const Step = ({ state, icon, children }: { state: StepState; icon: GlyphName; children: ReactNode }) => (
  <li className={`msg__step is-${state}`}>
    <span className="msg__step-dot" aria-hidden="true">
      <Glyph name={state === 'done' ? 'check' : icon} size={12} strokeWidth={state === 'done' ? 2.2 : 1.75} />
    </span>
    <span>{children}</span>
  </li>
);

/** Espera da resposta: as fases que o backend manda (retrieving → writing), sem etapas inventadas no meio. */
export const TypingIndicator = ({ stage, partial = '', model, provider }: TypingIndicatorProps) => {
  const writing = stage === 'writing';
  const withAi = writing || Boolean(provider && provider !== 'extractive');
  const header = model ? `Escrevendo com ${model}…` : 'Escrevendo a resposta…';
  return (
    <div className="msg msg--ai fade-in" role="status" aria-label={writing ? header : 'Buscando no vault'}>
      <div className="msg__head">
        <span className="msg__mark" aria-hidden="true">ES</span>
        <ol className="msg__steps">
          <Step state={writing ? 'done' : 'on'} icon="search">{writing ? 'Busca no vault' : 'Buscando no vault…'}</Step>
          {withAi && (
            <>
              <li className={`msg__rail${writing ? '' : ' ui-flow'}`} aria-hidden="true" />
              <Step state={writing ? 'on' : 'wait'} icon="stars">
                {writing ? header : model ? `Escrever com ${model}` : 'Escrever a resposta'}
              </Step>
            </>
          )}
        </ol>
      </div>
      {writing && (
        // aria-live off: o texto muda a cada consulta; a resposta final é anunciada pelo histórico.
        <div className="msg__draft rise" aria-live="off">
          <span className="msg__draft-tag">
            <span className="msg__draft-dot ui-pulse" aria-hidden="true" />
            rascunho, ainda sendo validado
          </span>
          <div className="msg__answer">
            {renderFormattedContent(partial.trimStart(), <span className="msg__cursor" aria-hidden="true" />, draftLine)}
          </div>
        </div>
      )}
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
function splitRefs(text: string, refOf: (n: number) => number): Array<string | { ref: number }> {
  return text.split(/[ \t]*\[(\d+)\]/).flatMap((part, i): Array<string | { ref: number }> => {
    if (i % 2 === 0) return part ? [part] : [];
    const ref = refOf(Number(part));
    return ref >= 0 ? [{ ref }] : [];
  });
}

/** Linha do rascunho: os [n] que a IA já escreveu viram chips (as fontes só ficam ligadas depois de validar). */
function draftLine(line: string): ReactNode {
  return splitRefs(line, (n) => n - 1).map((part, i) =>
    typeof part === 'string' ? part : <span key={i} className="msg__ref msg__ref--draft">{part.ref + 1}</span>
  );
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
  const parts = (
    [
      ['search', ask.strategy ? STRATEGY_LABEL[ask.strategy] ?? ask.strategy : null],
      ['layers', ask.top_k ? `top-${ask.top_k}` : null],
      ['clock', ask.latency_ms ? `${ask.latency_ms} ms` : null],
    ] as Array<[GlyphName, string | null]>
  ).filter((part): part is [GlyphName, string] => Boolean(part[1]));

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
      {parts.map(([icon, text]) => (
        <span key={icon} className="msg__meta-item">
          <Glyph name={icon} size={13} />
          {text}
        </span>
      ))}
      {copyText && (
        <button type="button" className={`msg__action${copied ? ' is-copied' : ''}`} onClick={copy} aria-label="Copiar resposta com as fontes">
          {copied ? (
            <span className="msg__action-ok pop"><Glyph name="check" size={14} strokeWidth={2.2} /></span>
          ) : (
            <Glyph name="copy" size={14} />
          )}
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
      {ask.reason_for_no_answer && (
        <details className="msg__details">
          <summary>Detalhes técnicos</summary>
          <div className="mono">motivo: {ask.reason_for_no_answer}</div>
        </details>
      )}
      {onRetry && ask.strategy !== 'lexical' && !NO_LEXICAL_RETRY.has(ask.reason_for_no_answer ?? '') && (
        <button type="button" className="msg__btn" onClick={() => onRetry(ask.query, 'lexical')}>
          Buscar só por palavra-chave
        </button>
      )}
    </div>
  </div>
);

// Limitações que vêm da tentativa do modelo (descarte, falha do provedor): vão para os detalhes técnicos.
const MODEL_LIMITATION = /^(Resposta generativa ignorada|A IA falhou|A IA declarou|A IA respondeu com uma negativa)/;

/** A IA foi chamada mas o texto dela não aparece: a resposta veio dos trechos. */
const isDiscarded = (ask: AskResult) => !ask.generated && Boolean(ask.answer_provider) && ask.answer_provider !== 'extractive';

/** Quem escreveu a resposta, no cabeçalho: a IA, só os trechos, ou a IA que foi descartada. */
const AnswerSeal = ({ ask }: { ask: AskResult }) => {
  if (ask.generated) {
    return (
      <span className="msg__seal msg__seal--ai">
        <Glyph name="stars" size={13} />
        Escrita pela IA · {ask.answer_model ?? 'IA'}
      </span>
    );
  }
  if (!isDiscarded(ask)) {
    return (
      <span className="msg__seal">
        <Glyph name="list" size={13} />
        Só trechos · sem IA
      </span>
    );
  }
  return (
    <span className="msg__seal msg__seal--warn">
      <Glyph name="shield" size={13} />
      IA descartada · mostramos o trecho
    </span>
  );
};

/** Por que o texto da IA ficou de fora: o motivo em português e, nos detalhes, o código e o que o backend anotou. */
const DiscardNotice = ({ ask }: { ask: AskResult }) => {
  const modelLimits = ask.limitations.filter((item) => MODEL_LIMITATION.test(item));
  const model = ask.answer_model;
  const lead =
    ask.answer_discard_reason === 'provider_error'
      ? model ? `O ${model} não respondeu.` : 'A IA não respondeu.'
      : `O texto ${model ? `do ${model}` : 'da IA'} não passou na conferência com os trechos.`;
  return (
    <section className="msg__discard" aria-label="Por que a IA foi descartada">
      <GlyphBadge name="shield" size={32} tone="warn" />
      <div className="msg__discard-body">
        <h4 className="msg__discard-why">{discardText(ask.answer_discard_reason)}</h4>
        <p>{lead} A resposta acima são frases das suas notas, cada uma com a fonte.</p>
        <details className="msg__details">
          <summary>
            <Glyph name="code" size={13} />
            Detalhes técnicos
            <Glyph name="chev" size={13} strokeWidth={2} className="msg__details-chev" />
          </summary>
          <div className="mono">
            <div className="msg__details-code">{ask.answer_discard_reason ?? 'sem código'}</div>
            {modelLimits.map((item) => (
              <div key={item}>{item}</div>
            ))}
          </div>
        </details>
      </div>
    </section>
  );
};

const StructuredAnswer = ({ ask, onOpenSource, during }: { ask: AskResult; onOpenSource?: MessageBubbleProps['onOpenSource']; during?: ReactNode }) => {
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
        <AnswerSeal ask={ask} />
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

      {during}

      {isDiscarded(ask) && <DiscardNotice ask={ask} />}

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
                  {showClaims && (
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
        <section className="msg__limits" aria-label={limits.length === 1 ? 'Limitação' : 'Limitações'}>
          <GlyphBadge name="info" size={28} tone="muted" />
          <div>
            <b>{limits.length === 1 ? 'Limitação' : 'Limitações'}</b>
            {limits.map((item) => <p key={item}>{item}</p>)}
          </div>
        </section>
      )}

      <AnswerMeta ask={ask} copyText={copyText} />
    </>
  );
};

/** A resposta veio com a indexação no meio: diz quanto já estava no corpus e, terminado o job, oferece perguntar de novo. */
const DuringIndexing = ({ ask, indexing, running, onRetry }: {
  ask: AskResult;
  indexing: NonNullable<MessageData['indexing']>;
  running: boolean;
  onRetry?: MessageBubbleProps['onRetry'];
}) => {
  const { ready, total } = indexing;
  const pct = total > 0 ? Math.min(100, (ready / total) * 100) : 0;
  return (
    <section className={`msg__during${running ? '' : ' msg__during--done'}`} aria-label={running ? 'Indexação em andamento' : 'Indexação terminada'}>
      <GlyphBadge name={running ? 'layers' : 'checkCircle'} size={32} tone={running ? 'accent' : 'ok'} />
      <div className="msg__during-text">
        <b>{running ? 'Respondida durante a indexação' : 'A indexação terminou'}</b>
        <p>
          {running
            ? `${ready} de ${total} arquivos desta pasta já estavam no corpus. A resposta pode mudar quando o resto entrar.`
            : `Esta resposta usou ${ready} de ${total} arquivos. Pergunte de novo para buscar no corpus completo.`}
        </p>
        <span className="msg__during-track" aria-hidden="true">
          <span className="msg__during-fill" style={{ width: `${running ? pct : 100}%` }} />
        </span>
      </div>
      {!running && onRetry && (
        <button type="button" className="msg__btn pop" onClick={() => onRetry(ask.query, ask.strategy === 'lexical' || ask.strategy === 'vector' ? ask.strategy : 'hybrid')}>
          <Glyph name="refresh" size={14} />
          Perguntar de novo
        </button>
      )}
    </section>
  );
};

const MessageBubble = ({ message, onRetry, onOpenSource, runningJobId = null }: MessageBubbleProps) => {
  if (message.role === 'user') {
    return (
      <article className="msg msg--user fade-in" aria-label="Sua pergunta">
        <div className="msg__bubble">{message.content}</div>
      </article>
    );
  }

  const { ask, retry, indexing } = message;
  const during = ask && indexing
    ? <DuringIndexing ask={ask} indexing={indexing} running={indexing.jobId === runningJobId} onRetry={onRetry} />
    : null;
  return (
    <article className="msg msg--ai fade-in" aria-label="Resposta">
      {ask?.no_answer ? (
        <>
          <div className="msg__head">
            <span className="msg__mark" aria-hidden="true">ES</span>
            <b>Sem resposta</b>
          </div>
          <NoAnswer ask={ask} onRetry={onRetry} />
          {during}
          <AnswerMeta ask={ask} />
        </>
      ) : ask ? (
        <StructuredAnswer ask={ask} onOpenSource={onOpenSource} during={during} />
      ) : (
        <>
          <div className="msg__head">
            <span className="msg__mark" aria-hidden="true">ES</span>
            <b>Resposta</b>
          </div>
          <div className="msg__answer">{renderFormattedContent(message.content)}</div>
          {retry && onRetry && (
            <button type="button" className="msg__btn" onClick={() => onRetry(retry.query, retry.strategy)}>
              Tentar de novo
            </button>
          )}
        </>
      )}
    </article>
  );
};

export default MessageBubble;
