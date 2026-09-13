import { useCallback, useEffect, useRef, useState, type DragEvent } from 'react';
import { bridge, type WatcherIngestionEvent } from '../services/bridge';
import { FileIcon, XIcon } from './Icons';

/** Extensões de arquivo aceitas pela dropzone (áudio, PDF, texto). */
const ACCEPTED_EXTENSIONS = ['.wav', '.mp3', '.m4a', '.ogg', '.pdf', '.txt', '.md'];

const isAccepted = (fileName: string) =>
  ACCEPTED_EXTENSIONS.some((ext) => fileName.toLowerCase().endsWith(ext));

interface DropzoneFile {
  id: string;
  name: string;
  status: 'pending' | 'indexed' | 'failed';
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

  const addDroppedFiles = useCallback((fileList: FileList) => {
    const accepted = Array.from(fileList).filter((file) => isAccepted(file.name));
    if (accepted.length === 0) return;
    setFiles((prev) => [
      ...accepted.map((file) => ({
        id: `${file.name}-${file.size}-${Date.now()}`,
        name: file.name,
        status: 'pending' as const,
        message: null,
      })),
      ...prev,
    ]);
  }, []);

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
      <FileIcon size={22} className="dropzone__icon" />
      <p className="dropzone__hint">
        Arraste áudios, PDFs ou TXTs aqui, ou clique para selecionar.
      </p>

      {files.length > 0 && (
        <ul className="dropzone__list" aria-label="Arquivos soltos">
          {files.map((file) => (
            <li key={file.id} className={`dropzone__item dropzone__item--${file.status}`}>
              <FileIcon />
              <span className="dropzone__item-name">{file.name}</span>
              <span className="dropzone__item-status">{file.status}</span>
              <button
                type="button"
                className="dropzone__item-remove"
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
