import {
  useEffect,
  useRef,
  useState,
  useCallback,
  type KeyboardEvent,
  type ChangeEvent,
  type RefObject,
} from 'react';
import { PaperclipIcon, MicIcon, SendIcon, FileIcon, XIcon, LoaderIcon, ChevronDownIcon, CheckIcon } from './Icons';
import { bridge, type AskStrategy, type AudioJobSnapshot, type CorpusRoot, type Vault } from '../services/bridge';
import { VaultGlyph } from './VaultGlyph';

const isAudioJobDone = (snapshot: AudioJobSnapshot) =>
  snapshot.status === 'completed' || snapshot.status === 'failed' || snapshot.status === 'cancelled';

/**
 * Traduz uma falha de transcrição em mensagem acionável. Quando o modelo de
 * voz configurado ainda não foi baixado (AUDIO_MODEL_NOT_READY), orienta o
 * usuário a ir em Configurações → Voz em vez de mostrar só o erro técnico cru.
 */
const describeAudioFailure = (errorCode: string | null, message: string | null): string => {
  const looksLikeMissingModel =
    errorCode === 'AUDIO_MODEL_NOT_READY' ||
    (message?.toLowerCase().includes('missing or corrupt') ?? false);
  if (looksLikeMissingModel) {
    return 'Modelo de transcrição não está instalado. Abra Configurações → Voz para baixá-lo.';
  }
  return message ?? 'Falha ao transcrever áudio.';
};

// Props do componente de input de chat
interface ChatInputProps {
  onSendMessage: (text: string, attachment?: File) => void;
  isLoading?: boolean;
  strategy?: AskStrategy;
  onStrategyChange?: (strategy: AskStrategy) => void;
  /** Pastas indexadas; o seletor de pasta só aparece com duas ou mais. */
  corpusRoots?: CorpusRoot[];
  /** Caminho da pasta escolhida, ou null para "Todas as pastas". */
  sourceRoot?: string | null;
  onSourceRootChange?: (root: string | null) => void;
  /** Vault que vai responder: aparece no placeholder, na dica e num chip que abre o seletor de vault. */
  vault?: Vault | null;
  onOpenVaultMenu?: () => void;
}

const STRATEGIES: { value: AskStrategy; label: string; hint: string }[] = [
  { value: 'hybrid', label: 'Híbrida', hint: 'Palavra-chave e significado combinados.' },
  { value: 'vector', label: 'Vetorial', hint: 'Por significado, mesmo sem as palavras exatas.' },
  { value: 'lexical', label: 'Lexical', hint: 'Só palavras exatas (FTS5). A mais rápida.' },
];

/** Fecha um menu flutuante ao clicar fora dele ou apertar Esc. */
const useDismissOnOutside = (open: boolean, wrapRef: RefObject<HTMLDivElement | null>, close: () => void) => {
  useEffect(() => {
    if (!open) return undefined;
    const onDown = (event: MouseEvent) => {
      if (!wrapRef.current?.contains(event.target as Node)) close();
    };
    const onKey = (event: globalThis.KeyboardEvent) => {
      if (event.key === 'Escape') close();
    };
    document.addEventListener('mousedown', onDown);
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('mousedown', onDown);
      document.removeEventListener('keydown', onKey);
    };
  }, [open, wrapRef, close]);
};

