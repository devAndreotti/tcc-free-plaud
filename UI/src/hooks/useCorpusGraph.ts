/**
 * useCorpusGraph.ts — nós do grafo lidos do corpus (notas indexadas da vault ativa).
 *
 * Cada nota vira um MarkdownNode: id = note_id e path = nome da raiz do corpus que a contém +
 * caminho relativo à raiz. Nota fora de qualquer raiz cai na pasta "Soltas".
 */

import { useCallback, useContext, useEffect, useState } from 'react';
import { QueueContext } from '../contexts/QueueContextObject';
import { bridge, type CorpusRoot, type NoteSummary } from '../services/bridge';
import type { MarkdownNode } from '../lib/vaultGraph';

// Mesmo evento que notifyCorpusChanged() (hooks/useCorpusHealth) dispara após indexar/apagar
const CORPUS_CHANGED = 'escolio:corpus-changed';
const LOOSE_FOLDER = 'Soltas';

const slash = (p: string) => p.replaceAll('\\', '/').replace(/\/+$/, '');

/** Converte as notas do corpus em nós do grafo (função pura, testável). */
export function buildCorpusNodes(notes: NoteSummary[], roots: CorpusRoot[]): MarkdownNode[] {
  // Raiz mais específica primeiro: raízes aninhadas não disputam a mesma nota
  const rootList = roots
    .map((r) => slash(r.root))
    .filter(Boolean)
    .sort((a, b) => b.length - a.length);

  return notes.map((note) => {
    const src = slash(note.source_path ?? '');
    const file = src.split('/').at(-1) ?? '';
    const root = rootList.find((r) => src.toLowerCase().startsWith(`${r.toLowerCase()}/`));
    const path = root
      ? `${root.split('/').at(-1)}/${src.slice(root.length + 1)}`
      : `${LOOSE_FOLDER}/${file || note.title}`;
    return {
      id: note.note_id,
      name: note.title || file.replace(/\.[^.]+$/, ''),
      path,
      size: 0,
      modified: note.created_at,
    };
  });
}

export function useCorpusGraph() {
  const [nodes, setNodes] = useState<MarkdownNode[]>([]);
  const job = useContext(QueueContext)?.job;
  // Id do job que acabou de terminar (status diferente de running); muda uma vez por job
  const jobDone = job && job.status !== 'running' ? job.job_id : null;

  const refresh = useCallback(async () => {
    try {
      const [notes, roots] = await Promise.all([
        bridge.listNotes?.() ?? [],
        bridge.listCorpusRoots?.() ?? [],
      ]);
      setNodes(buildCorpusNodes(notes, roots));
    } catch {
      // Mantém o grafo anterior: uma falha de leitura não deve apagar o desenho
    }
  }, []);

  // eslint-disable-next-line react-hooks/set-state-in-effect -- carga inicial vinda da bridge (sistema externo).
  useEffect(() => { void refresh(); }, [refresh]);

  useEffect(() => {
    const onChange = () => { void refresh(); };
    window.addEventListener(CORPUS_CHANGED, onChange);
    return () => window.removeEventListener(CORPUS_CHANGED, onChange);
  }, [refresh]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- job da Fila terminou (sistema externo).
    if (jobDone) void refresh();
  }, [jobDone, refresh]);

  return { nodes, refresh };
}
