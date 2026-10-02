import { useCallback, useEffect, useRef, useState, type DragEvent } from 'react';
import { bridge, type DroppedFileEvent, type WatcherIngestionEvent } from '../services/bridge';
import { FileIcon, XIcon } from './Icons';

/** Extensões de arquivo aceitas pela dropzone (áudio, PDF, texto). */
const ACCEPTED_EXTENSIONS = ['.wav', '.mp3', '.m4a', '.ogg', '.pdf', '.txt', '.md'];

const isAccepted = (fileName: string) =>
  ACCEPTED_EXTENSIONS.some((ext) => fileName.toLowerCase().endsWith(ext));

interface DropzoneFile {
  id: string;
  name: string;
  status: 'indexing' | 'indexed' | 'unchanged' | 'failed';
  message: string | null;
}

/** Notificação toast de auto-ingestão exibida temporariamente. */
export interface DropzoneToast {
  id: string;
  message: string;
  status: 'success' | 'failed';
}

interface DropzoneProps {
  /** Diretório monitorado pelo watcher; se ausente, drag-drop apenas lista os arquivos soltos. */
  watchDirectory?: string | null;
  /** Notifica o componente pai a cada evento de auto-ingestão recebido do watcher. */
  onToast?: (toast: DropzoneToast) => void;
}

const POLL_INTERVAL_MS = 1500;
// O caminho do arquivo chega ao Python por outro canal, um instante depois do drop no JS.
const ENQUEUE_RETRIES = 5;
const ENQUEUE_RETRY_MS = 300;
const NO_PATH_MESSAGE = 'O caminho do arquivo não chegou ao backend. Soltar para indexar só funciona no app desktop.';

const STATUS_LABEL: Record<DropzoneFile['status'], { label: string; tone: string }> = {
  indexing: { label: 'indexando', tone: ' pill--accent' },
  indexed: { label: 'indexado', tone: ' pill--ok' },
  unchanged: { label: 'sem mudança', tone: '' },
  failed: { label: 'falhou', tone: ' pill--err' },
};

const dropMessage = (event: DroppedFileEvent): string => {
  if (event.status === 'indexed') return `${event.name} entrou no corpus (${event.chunks} chunks).`;
  if (event.status === 'unchanged') return `${event.name} já estava indexado, sem mudança.`;
  return `Falha ao indexar ${event.name}: ${event.message ?? 'erro desconhecido'}`;
};

const dropToast = (event: DroppedFileEvent): DropzoneToast => ({
  id: `drop-${event.name}-${Date.now()}`,
  status: event.status === 'failed' ? 'failed' : 'success',
  message: dropMessage(event),
});

