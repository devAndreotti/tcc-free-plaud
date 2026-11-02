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
}

/** Fontes de uma resposta, sem repetir o trecho: primeiro as das afirmações, depois as citações soltas (mesma ordem da tela). */
const uniqueSources = (citations: AskCitation[][]): AskCitation[] => {
  const seen = new Map<string, AskCitation>();
  for (const list of citations) {
    for (const citation of list) if (!seen.has(citation.chunk_id)) seen.set(citation.chunk_id, citation);
  }
  return [...seen.values()];
};

const formatSource = (citation: AskCitation): string =>
  `${citation.source_path ?? citation.note_id} (${citation.char_start}–${citation.char_end})`;

/** Monta o Markdown da conversa. */
export const buildConversationMarkdown = ({ title, messages, exportedAt }: ConversationExportInput): string => {
  const lines: string[] = [`# ${title.trim() || 'Conversa'}`, '', `Exportada em ${exportedAt.toLocaleString('pt-BR')}`, ''];

  for (const message of messages) {
    if (message.role === 'user') {
      lines.push('## Pergunta', '', message.content.trim(), '');
      continue;
    }
    lines.push('## Resposta', '', (message.ask?.answer ?? message.content).trim(), '');
    const sources = message.ask
      ? uniqueSources([...message.ask.claims.map((claim) => claim.citations), message.ask.citations])
      : [];
    if (sources.length > 0) {
      lines.push('**Fontes:**', '');
      sources.forEach((source, index) => lines.push(`${index + 1}. ${formatSource(source)}`));
      lines.push('');
    }
  }

  return lines.join('\n');
};

/** Nome sugerido para o arquivo: o título sem caracteres proibidos em nome de arquivo nem separador de pasta. */
export const conversationFileName = (title: string): string => {
  // Remover caracteres de controle é o objetivo desta expressão.
  // eslint-disable-next-line no-control-regex
  const safe = title.replace(/[\\/:*?"<>|\x00-\x1f]/g, '-').replace(/\s+/g, ' ').trim().slice(0, 80).trim();
  return `${safe || 'conversa'}.md`;
};
