import { useCallback, useEffect, useMemo, useState } from 'react';
import { FileIcon, XIcon } from './Icons';
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

/** Exportado só para os testes resetarem o cache de módulo entre casos. */
// eslint-disable-next-line react-refresh/only-export-components -- helper de teste, não um componente.
export const __resetNotesCacheForTests = () => {
  notesCache = null;
};

const NotesPanel = () => {
  const [notes, setNotes] = useState<NoteSummary[]>(() => notesCache ?? []);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [detail, setDetail] = useState<NoteDetail | null>(null);
  const [query, setQuery] = useState('');
  const [confirmation, setConfirmation] = useState('');
  const [isLoadingList, setIsLoadingList] = useState(false);
  const [isLoadingDetail, setIsLoadingDetail] = useState(false);
  const [isMutating, setIsMutating] = useState(false);
  const [status, setStatus] = useState('Pronto.');

  // Skeleton só no primeiro load real (sem cache) - com cache, a lista
  // aparece imediatamente e a revalidação acontece em silêncio.
  const showSkeleton = isLoadingList && notes.length === 0;

  const filteredNotes = useMemo(() => {
    const term = query.trim().toLowerCase();
    if (!term) return notes;
    return notes.filter((note) => {
      const haystack = `${note.note_id} ${note.title} ${note.source_path} ${note.tags.join(' ')}`.toLowerCase();
      return haystack.includes(term);
    });
  }, [notes, query]);

  const loadNotes = useCallback(async () => {
    const hadCache = notesCache !== null;
    setIsLoadingList(true);
    if (!hadCache) setStatus('Carregando notas indexadas...');
    try {
      const loaded = await bridge.listNotes();
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
        return loaded[0]?.note_id ?? null;
      });
      setStatus(`${loaded.length} nota(s) indexada(s).`);
    } catch (error) {
      setStatus(error instanceof Error ? error.message : 'Falha ao carregar notas.');
    } finally {
      setIsLoadingList(false);
    }
  }, []);

  useEffect(() => {
    void loadNotes();
  }, [loadNotes]);

  useEffect(() => {
    if (!selectedId) {
      setDetail(null);
      return;
    }

    let cancelled = false;
    const loadDetail = async () => {
      setIsLoadingDetail(true);
      try {
        const loaded = await bridge.getNoteDetail(selectedId);
        if (!cancelled) {
          setDetail(loaded);
          setConfirmation('');
        }
      } catch (error) {
        if (!cancelled) {
          setDetail(null);
          setStatus(error instanceof Error ? error.message : 'Falha ao abrir nota.');
        }
      } finally {
        if (!cancelled) {
          setIsLoadingDetail(false);
        }
      }
    };

    void loadDetail();
    return () => {
      cancelled = true;
    };
  }, [selectedId]);

  const handleDelete = async () => {
    if (!detail) return;
    setIsMutating(true);
    setStatus('Removendo nota do corpus...');
    try {
      const result: NoteDeleteResult = await bridge.deleteNote(detail.note_id, confirmation);
      if (!result.ok) {
        setStatus(result.message ?? 'Confirmação necessária.');
        return;
      }
      setStatus(`Nota removida. Vetores apagados: ${result.deleted_vectors ?? 0}.`);
      setDetail(null);
      setSelectedId(null);
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
    setStatus('Reindexando nota...');
    try {
      const result: NoteReindexResult = await bridge.reindexNote(detail.note_id);
      setStatus(`${result.status}: ${result.chunks_indexed} chunk(s). ${result.message ?? ''}`.trim());
      await loadNotes();
      setSelectedId(detail.note_id);
    } catch (error) {
      setStatus(error instanceof Error ? error.message : 'Falha ao reindexar nota.');
    } finally {
      setIsMutating(false);
    }
  };

  return (
    <main className="main notes-panel" id="notes-panel">
      <section className="notes-panel__list" aria-label="Notas indexadas">
        <div className="notes-panel__toolbar">
          <div>
            <h1 className="notes-panel__title">Notes</h1>
            <p className="notes-panel__meta">{notes.length} nota(s) no corpus</p>
          </div>
          <button
            type="button"
            className="notes-panel__button"
            onClick={loadNotes}
            disabled={isLoadingList}
          >
            Atualizar
          </button>
        </div>

        <input
          className="notes-panel__search"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="Filtrar por título, caminho ou id"
          aria-label="Filtrar notas"
        />

        <div className="notes-panel__items" aria-label="Notas">
          {showSkeleton ? (
            <div aria-hidden="true" aria-label="Carregando notas">
              {[0, 1, 2, 3].map((key) => (
                <div key={key} className="notes-panel__item">
                  <span className="skeleton-box" />
                  <span className="notes-panel__item-body">
                    <span className="skeleton-box skeleton-box--name" />
                    <span className="skeleton-box skeleton-box--path" />
                  </span>
                </div>
              ))}
            </div>
          ) : (
            <>
              {filteredNotes.map((note) => (
                <button
                  key={note.note_id}
                  type="button"
                  className={`notes-panel__item ${selectedId === note.note_id ? 'notes-panel__item--active' : ''}`}
                  onClick={() => setSelectedId(note.note_id)}
                >
                  <span className="notes-panel__item-icon">
                    <FileIcon size={15} />
                  </span>
                  <span className="notes-panel__item-body">
                    <span className="notes-panel__item-title">{note.title}</span>
                    <span className="notes-panel__item-path">{note.source_path}</span>
                  </span>
                  <span className="notes-panel__item-count">{note.chunk_count}</span>
                </button>
              ))}

              {!isLoadingList && filteredNotes.length === 0 && (
                <div className="notes-panel__empty">Nenhuma nota encontrada.</div>
              )}
            </>
          )}
        </div>
      </section>

      <section className="notes-panel__detail" aria-label="Detalhe da nota">
        {detail ? (
          <>
            <div className="notes-panel__detail-header">
              <div>
                <h2 className="notes-panel__detail-title">{detail.title}</h2>
                <p className="notes-panel__detail-path">{detail.source_path}</p>
              </div>
              <div className="notes-panel__actions">
                <button
                  type="button"
                  className="notes-panel__button"
                  onClick={handleReindex}
                  disabled={isMutating || isLoadingDetail}
                >
                  Reindexar
                </button>
                <button
                  type="button"
                  className="notes-panel__button notes-panel__button--danger"
                  onClick={handleDelete}
                  disabled={isMutating || isLoadingDetail}
                >
                  <XIcon size={12} />
                  Apagar
                </button>
              </div>
            </div>

            <dl className="notes-panel__facts">
              <div>
                <dt>note_id</dt>
                <dd>{detail.note_id}</dd>
              </div>
              <div>
                <dt>tipo</dt>
                <dd>{detail.source_type}</dd>
              </div>
              <div>
                <dt>chunks</dt>
                <dd>{detail.chunk_count}</dd>
              </div>
              <div>
                <dt>criado</dt>
                <dd>{detail.created_at}</dd>
              </div>
            </dl>

            <div className="notes-panel__confirm">
              <label htmlFor="note-delete-confirm">Confirmar exclusão</label>
              <input
                id="note-delete-confirm"
                value={confirmation}
                onChange={(event) => setConfirmation(event.target.value)}
                placeholder="Digite APAGAR"
              />
            </div>

            <div className="notes-panel__split">
              <div className="notes-panel__markdown">
                <h3>Markdown estruturado</h3>
                <pre>{detail.structured_markdown}</pre>
              </div>
              <div className="notes-panel__chunks">
                <h3>Chunks</h3>
                {detail.chunks.map((chunk) => (
                  <article key={chunk.chunk_id} className="notes-panel__chunk">
                    <div className="notes-panel__chunk-head">
                      <strong>#{chunk.chunk_index}</strong>
                      <span>{chunk.token_count} tokens</span>
                    </div>
                    <code>{chunk.chunk_id}</code>
                    <p>{chunk.snippet}</p>
                  </article>
                ))}
              </div>
            </div>
          </>
        ) : (
          <div className="notes-panel__empty notes-panel__empty--detail">
            {isLoadingDetail ? 'Abrindo nota...' : 'Selecione uma nota indexada.'}
          </div>
        )}

        <div className="notes-panel__status" role="status">
          {status}
        </div>
      </section>
    </main>
  );
};

export default NotesPanel;