/** Área de drag-and-drop em lote com progresso de indexação em tempo real. */
const Dropzone = ({ watchDirectory, onToast }: DropzoneProps) => {
  const [isDragging, setIsDragging] = useState(false);
  const [files, setFiles] = useState<DropzoneFile[]>([]);
  const dragCounter = useRef(0);

  const applyWatcherEvent = useCallback(
    (event: WatcherIngestionEvent) => {
      const name = event.source_path.split(/[/\\]/).pop() ?? event.source_path;
      const status: DropzoneFile['status'] = event.status === 'success' ? 'indexed' : 'failed';
      setFiles((prev) => {
        const next = prev.filter((file) => file.name !== name);
        return [{ id: event.ingestion_id, name, status, message: event.message }, ...next];
      });
      onToast?.({
        id: event.ingestion_id,
        status: event.status,
        message:
          event.status === 'success'
            ? `${name} indexado com sucesso.`
            : `Falha ao indexar ${name}: ${event.message ?? 'erro desconhecido'}`,
      });
    },
    [onToast]
  );

  useEffect(() => {
    if (!watchDirectory) return undefined;
    const interval = window.setInterval(() => {
      void bridge.pollWatcherEvents().then((events) => {
        events.forEach((event) => applyWatcherEvent(event));
      });
    }, POLL_INTERVAL_MS);
    return () => window.clearInterval(interval);
  }, [watchDirectory, applyWatcherEvent]);

  const markFailed = useCallback((names: string[], message: string) => {
    setFiles((prev) =>
      prev.map((file) =>
        file.status === 'indexing' && names.includes(file.name) ? { ...file, status: 'failed', message } : file
      )
    );
  }, []);

  const requestIndexing = useCallback(
    async (names: string[]): Promise<void> => {
      let pending = names;
      for (let attempt = 0; ; attempt += 1) {
        try {
          ({ missing: pending } = await bridge.indexDroppedFiles(pending));
        } catch (error) {
          markFailed(pending, error instanceof Error ? error.message : 'Falha ao pedir a indexação.');
          return;
        }
        if (pending.length === 0) return;
        if (attempt === ENQUEUE_RETRIES) break;
        await new Promise((resolve) => window.setTimeout(resolve, ENQUEUE_RETRY_MS));
      }
      markFailed(pending, NO_PATH_MESSAGE);
    },
    [markFailed]
  );

  const applyDropEvent = useCallback(
    (event: DroppedFileEvent) => {
      setFiles((prev) => {
        const index = prev.findIndex((file) => file.status === 'indexing' && file.name === event.name);
        if (index < 0) return prev;
        const next = [...prev];
        next[index] = { ...next[index], status: event.status, message: event.message };
        return next;
      });
      onToast?.(dropToast(event));
    },
    [onToast]
  );

  const isIndexing = files.some((file) => file.status === 'indexing');

  useEffect(() => {
    if (!isIndexing) return undefined;
    const interval = window.setInterval(() => {
      void bridge.pollDroppedFiles().then((events) => events.forEach((event) => applyDropEvent(event)));
    }, POLL_INTERVAL_MS);
    return () => window.clearInterval(interval);
  }, [isIndexing, applyDropEvent]);

  const addDroppedFiles = useCallback(
    (fileList: FileList) => {
      const accepted = Array.from(fileList).filter((file) => isAccepted(file.name));
      if (accepted.length === 0) return;
      setFiles((prev) => [
        ...accepted.map((file) => ({
          id: `${file.name}-${file.size}-${Date.now()}`,
          name: file.name,
          status: 'indexing' as const,
          message: null,
        })),
        ...prev,
      ]);
      void requestIndexing(accepted.map((file) => file.name));
    },
    [requestIndexing]
  );

  const handleDragEnter = (event: DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    dragCounter.current += 1;
    setIsDragging(true);
  };

  const handleDragLeave = (event: DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    dragCounter.current -= 1;
    if (dragCounter.current <= 0) {
      dragCounter.current = 0;
      setIsDragging(false);
    }
  };

  const handleDragOver = (event: DragEvent<HTMLDivElement>) => {
    event.preventDefault();
  };

  const handleDrop = (event: DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    dragCounter.current = 0;
    setIsDragging(false);
    addDroppedFiles(event.dataTransfer.files);
  };

  const removeFile = (id: string) => {
    setFiles((prev) => prev.filter((file) => file.id !== id));
  };

  return (
    <div
      className={`dropzone${isDragging ? ' dropzone--active' : ''}`}
      onDragEnter={handleDragEnter}
      onDragLeave={handleDragLeave}
      onDragOver={handleDragOver}
      onDrop={handleDrop}
      role="region"
      aria-label="Área de arrastar e soltar arquivos"
    >
      <div className="dropzone__head">
        <FileIcon size={18} className="dropzone__icon" />
        <p className="dropzone__hint">
          <b>Arraste áudios, PDFs ou textos aqui para indexar</b>
          <span>Cada arquivo entra no corpus sem ser copiado nem alterado.</span>
        </p>
      </div>

      {files.length > 0 && (
        <ul className="dropzone__list" aria-label="Arquivos soltos">
          {files.map((file) => (
            <li key={file.id} className={`dropzone__item dropzone__item--${file.status}`}>
              <FileIcon />
              <span className="dropzone__item-name" title={file.message ?? undefined}>{file.name}</span>
              <span className={`pill${STATUS_LABEL[file.status].tone}`}>{STATUS_LABEL[file.status].label}</span>
              <button
                type="button"
                className="btn-icon dropzone__item-remove"
                onClick={() => removeFile(file.id)}
                aria-label={`Remover ${file.name}`}
              >
                <XIcon />
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
};

export default Dropzone;
