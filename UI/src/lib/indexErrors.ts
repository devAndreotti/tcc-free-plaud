import type { IndexJobFileError } from '../services/bridge';

/** O que o usuário pode fazer com o arquivo que falhou. */
export type IndexIssueAction = 'open' | 'reveal' | 'retry' | 'ignore' | 'voice-settings';

export interface IndexIssueInfo {
  /** Chave do grupo: falhas com a mesma explicação aparecem juntas. */
  kind: string;
  title: string;
  plural: string;
  description: string;
  tone: 'warn' | 'error';
  actions: IndexIssueAction[];
}

type Entry = Omit<IndexIssueInfo, 'kind'>;

const UNSUPPORTED: Entry = {
  title: 'Formato não suportado',
  plural: 'Formatos não suportados',
  description: 'O Escólio lê Markdown, texto (.txt), PDF e áudio (.wav, .mp3, .m4a, .ogg). Ignore para não aparecer de novo.',
  tone: 'warn',
  actions: ['reveal', 'ignore'],
};

const NO_ACCESS: Entry = {
  title: 'Sem acesso ao arquivo',
  plural: 'Arquivos sem acesso',
  description:
    'Está bloqueado por outro programa, sem permissão de leitura ou ainda não foi baixado do OneDrive. Libere o arquivo e tente de novo.',
  tone: 'error',
  actions: ['reveal', 'retry', 'ignore'],
};

// Códigos que a indexação devolve (pipeline: corpus/service.py, ingest, corpus/dropped.py).
const CATALOG: Record<string, Entry> = {
  EMPTY_CONTENT: {
    title: 'Nota sem conteúdo',
    plural: 'Notas sem conteúdo',
    description:
      'Só tem título, propriedades (frontmatter) ou está em branco: não há texto para pesquisar. Escreva algo e tente de novo, ou ignore (bom para templates).',
    tone: 'warn',
    actions: ['open', 'retry', 'ignore'],
  },
  PDF_PARSE_FAILED: {
    title: 'PDF sem texto legível',
    plural: 'PDFs sem texto legível',
    description:
      'O PDF não tem texto extraível (foi escaneado como imagem), tem senha ou está corrompido. Gere uma versão com texto (OCR) e tente de novo, ou ignore.',
    tone: 'error',
    actions: ['open', 'retry', 'ignore'],
  },
  UNSUPPORTED_MEDIA_TYPE: UNSUPPORTED,
  UNSUPPORTED_EXTENSION: UNSUPPORTED,
  INPUT_NOT_FOUND: {
    title: 'Arquivo não encontrado',
    plural: 'Arquivos não encontrados',
    description: 'Foi movido, renomeado ou apagado durante a indexação. Se ele voltou para o lugar, tente de novo.',
    tone: 'warn',
    actions: ['retry'],
  },
  DUPLICATE_NOTE_ID: {
    title: 'Nota duplicada',
    plural: 'Notas duplicadas',
    description:
      'Outro arquivo gerou a mesma nota (o mesmo caminho em outra pasta indexada). Renomeie um deles e tente de novo, ou ignore este.',
    tone: 'warn',
    actions: ['reveal', 'retry', 'ignore'],
  },
  AUDIO_MODEL_NOT_READY: {
    title: 'Modelo de voz não instalado',
    plural: 'Áudios sem modelo de voz',
    description: 'Para indexar áudio, baixe o modelo de transcrição em Configurações › Voz e tente de novo.',
    tone: 'error',
    actions: ['voice-settings', 'retry', 'ignore'],
  },
  PermissionError: NO_ACCESS,
  OSError: NO_ACCESS,
  UnicodeDecodeError: {
    title: 'Texto com codificação inválida',
    plural: 'Textos com codificação inválida',
    description: 'O arquivo não está em UTF-8. Salve-o de novo como UTF-8 e tente outra vez, ou ignore.',
    tone: 'error',
    actions: ['open', 'retry', 'ignore'],
  },
};

const AUDIO_FAILED: Entry = {
  title: 'Falha ao transcrever o áudio',
  plural: 'Áudios que falharam na transcrição',
  description: 'O áudio não pôde ser transcrito (arquivo danificado ou formato interno não suportado). Tente de novo ou ignore.',
  tone: 'error',
  actions: ['reveal', 'retry', 'ignore'],
};

const UNKNOWN: Entry = {
  title: 'Falha ao indexar',
  plural: 'Falhas ao indexar',
  description: 'Erro inesperado ao ler ou indexar o arquivo. Veja o detalhe técnico, tente de novo ou ignore.',
  tone: 'error',
  actions: ['reveal', 'retry', 'ignore'],
};

export function describeIndexIssue(code: string | null): IndexIssueInfo {
  if (code && CATALOG[code]) return { kind: code, ...CATALOG[code] };
  if (code?.startsWith('AUDIO_')) return { kind: 'AUDIO_FAILED', ...AUDIO_FAILED };
  return { kind: 'UNKNOWN', ...UNKNOWN };
}

/** Detalhe técnico que vale mostrar: a mensagem, quando diz algo além do próprio código. */
export function technicalDetail(issue: IndexJobFileError): string | null {
  const message = issue.message?.trim();
  if (!message || message === issue.error_code) return null;
  return message;
}

export interface IndexIssueGroup {
  info: IndexIssueInfo;
  items: IndexJobFileError[];
}

/** Agrupa falhas pela explicação; erros antes de avisos, na ordem em que apareceram. */
export function groupIndexIssues(issues: IndexJobFileError[]): IndexIssueGroup[] {
  const groups = new Map<string, IndexIssueGroup>();
  for (const issue of issues) {
    const info = describeIndexIssue(issue.error_code);
    const group = groups.get(info.kind) ?? { info, items: [] };
    group.items.push(issue);
    groups.set(info.kind, group);
  }
  const rank = { error: 0, warn: 1 } as const;
  return [...groups.values()].sort((a, b) => rank[a.info.tone] - rank[b.info.tone]);
}

const parts = (path: string) => path.split(/[\\/]/).filter(Boolean);

/** Nome do arquivo e a pasta dele relativa à pasta indexada ("Obsidian-Core › Templates"). */
export function splitIssuePath(path: string, root: string): { name: string; folder: string } {
  const pathParts = parts(path);
  const name = pathParts.pop() ?? path;
  const rootParts = parts(root);
  const underRoot =
    rootParts.length > 0 &&
    rootParts.every((part, index) => pathParts[index]?.toLocaleLowerCase() === part.toLocaleLowerCase());
  const folder = underRoot ? [rootParts[rootParts.length - 1], ...pathParts.slice(rootParts.length)] : pathParts;
  return { name, folder: folder.join(' › ') };
}
