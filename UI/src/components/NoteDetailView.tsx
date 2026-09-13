import { type NoteDetail } from '../services/bridge';
import { XIcon } from './Icons';

interface NoteDetailViewProps {
  detail: NoteDetail;
  isMutating: boolean;
  isLoadingDetail: boolean;
  confirmation: string;
  onConfirmationChange: (value: string) => void;
  onReindex: () => void;
  onDelete: () => void;
}

export const NoteDetailView = ({
  detail,
  isMutating,
  isLoadingDetail,
  confirmation,
  onConfirmationChange,
  onReindex,
  onDelete,
}: NoteDetailViewProps) => (
  <>
    <div className="notes-panel__detail-head">
      <div>
        <h2>{detail.title}</h2>
        <p className="notes-panel__path">{detail.source_path}</p>
      </div>
      <div className="notes-panel__actions">
        <button
          type="button"
          className="notes-panel__button"
          onClick={onReindex}
          disabled={isMutating || isLoadingDetail}
        >
          Reindexar
        </button>
        <button
          type="button"
          className="notes-panel__button notes-panel__button--danger"
          onClick={onDelete}
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
        onChange={(event) => onConfirmationChange(event.target.value)}
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
);
