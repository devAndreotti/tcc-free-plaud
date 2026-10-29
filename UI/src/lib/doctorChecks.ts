import type { DoctorCheck } from '../services/bridge';

export interface DoctorGroup {
  id: 'indice' | 'ia' | 'voz' | 'outros';
  title: string;
  checks: DoctorCheck[];
}

/** Rótulos amigáveis dos códigos do Doctor. Map (e não objeto) para `constructor` não casar. */
const CHECK_LABELS = new Map<string, string>([
  ['settings.embedding_model', 'Modelo de busca semântica'],
  ['settings.embedding_device', 'Dispositivo do modelo de busca semântica'],
  ['sqlite', 'Banco de notas (SQLite)'],
  ['fts', 'Busca por palavras'],
  ['chroma', 'Índice vetorial (Chroma)'],
  ['corpus', 'Corpus indexado'],
  ['answer_provider', 'Provedor de respostas'],
  ['api_key', 'Chave de API'],
  ['audio.dependencies', 'Bibliotecas de áudio'],
  ['audio.device', 'Dispositivo da transcrição'],
  ['audio.models', 'Modelos de voz'],
  ['audio.runtime', 'Diagnóstico de áudio'],
]);

const GROUPS: { id: DoctorGroup['id']; title: string }[] = [
  { id: 'indice', title: 'Índice' },
  { id: 'ia', title: 'IA' },
  { id: 'voz', title: 'Voz' },
  { id: 'outros', title: 'Outros' },
];

const INDEX_CODES = new Set(['sqlite', 'fts', 'chroma', 'corpus']);
const IA_CODES = new Set(['answer_provider', 'api_key']);

/** settings.* e o índice vão para Índice; audio.* para Voz; o resto cai em Outros. */
const groupOf = (code: string): DoctorGroup['id'] => {
  if (code.startsWith('settings.') || INDEX_CODES.has(code)) return 'indice';
  if (IA_CODES.has(code)) return 'ia';
  if (code.startsWith('audio.')) return 'voz';
  return 'outros';
};

/** Erro antes de aviso, aviso antes de ok. */
const SEVERITY: Record<DoctorCheck['status'], number> = { error: 0, warning: 1, ok: 2 };

export function checkLabel(code: string): string {
  return CHECK_LABELS.get(code) ?? code;
}

/** Agrupa em Índice, IA, Voz e Outros, omitindo grupos vazios. Array.sort é estável. */
export function groupChecks(checks: DoctorCheck[]): DoctorGroup[] {
  return GROUPS.map(({ id, title }) => ({
    id,
    title,
    checks: checks
      .filter((check) => groupOf(check.code) === id)
      .sort((a, b) => SEVERITY[a.status] - SEVERITY[b.status]),
  })).filter((group) => group.checks.length > 0);
}
