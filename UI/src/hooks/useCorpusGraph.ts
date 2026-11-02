/**
 * useCorpusGraph.ts — nós do grafo lidos do corpus (notas indexadas da vault ativa).
 *
 * Cada nota vira um MarkdownNode: id = note_id e path = nome da raiz do corpus que a contém +
 * caminho relativo à raiz. Nota fora de qualquer raiz cai na pasta "Soltas".
 * Junto vêm as ligações [[...]] entre essas notas (links), só as que apontam para notas do grafo.
 *
 * Com um job rodando, o grafo acompanha ao vivo: cada lote gravado entra (lendo só as notas novas), os arquivos
 * lidos e ainda não gravados aparecem como pendentes, e `activeId` aponta o arquivo que está sendo indexado.
 */

import { useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react';
import { QueueContext } from '../contexts/QueueContextObject';
import { CORPUS_CHANGED } from '../lib/corpusEvents';
import { bridge, type CorpusRoot, type NoteSummary } from '../services/bridge';
import { pendingNodeId, type MarkdownNode, type VaultLink } from '../lib/vaultGraph';

const LOOSE_FOLDER = 'Soltas';

const slash = (p: string) => p.replaceAll('\\', '/').replace(/\/+$/, '');
const samePath = (p: string) => slash(p).toLowerCase();
const fileOf = (src: string) => src.split('/').at(-1) ?? '';

// Raiz mais específica primeiro: raízes aninhadas não disputam a mesma nota
const rootsBySpecificity = (roots: CorpusRoot[]) =>
  roots
    .map((r) => slash(r.root))
    .filter(Boolean)
    .sort((a, b) => b.length - a.length);

/** Caminho do arquivo no grafo: nome da raiz + caminho relativo; fora de qualquer raiz, "Soltas". */
function graphPath(src: string, rootList: string[], fallback: string): string {
  const root = rootList.find((r) => src.toLowerCase().startsWith(`${r.toLowerCase()}/`));
  return root ? `${root.split('/').at(-1)}/${src.slice(root.length + 1)}` : `${LOOSE_FOLDER}/${fileOf(src) || fallback}`;
}

/** Converte as notas do corpus em nós do grafo (função pura, testável). */
export function buildCorpusNodes(notes: NoteSummary[], roots: CorpusRoot[]): MarkdownNode[] {
  const rootList = rootsBySpecificity(roots);
  return notes.map((note) => {
    const src = slash(note.source_path ?? '');
    return {
      id: note.note_id,
      name: note.title || fileOf(src).replace(/\.[^.]+$/, ''),
      path: graphPath(src, rootList, note.title),
      size: 0,
      modified: note.created_at,
    };
  });
}

/** Arquivos lidos e ainda não gravados, como nós tracejados; quem já tem nota (versão nova a caminho) fica como está. */
export function buildPendingNodes(files: string[], notes: NoteSummary[], roots: CorpusRoot[]): MarkdownNode[] {
  const rootList = rootsBySpecificity(roots);
  const known = new Set(notes.map((note) => samePath(note.source_path ?? '')));
  return files
    .filter((file) => !known.has(samePath(file)))
    .map((file) => {
      const src = slash(file);
      const path = graphPath(src, rootList, src);
      return { id: pendingNodeId(path), name: fileOf(src).replace(/\.[^.]+$/, ''), path, size: 0, modified: '', pending: true };
    });
}

/** Junta as notas gravadas desde a última leitura às que já estavam no grafo (versão nova substitui a antiga). */
export function mergeNotes(current: NoteSummary[], delta: NoteSummary[]): NoteSummary[] {
  const byId = new Map(current.map((note) => [note.note_id, note]));
  for (const note of delta) byId.set(note.note_id, note);
  return [...byId.values()];
}

// created_at mais recente: a próxima leitura pede só o que veio a partir dele
const latestCreatedAt = (notes: NoteSummary[]) => notes.reduce((latest, note) => (note.created_at > latest ? note.created_at : latest), '');

// Ligações entre notas; falha ao lê-las não pode apagar o grafo de pastas e notas
async function readLinks(): Promise<VaultLink[]> {
  try {
    return (await bridge.listNoteLinks?.()) ?? [];
  } catch {
    return [];
  }
}

export interface GraphLive {
  /** Nome do arquivo que está sendo indexado; null quando o job está num passo que não é de um arquivo só. */
  current: string | null;
  /** Arquivos lidos que ainda esperam gravação. */
  pending: number;
}

export function useCorpusGraph() {
  const [notes, setNotes] = useState<NoteSummary[]>([]);
  const [roots, setRoots] = useState<CorpusRoot[]>([]);
  const [noteLinks, setNoteLinks] = useState<VaultLink[]>([]);
  const [loaded, setLoaded] = useState(false);
  const job = useContext(QueueContext)?.job;
  const running = job?.status === 'running';
  // Id do job que acabou de terminar (status diferente de running); muda uma vez por job
  const jobDone = job && !running ? job.job_id : null;
  // Notas já gravadas pelo job em andamento: em micro-lotes cada lote gravado já responde no chat, então entra no grafo.
  const committed = running ? job.progress?.committed_count ?? 0 : 0;
  // O job vem novo a cada segundo; a chave só muda quando a lista muda, para o grafo não remontar à toa
  const pendingKey = running ? (job.progress?.pending_files ?? []).join('\n') : '';
  const currentPath = running ? job.progress?.current_path ?? null : null;
  // Leitura mais recente: uma resposta lenta de um lote anterior não sobrescreve o grafo mais novo
  const seq = useRef(0);
  const notesRef = useRef<NoteSummary[]>([]);

  const load = useCallback(async (onlyNew: boolean) => {
    const mine = ++seq.current;
    const since = onlyNew ? latestCreatedAt(notesRef.current) : '';
    try {
      const [listed, listedRoots, listedLinks] = await Promise.all([
        since ? bridge.listNotes?.({ since }) ?? [] : bridge.listNotes?.() ?? [],
        bridge.listCorpusRoots?.() ?? [],
        readLinks(),
      ]);
      if (mine !== seq.current) return;
      const next = since ? mergeNotes(notesRef.current, listed) : listed;
      notesRef.current = next;
      setNotes(next);
      setRoots(listedRoots);
      setNoteLinks(listedLinks);
    } catch {
      // Mantém o grafo anterior: uma falha de leitura não deve apagar o desenho
    } finally {
      if (mine === seq.current) setLoaded(true);
    }
  }, []);

  // Leitura completa: é ela que tira do grafo o que foi apagado; durante o job só entram as notas novas.
  const refresh = useCallback(() => load(false), [load]);

  useEffect(() => { void refresh(); }, [refresh]);

  useEffect(() => {
    const onChange = () => { void refresh(); };
    window.addEventListener(CORPUS_CHANGED, onChange);
    return () => window.removeEventListener(CORPUS_CHANGED, onChange);
  }, [refresh]);

  useEffect(() => {
    if (jobDone) void refresh();
  }, [jobDone, refresh]);

  useEffect(() => {
    if (committed > 0) void load(true);
  }, [committed, load]);

  const pendingNodes = useMemo(
    () => buildPendingNodes(pendingKey ? pendingKey.split('\n') : [], notes, roots),
    [pendingKey, notes, roots],
  );
  const nodes = useMemo(() => [...buildCorpusNodes(notes, roots), ...pendingNodes], [notes, roots, pendingNodes]);

  // Link para nota fora do grafo (apagada, de outra vault) não vira aresta solta
  const links = useMemo(() => {
    const ids = new Set(nodes.map((n) => n.id));
    return noteLinks.filter((l) => ids.has(l.source) && ids.has(l.target));
  }, [nodes, noteLinks]);

  // O arquivo atual, se já for nó do grafo: a nota gravada ou o pendente. Passos do job em cima da pasta inteira não têm nó.
  const activeId = useMemo(() => {
    if (!currentPath) return null;
    const current = samePath(currentPath);
    const note = notes.find((n) => samePath(n.source_path ?? '') === current);
    if (note) return note.note_id;
    const path = graphPath(slash(currentPath), rootsBySpecificity(roots), '');
    return pendingNodes.find((n) => n.id === pendingNodeId(path))?.id ?? null;
  }, [currentPath, notes, roots, pendingNodes]);

  const live = useMemo<GraphLive | null>(() => {
    if (!running) return null;
    const file = currentPath ? fileOf(slash(currentPath)) : '';
    return { current: /\.[^.]+$/.test(file) ? file : null, pending: pendingNodes.length };
  }, [running, currentPath, pendingNodes]);

  return { nodes, links, refresh, activeId, live, loaded };
}
