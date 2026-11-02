import { useCallback, useEffect, useMemo, useState } from 'react';
import { ChevronRightIcon, NoteIcon, PdfIcon, SearchIcon, WaveIcon } from './Icons';
import { NoteDetailSkeleton, NoteDetailView } from './NoteDetailView';
import { Sk } from './ui/Loading';
import { NoteTitle } from './NoteTitle';
import { commonRoot, formatDate, relativeParts, typeLabel } from '../lib/notes';
import { stripEmoji } from '../lib/noteIcons';
import { notifyCorpusChanged } from '../hooks/useCorpusHealth';
import { CORPUS_CHANGED, CORPUS_PROGRESS_EVENT } from '../lib/corpusEvents';
import {
  bridge,
  type NoteDeleteResult,
  type NoteDetail,
  type NoteReindexResult,
  type NoteSummary,
} from '../services/bridge';

// Cache em variável de módulo (fora do componente): sobrevive à desmontagem
// de NotesPanel quando o usuário troca de aba (App.tsx desmonta a view ao
// trocar), evitando recarregar do zero e mostrar tela vazia toda vez que o
// usuário volta para Notes.
// ponytail: cache não sobrevive a fechar o processo - promover para
// localStorage/Context se precisar persistir entre sessões do app.
let notesCache: NoteSummary[] | null = null;
// Pastas recolhidas: pelo mesmo motivo, sobrevivem à troca de aba.
let closedFoldersCache = new Set<string>();
const rememberClosedFolders = (folders: Set<string>) => {
  closedFoldersCache = folders;
};

/** Exportado só para os testes resetarem o cache de módulo entre casos. */
// eslint-disable-next-line react-refresh/only-export-components -- helper de teste, não um componente.
export const __resetNotesCacheForTests = () => {
  notesCache = null;
  closedFoldersCache = new Set();
};

// O backend confirma exclusão por texto; a UI pede a confirmação no próprio popover.
const ROOT_GROUP = 'Raiz do vault';
const DELETE_CONFIRMATION = 'APAGAR';

const TypeIcon = ({ type }: { type: string | null | undefined }) => {
  const t = (type ?? '').toLowerCase();
  if (t === 'pdf') return <PdfIcon size={15} />;
  if (t === 'audio' || t === 'wav' || t === 'm4a' || t === 'mp3') return <WaveIcon size={15} />;
  return <NoteIcon size={15} />;
};

interface NotesPanelProps {
  /** Nota pedida pelo grafo: abre o detalhe dela ao montar ou quando muda */
  initialNoteId?: string | null;
  /** Trecho citado numa resposta do chat: a nota abre com ele destacado */
  initialChunkId?: string | null;
}