const StrategyPicker = ({ value, onChange }: { value: AskStrategy; onChange: (s: AskStrategy) => void }) => {
  const [open, setOpen] = useState(false);
  const wrapRef = useRef<HTMLDivElement>(null);
  useDismissOnOutside(open, wrapRef, () => setOpen(false));

  const current = STRATEGIES.find((s) => s.value === value) ?? STRATEGIES[0];
  return (
    <div className="strategy" ref={wrapRef}>
      <button
        type="button"
        className="strategy__chip"
        aria-haspopup="menu"
        aria-expanded={open}
        aria-label={`Estratégia de busca: ${current.label}`}
        onClick={() => setOpen((prev) => !prev)}
      >
        {current.label}
        <ChevronDownIcon size={13} />
      </button>
      {open && (
        <div className="strategy__menu" role="menu" aria-label="Estratégia de busca">
          {STRATEGIES.map((option) => (
            <button
              key={option.value}
              type="button"
              role="menuitemradio"
              aria-checked={option.value === value}
              className="strategy__item"
              onClick={() => {
                onChange(option.value);
                setOpen(false);
              }}
            >
              <CheckIcon size={15} />
              <span>
                {option.label}
                <small>{option.hint}</small>
              </span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
};

const folderName = (path: string): string => path.split(/[\\/]/).filter(Boolean).pop() ?? path;

// Mesmo padrão visual do StrategyPicker: escolhe a pasta de origem da pergunta (ou todas).
const SourcePicker = ({
  roots,
  value,
  onChange,
}: {
  roots: CorpusRoot[];
  value: string | null;
  onChange: (root: string | null) => void;
}) => {
  const [open, setOpen] = useState(false);
  const wrapRef = useRef<HTMLDivElement>(null);
  useDismissOnOutside(open, wrapRef, () => setOpen(false));

  const current = roots.find((root) => root.root === value);
  const currentLabel = current ? folderName(current.root) : 'Todas as pastas';
  return (
    <div className="strategy" ref={wrapRef}>
      <button
        type="button"
        className="strategy__chip"
        aria-haspopup="menu"
        aria-expanded={open}
        aria-label={`Pasta de origem: ${currentLabel}`}
        title={current?.root ?? 'Perguntar em todas as pastas indexadas'}
        onClick={() => setOpen((prev) => !prev)}
      >
        Pasta: {currentLabel}
        <ChevronDownIcon size={13} />
      </button>
      {open && (
        <div className="strategy__menu" role="menu" aria-label="Pasta de origem">
          <button
            type="button"
            role="menuitemradio"
            aria-checked={value === null}
            className="strategy__item"
            onClick={() => {
              onChange(null);
              setOpen(false);
            }}
          >
            <CheckIcon size={15} />
            <span>
              Todas as pastas
              <small>Busca em todo o corpus indexado.</small>
            </span>
          </button>
          {roots.map((root) => (
            <button
              key={root.root}
              type="button"
              role="menuitemradio"
              aria-checked={root.root === value}
              className="strategy__item"
              title={root.root}
              onClick={() => {
                onChange(root.root);
                setOpen(false);
              }}
            >
              <CheckIcon size={15} />
              <span>
                {folderName(root.root)}
                <small>{root.notes_count} notas</small>
              </span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
};

const ChatInput = ({
  onSendMessage,
  isLoading = false,
  strategy,
  onStrategyChange,
  corpusRoots = [],
  sourceRoot = null,
  onSourceRootChange,
  vault = null,
  onOpenVaultMenu,
}: ChatInputProps) => {
  const [text, setText] = useState('');
  const [attachment, setAttachment] = useState<File | null>(null);
  const [micStatus, setMicStatus] = useState<'idle' | 'recording' | 'processing'>('idle');
  const [micError, setMicError] = useState('');
  const [recordingSeconds, setRecordingSeconds] = useState(0);

  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const audioJobIdRef = useRef<string | null>(null);
  const pollIntervalRef = useRef<number | null>(null);
  const recordingIntervalRef = useRef<number | null>(null);

  // Contador de tempo decorrido, visível ao lado do mic enquanto grava
  useEffect(() => {
    if (micStatus !== 'recording') {
      if (recordingIntervalRef.current !== null) {
        window.clearInterval(recordingIntervalRef.current);
        recordingIntervalRef.current = null;
      }
      return undefined;
    }
    recordingIntervalRef.current = window.setInterval(() => {
      setRecordingSeconds((seconds) => seconds + 1);
    }, 1000);
    return () => {
      if (recordingIntervalRef.current !== null) {
        window.clearInterval(recordingIntervalRef.current);
        recordingIntervalRef.current = null;
      }
    };
  }, [micStatus]);

  const stopPolling = useCallback(() => {
    if (pollIntervalRef.current !== null) {
      window.clearInterval(pollIntervalRef.current);
      pollIntervalRef.current = null;
    }
  }, []);

  // Garante que nenhum polling fica orfao se o componente desmontar em gravacao
  useEffect(() => stopPolling, [stopPolling]);

  const finishAudioJob = useCallback((snapshot: AudioJobSnapshot) => {
    stopPolling();
    audioJobIdRef.current = null;
    setMicStatus('idle');
    if (snapshot.status === 'completed' && snapshot.result?.text) {
      setText((prev) => (prev.trim() ? `${prev.trim()} ${snapshot.result!.text}` : snapshot.result!.text));
      setMicError('');
    } else if (snapshot.status === 'completed') {
      setMicError('Nenhuma fala detectada no áudio. Confira o microfone em Configurações → Voz.');
    } else if (snapshot.status === 'failed') {
      setMicError(describeAudioFailure(snapshot.error_code, snapshot.message));
    }
  }, [stopPolling]);

  // Ajusta a altura do textarea automaticamente conforme o conteúdo cresce
  const adjustTextareaHeight = useCallback(() => {
    const textarea = textareaRef.current;
    if (!textarea) return;
    textarea.style.height = 'auto';
    textarea.style.height = `${Math.min(textarea.scrollHeight, 200)}px`;
  }, []);

  // Atualiza texto e ajusta altura
  const handleTextChange = (e: ChangeEvent<HTMLTextAreaElement>) => {
    setText(e.target.value);
    adjustTextareaHeight();
  };

  // Envia mensagem ao pressionar Enter (sem Shift)
  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  // Lógica de envio da mensagem
  const handleSend = () => {
    const trimmed = text.trim();
    if (!trimmed && !attachment) return;
    if (isLoading) return;

    onSendMessage(trimmed, attachment ?? undefined);
    setText('');
    setAttachment(null);

    // Reseta altura do textarea
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
    }
  };

  // Abre diálogo de seleção de arquivo
  const handleAttachClick = () => {
    fileInputRef.current?.click();
  };

  // Armazena arquivo selecionado
  const handleFileChange = (e: ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) setAttachment(file);
    // Limpa o input para permitir selecionar o mesmo arquivo novamente
    e.target.value = '';
  };

  // Remove o arquivo anexado
  const handleRemoveAttachment = () => {
    setAttachment(null);
  };

  // Inicia gravação do microfone padrão do sistema via backend Python
  const handleStartRecording = async () => {
    setMicError('');
    try {
      const job = await bridge.startAudioCapture();
      audioJobIdRef.current = job.job_id;
      setRecordingSeconds(0);
      setMicStatus('recording');
    } catch (error) {
      setMicError(error instanceof Error ? error.message : 'Não foi possível acessar o microfone.');
    }
  };

  // Encerra a gravação e aguarda a transcrição local terminar
  const handleStopRecording = async () => {
    const jobId = audioJobIdRef.current;
    if (!jobId) return;
    setMicStatus('processing');
    try {
      const stopped = await bridge.stopAudioCapture(jobId);
      if (isAudioJobDone(stopped)) {
        finishAudioJob(stopped);
        return;
      }
      pollIntervalRef.current = window.setInterval(async () => {
        try {
          const snapshot = await bridge.getAudioCapture(jobId);
          if (isAudioJobDone(snapshot)) finishAudioJob(snapshot);
        } catch (error) {
          finishAudioJob({
            job_id: jobId,
            status: 'failed',
            source_path: '',
            samples_captured: 0,
            error_code: null,
            message: error instanceof Error ? error.message : 'Falha ao consultar transcrição.',
            result: null,
          });
        }
      }, 800);
    } catch (error) {
      finishAudioJob({
        job_id: jobId,
        status: 'failed',
        source_path: '',
        samples_captured: 0,
        error_code: null,
        message: error instanceof Error ? error.message : 'Falha ao encerrar gravação.',
        result: null,
      });
    }
  };

  const handleMicToggle = () => {
    if (micStatus === 'idle') void handleStartRecording();
    else if (micStatus === 'recording') void handleStopRecording();
  };

  const formatRecordingTime = (totalSeconds: number) =>
    `${Math.floor(totalSeconds / 60)}:${String(totalSeconds % 60).padStart(2, '0')}`;

  const canSend = (text.trim().length > 0 || attachment !== null) && !isLoading;

  return (
    <section className="input-area" aria-label="Área de entrada de mensagem">
      <div
        className={`composer${micStatus !== 'idle' ? ' composer--recording' : ''}`}
        role="form"
        aria-label="Formulário de chat"
      >
        {/* Input oculto para seleção de arquivo */}
        <input
          ref={fileInputRef}
          id="file-input"
          type="file"
          aria-label="Selecionar arquivo para anexar"
          style={{ display: 'none' }}
          onChange={handleFileChange}
          accept="*/*"
        />

        {/* Preview do arquivo anexado */}
        {attachment && (
          <div className="attachment-preview" aria-label={`Arquivo anexado: ${attachment.name}`}>
            <div className="attachment-preview__icon" aria-hidden="true">
              <FileIcon size={14} />
            </div>
            <span className="attachment-preview__name" title={attachment.name}>
              {attachment.name}
            </span>
            <button
              type="button"
              className="attachment-preview__remove"
              aria-label="Remover arquivo anexado"
              onClick={handleRemoveAttachment}
            >
              <XIcon size={12} />
            </button>
          </div>
        )}

        <textarea
          ref={textareaRef}
          id="chat-textarea"
          className="chat-input"
          placeholder={vault ? `Pergunte à vault ${vault.name}…` : 'Pergunte ao seu vault…'}
          value={text}
          onChange={handleTextChange}
          onKeyDown={handleKeyDown}
          rows={2}
          aria-label="Campo de mensagem"
          aria-multiline="true"
          disabled={isLoading}
        />

        <div className="composer__row">
          <button
            id="btn-attach"
            type="button"
            className="composer__icon"
            aria-label="Anexar arquivo"
            title="Anexar arquivo"
            onClick={handleAttachClick}
            disabled={isLoading}
          >
            <PaperclipIcon size={17} />
          </button>

          {vault && onOpenVaultMenu && (
            <button
              type="button"
              className="strategy__chip composer__vault"
              aria-label={`Vault da pergunta: ${vault.name}. Trocar vault`}
              onClick={onOpenVaultMenu}
            >
              <VaultGlyph icon={vault.icon} color={vault.color} size={11} />
              <span className="composer__vault-name">{vault.name}</span>
              <ChevronDownIcon size={13} />
            </button>
          )}
          {strategy && onStrategyChange && <StrategyPicker value={strategy} onChange={onStrategyChange} />}
          {onSourceRootChange && corpusRoots.length >= 2 && (
            <SourcePicker roots={corpusRoots} value={sourceRoot} onChange={onSourceRootChange} />
          )}

          <span className="composer__grow" />

          {micStatus === 'recording' && (
            <span className="recording-timer mono" aria-hidden="true">
              <span className="recording-timer__dot" />
              {formatRecordingTime(recordingSeconds)}
            </span>
          )}

          <button
            id="btn-mic"
            type="button"
            className={`composer__icon btn-mic${micStatus === 'recording' ? ' btn-mic--recording' : ''}${micStatus === 'processing' ? ' btn-mic--processing' : ''}`}
            aria-label={micStatus === 'recording' ? 'Parar gravação' : 'Gravar áudio'}
            title={micStatus === 'recording' ? 'Parar gravação' : 'Gravar áudio'}
            onClick={handleMicToggle}
            disabled={isLoading || micStatus === 'processing'}
            aria-pressed={micStatus === 'recording'}
          >
            {micStatus === 'processing' ? <LoaderIcon size={17} className="spin" /> : <MicIcon size={17} />}
          </button>

          <button
            id="btn-send"
            type="button"
            className="btn-send"
            aria-label="Enviar mensagem"
            title="Enviar (Enter)"
            onClick={handleSend}
            disabled={!canSend}
          >
            <SendIcon size={15} />
          </button>
        </div>
      </div>

      {/* Rodapé: status da gravação tem prioridade sobre o aviso padrão */}
      <p
        className={`input-footer${
          micStatus === 'recording' ? ' input-footer--recording' :
          micStatus === 'processing' ? ' input-footer--processing' :
          micError ? ' input-footer--error' : ''
        }`}
        aria-live="polite"
      >
        {micStatus === 'recording' && 'Gravando… clique no microfone para parar.'}
        {micStatus === 'processing' && 'Transcrevendo áudio localmente…'}
        {micStatus === 'idle' &&
          (micError ||
            `Respostas usam só o que está indexado ${vault ? `em ${vault.name}` : 'no vault'}. Enter envia, Shift+Enter quebra a linha.`)}
      </p>
    </section>
  );
};

export default ChatInput;
