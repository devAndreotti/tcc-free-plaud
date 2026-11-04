/**
 * conversationExport.ts
 * Exporta uma conversa para Markdown: título, perguntas e respostas, e as fontes de cada resposta
 * (caminho e faixa de caracteres, o mesmo texto que o botão de copiar põe em MessageBubble).
 * Função pura: não toca em arquivo nem em tela.
 */
import type { AskCitation } from '../services/bridge';
import type { MessageData } from '../components/MessageBubble';

export interface ConversationExportInput {
  title: string;
  messages: MessageData[];
  exportedAt: Date;
  /** Sem valor, as fontes vão junto. */
  includeSources?: boolean;
}

export type ExportFormat = 'md' | 'txt' | 'html' | 'json';
/** O PDF sai pela impressão do sistema, então não é um arquivo que o app grava. */
export type ExportChoice = ExportFormat | 'pdf';

/** Fontes de uma resposta, sem repetir o trecho: primeiro as das afirmações, depois as citações soltas (mesma ordem da tela). */
const uniqueSources = (citations: AskCitation[][]): AskCitation[] => {
  const seen = new Map<string, AskCitation>();
  for (const list of citations) {
    for (const citation of list) if (!seen.has(citation.chunk_id)) seen.set(citation.chunk_id, citation);
  }
  return [...seen.values()];
};

const sourcesOf = (message: MessageData): AskCitation[] =>
  message.ask ? uniqueSources([...message.ask.claims.map((claim) => claim.citations), message.ask.citations]) : [];

const textOf = (message: MessageData): string =>
  (message.role === 'user' ? message.content : message.ask?.answer ?? message.content).trim();

const formatSource = (citation: AskCitation): string =>
  `${citation.source_path ?? citation.note_id} (${citation.char_start}–${citation.char_end})`;

/** Monta o Markdown da conversa. */
export const buildConversationMarkdown = ({ title, messages, exportedAt, includeSources = true }: ConversationExportInput): string => {
  const lines: string[] = [`# ${title.trim() || 'Conversa'}`, '', `Exportada em ${exportedAt.toLocaleString('pt-BR')}`, ''];

  for (const message of messages) {
    if (message.role === 'user') {
      lines.push('## Pergunta', '', message.content.trim(), '');
      continue;
    }
    lines.push('## Resposta', '', (message.ask?.answer ?? message.content).trim(), '');
    const sources = includeSources ? sourcesOf(message) : [];
    if (sources.length > 0) {
      lines.push('**Fontes:**', '');
      sources.forEach((source, index) => lines.push(`${index + 1}. ${formatSource(source)}`));
      lines.push('');
    }
  }

  return lines.join('\n');
};

/** Nome sugerido para o arquivo: o título sem caracteres proibidos em nome de arquivo nem separador de pasta. */
export const conversationFileName = (title: string, extension: ExportFormat = 'md'): string => {
  // Remover caracteres de controle é o objetivo desta expressão.
  // eslint-disable-next-line no-control-regex
  const safe = title.replace(/[\\/:*?"<>|\x00-\x1f]/g, '-').replace(/\s+/g, ' ').trim().slice(0, 80).trim();
  return `${safe || 'conversa'}.${extension}`;
};

const exportDate = (date: Date): string => date.toLocaleString('pt-BR');

const buildPlainText = ({ title, messages, exportedAt, includeSources = true }: ConversationExportInput): string => {
  const lines: string[] = [title.trim() || 'Conversa', `Exportada em ${exportDate(exportedAt)}`, ''];
  for (const message of messages) {
    lines.push(message.role === 'user' ? 'Pergunta:' : 'Resposta:', textOf(message));
    const sources = includeSources ? sourcesOf(message) : [];
    if (sources.length > 0) {
      lines.push('Fontes:');
      sources.forEach((source, index) => lines.push(`${index + 1}. ${formatSource(source)}`));
    }
    lines.push('');
  }
  return lines.join('\n');
};

const buildJson = ({ title, messages, exportedAt, includeSources = true }: ConversationExportInput): string =>
  JSON.stringify(
    {
      title,
      exported_at: exportedAt.toISOString(),
      messages: messages.map((message) => ({
        role: message.role,
        text: textOf(message),
        ...(includeSources && message.role !== 'user'
          ? {
              sources: sourcesOf(message).map((source) => ({
                note_id: source.note_id,
                path: source.source_path ?? null,
                char_start: source.char_start,
                char_end: source.char_end,
              })),
            }
          : {}),
      })),
    },
    null,
    2,
  );

// A conversa tem texto de notas e de IA: nada dela entra no HTML sem escapar.
const escapeHtml = (text: string): string =>
  text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#39;');

const buildHtmlBody = ({ title, messages, exportedAt, includeSources = true }: ConversationExportInput): string => {
  const parts: string[] = [
    `<h1>${escapeHtml(title.trim() || 'Conversa')}</h1>`,
    `<p class="fontes">Exportada em ${escapeHtml(exportDate(exportedAt))}</p>`,
  ];
  for (const message of messages) {
    parts.push(`<h2>${message.role === 'user' ? 'Pergunta' : 'Resposta'}</h2>`, `<p>${escapeHtml(textOf(message))}</p>`);
    const sources = includeSources ? sourcesOf(message) : [];
    if (sources.length > 0) {
      const items = sources.map((source) => `<li>${escapeHtml(formatSource(source))}</li>`).join('');
      parts.push(`<ol class="fontes">${items}</ol>`);
    }
  }
  return parts.join('\n');
};

const buildHtmlDocument = (input: ConversationExportInput): string =>
  [
    '<!doctype html>',
    '<html lang="pt-BR"><head><meta charset="utf-8">',
    `<title>${escapeHtml(input.title.trim() || 'Conversa')}</title>`,
    '<style>body{max-width:720px;margin:40px auto;padding:0 20px;font:16px/1.6 Georgia,serif;color:#1a1a1a}',
    'h1{font-size:26px;margin-bottom:4px}h2{font-size:17px;margin:28px 0 6px}p{white-space:pre-wrap;overflow-wrap:anywhere}',
    '.fontes{font-size:13px;color:#555}</style></head><body>',
    buildHtmlBody(input),
    '</body></html>',
  ].join('\n');

/** Monta o arquivo no formato escolhido. */
export const buildConversationExport = (format: ExportFormat, input: ConversationExportInput): string => {
  if (format === 'txt') return buildPlainText(input);
  if (format === 'json') return buildJson(input);
  if (format === 'html') return buildHtmlDocument(input);
  return buildConversationMarkdown(input);
};

/** PDF: abre a impressão do sistema com só a conversa no papel ("Salvar como PDF"). */
export const printConversation = (input: ConversationExportInput): void => {
  const root = document.createElement('div');
  root.className = 'print-root';
  root.innerHTML = buildHtmlBody(input); // tudo escapado em buildHtmlBody
  document.body.appendChild(root);
  document.documentElement.classList.add('is-printing');
  const finish = () => {
    window.removeEventListener('afterprint', finish);
    document.documentElement.classList.remove('is-printing');
    root.remove();
  };
  window.addEventListener('afterprint', finish);
  window.print();
};