const NotesPanel = ({ initialNoteId = null, initialChunkId = null }: NotesPanelProps) => {
  const [notes, setNotes] = useState<NoteSummary[]>(() => notesCache ?? []);
  const [selectedId, setSelectedId] = useState<string | null>(initialNoteId);
  const [detail, setDetail] = useState<NoteDetail | null>(null);
  const [query, setQuery] = useState('');
  const [typeFilter, setTypeFilter] = useState('all');
  const [isLoadingList, setIsLoadingList] = useState(false);
  const [isLoadingDetail, setIsLoadingDetail] = useState(false);
  const [isMutating, setIsMutating] = useState(false);
  const [isReindexing, setIsReindexing] = useState(false);
  const [status, setStatus] = useState('');
  const [closedFolders, setClosedFolders] = useState(closedFoldersCache);
  // Com cache a lista já vem pronta: sem animação ao voltar para a aba.
  const [firstLoad] = useState(notesCache === null);
  const [slowId, setSlowId] = useState<string | null>(null);
  const [failedId, setFailedId] = useState<string | null>(null);
  const term = query.trim().toLowerCase();
  const isFiltering = Boolean(term) || typeFilter !== 'all';

  // Skeleton só no primeiro load real (sem cache) - com cache, a lista
  // aparece imediatamente e a revalidação acontece em silêncio.
  const showSkeleton = isLoadingList && notes.length === 0;

  const root = useMemo(() => commonRoot(notes.map((note) => note.source_path ?? '')), [notes]);
  const types = useMemo(
    () => Array.from(new Set(notes.map((note) => note.source_type).filter(Boolean))) as string[],
    [notes]
  );

  const groups = useMemo(() => {
    const filtered = notes.filter((note) => {
      if (typeFilter !== 'all' && note.source_type !== typeFilter) return false;
      if (!term) return true;
      const haystack = `${note.note_id} ${note.title} ${note.source_path ?? ''} ${(note.tags ?? []).join(' ')}`.toLowerCase();
      return haystack.includes(term);
    });
    const byFolder = new Map<string, NoteSummary[]>();
    filtered.forEach((note) => {
      const folder = relativeParts(note.source_path, root).slice(0, -1).join(' / ') || ROOT_GROUP;
      byFolder.set(folder, [...(byFolder.get(folder) ?? []), note]);
    });
    return Array.from(byFolder.entries()).sort(([a], [b]) =>
      a === ROOT_GROUP ? -1 : b === ROOT_GROUP ? 1 : a.localeCompare(b, 'pt-BR')
    );
  }, [notes, term, typeFilter, root]);

  const visibleCount = groups.reduce((sum, [, items]) => sum + items.length, 0);
  const countLabel = isFiltering
    ? `${visibleCount.toLocaleString('pt-BR')} ${visibleCount === 1 ? 'encontrada' : 'encontradas'}`
    : `${notes.length.toLocaleString('pt-BR')} no corpus`;

  const toggleFolder = (folder: string) => {
    const next = new Set(closedFolders);
    if (!next.delete(folder)) next.add(folder);
    rememberClosedFolders(next);
    setClosedFolders(next);
  };

  const clearFilters = () => {
    setQuery('');
    setTypeFilter('all');
  };

  // Sem escolha do usuário, abre a primeira nota da lista como ela aparece na tela.
  const activeId = selectedId ?? groups[0]?.[1][0]?.note_id ?? null;

  const loadNotes = useCallback(async () => {
    setIsLoadingList(true);
    try {
      const loaded = await bridge.listNotes();
      if (initialNoteId && !loaded.some((note) => note.note_id === initialNoteId)) {
        setStatus('Esta nota não existe mais no corpus.');
      }
      // Evita re-render/flicker quando o resultado é idêntico ao já exibido.
      const changed = JSON.stringify(loaded) !== JSON.stringify(notesCache);
      notesCache = loaded;
      if (changed) {
        setNotes(loaded);
      }
      setSelectedId((current) => {
        if (current && loaded.some((note) => note.note_id === current)) {
          return current;
        }
        return null;
      });
    } catch (error) {
      setStatus(error instanceof Error ? error.message : 'Falha ao carregar notas.');
    } finally {
      setIsLoadingList(false);
    }
  }, [initialNoteId]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- carga inicial vinda da bridge (sistema externo).
    void loadNotes();
  }, [loadNotes]);

  // A lista acompanha a indexação: cada lote gravado e o fim do job. O skeleton só aparece com a lista vazia.
  useEffect(() => {
    const onCorpus = () => void loadNotes();
    window.addEventListener(CORPUS_PROGRESS_EVENT, onCorpus);
    window.addEventListener(CORPUS_CHANGED, onCorpus);
    return () => {
      window.removeEventListener(CORPUS_PROGRESS_EVENT, onCorpus);
      window.removeEventListener(CORPUS_CHANGED, onCorpus);
    };
  }, [loadNotes]);

  useEffect(() => {
    if (!activeId) {
      // eslint-disable-next-line react-hooks/set-state-in-effect -- sem nota ativa, o detalhe some junto.
      setDetail(null);
      return;
    }

    let cancelled = false;
    const loadDetail = async () => {
      setIsLoadingDetail(true);
      try {
        const loaded = await bridge.getNoteDetail(activeId);
        if (!cancelled) setDetail(loaded);
      } catch (error) {
        if (!cancelled) {
          setDetail(null);
          setFailedId(activeId);
          setStatus(error instanceof Error ? error.message : 'Falha ao abrir nota.');
        }
      } finally {
        if (!cancelled) setIsLoadingDetail(false);
      }
    };

    void loadDetail();
    return () => {
      cancelled = true;
    };
  }, [activeId]);

  // Trocar de nota: até 150 ms a nota anterior continua na tela, para resposta rápida não piscar.
  const opening = Boolean(activeId) && detail?.note_id !== activeId && failedId !== activeId;
  useEffect(() => {
    if (!opening) return undefined;
    const timer = window.setTimeout(() => setSlowId(activeId), 150);
    return () => window.clearTimeout(timer);
  }, [opening, activeId]);
  const showDetailSkeleton = showSkeleton || (opening && (!detail || slowId === activeId));

  const handleDelete = async () => {
    if (!detail) return;
    setIsMutating(true);
    setStatus('Removendo nota do corpus…');
    try {
      const result: NoteDeleteResult = await bridge.deleteNote(detail.note_id, DELETE_CONFIRMATION);
      if (!result.ok) {
        setStatus(result.message ?? 'Não foi possível remover a nota.');
        return;
      }
      setStatus(`“${stripEmoji(detail.title)}” removida do corpus · ${result.deleted_vectors ?? 0} vetores apagados.`);
      setDetail(null);
      setSelectedId(null);
      notifyCorpusChanged();
      await loadNotes();
    } catch (error) {
      setStatus(error instanceof Error ? error.message : 'Falha ao remover nota.');
    } finally {
      setIsMutating(false);
    }
  };

  const handleReindex = async () => {
    if (!detail) return;
    setIsMutating(true);
    setIsReindexing(true);
    setStatus('Reindexando nota…');
    try {
      const result: NoteReindexResult = await bridge.reindexNote(detail.note_id);
      setStatus(`Nota reindexada · ${result.chunks_indexed} ${result.chunks_indexed === 1 ? 'trecho' : 'trechos'}. ${result.message ?? ''}`.trim());
      await loadNotes();
      setSelectedId(result.note_id ?? detail.note_id);
      notifyCorpusChanged();
    } catch (error) {
      setStatus(error instanceof Error ? error.message : 'Falha ao reindexar nota.');
    } finally {
      setIsMutating(false);
      setIsReindexing(false);
    }
  };

  return (
    <main className="main notes" id="notes-panel">
      <section className="notes__list" aria-label="Notas indexadas">
        <div className="notes__top">
          <div className="notes__head">
            <h1>Notas</h1>
            {showSkeleton ? <Sk w={70} h={11} /> : <span className="mono">{countLabel}</span>}
          </div>

          <label className="notes__search">
            <SearchIcon size={15} />
            <input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Buscar título, pasta ou tag"
              aria-label="Filtrar notas"
            />
          </label>

          {types.length > 1 && (
            <div className="notes__filters" role="group" aria-label="Filtrar por tipo">
              {['all', ...types].map((type) => (
                <button
                  key={type}
                  type="button"
                  className="notes__chip"
                  aria-pressed={typeFilter === type}
                  onClick={() => setTypeFilter(type)}
                >
                  {type === 'all' ? 'Todas' : typeLabel(type)}
                </button>
              ))}
            </div>
          )}
        </div>

        <div className="notes__items" aria-label="Notas">
          {showSkeleton ? (
            <div className="load-wait" aria-hidden="true">
              {[0, 1, 2, 3, 4].map((key) => (
                <div key={key} className="notes__item notes__item--skeleton">
                  <span className="skeleton-box skeleton-box--icon" />
                  <span className="notes__item-body">
                    <span className="skeleton-box skeleton-box--name" />
                    <span className="skeleton-box skeleton-box--path" />
                  </span>
                </div>
              ))}
            </div>
          ) : (
            <div className={firstLoad ? 'load-on' : undefined}>
              {groups.map(([folder, items]) => {
                // A busca abre tudo: nota encontrada não fica escondida em pasta recolhida.
                const open = Boolean(term) || !closedFolders.has(folder);
                return (
                  <div key={folder} className="notes__group">
                    <button type="button" className="notes__group-title" aria-expanded={open} onClick={() => toggleFolder(folder)}>
                      <span className="notes__chev"><ChevronRightIcon size={13} /></span>
                      <span className="notes__group-name"><NoteTitle text={folder} /></span>
                      <span className="notes__group-count">{items.length}</span>
                    </button>
                    {open && items.map((note) => {
                      const active = activeId === note.note_id;
                      const date = formatDate(note.created_at, false);
                      return (
                        <button
                          key={note.note_id ?? note.title}
                          type="button"
                          className={`notes__item${active ? ' notes__item--active' : ''}`}
                          aria-current={active ? 'true' : undefined}
                          onClick={() => setSelectedId(note.note_id)}
                        >
                          <TypeIcon type={note.source_type} />
                          <span className="notes__item-body">
                            <span className="notes__item-title"><NoteTitle text={note.title} /></span>
                            <span className="notes__item-meta">
                              {note.chunk_count ?? 0} {note.chunk_count === 1 ? 'trecho' : 'trechos'}
                              {date && ` · ${date}`}
                            </span>
                          </span>
                        </button>
                      );
                    })}
                  </div>
                );
              })}

              {!isLoadingList && visibleCount === 0 && notes.length === 0 && !status && (
                <div className="notes__empty">Nenhuma nota indexada ainda. Indexe uma pasta na Fila.</div>
              )}
              {visibleCount === 0 && notes.length > 0 && (
                <div className="notes__noresults">
                  <SearchIcon size={22} />
                  <span>Nenhuma nota com esse filtro.</span>
                  <button type="button" className="btn btn--sm" onClick={clearFilters}>Limpar filtros</button>
                </div>
              )}
            </div>
          )}
        </div>
      </section>

      <section className="notes__detail" aria-label="Detalhe da nota">
        {showDetailSkeleton ? (
          <NoteDetailSkeleton />
        ) : detail ? (
          <NoteDetailView
            key={detail.note_id}
            detail={detail}
            crumbs={relativeParts(detail.source_path, root)}
            isMutating={isMutating}
            isLoadingDetail={isLoadingDetail}
            isReindexing={isReindexing}
            onReindex={handleReindex}
            onDelete={handleDelete}
            highlightChunkId={initialChunkId}
          />
        ) : (
          <div className="notes__empty notes__empty--detail">
            Selecione uma nota para ler.
          </div>
        )}

        {status && (
          <div className="notes__status" role="status">
            {status}
          </div>
        )}
      </section>
    </main>
  );
};

export default NotesPanel;
