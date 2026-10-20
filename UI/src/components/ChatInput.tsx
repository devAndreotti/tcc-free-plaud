import {
  useEffect,
  useRef,
  useState,
  useCallback,
  type KeyboardEvent,
  type ChangeEvent,
} from 'react';
import { MicIcon, SendIcon, LoaderIcon, ChevronDownIcon, CheckIcon } from './Icons';
import { bridge, type AudioJobSnapshot, type BackendSettings, type CorpusRoot, type Vault } from '../services/bridge';
import { VaultGlyph } from './VaultGlyph';
import { vaultMeta } from '../lib/vaultVisuals';
import { useDismissOnOutside } from '../hooks/useDismissOnOutside';
import { AnswerPicker } from './AnswerPicker';

const isAudioJobDone = (snapshot: AudioJobSnapshot) =>
  snapshot.status === 'completed' || snapshot.status === 'failed' || snapshot.status === 'cancelled';

// Cancela a captura no backend: a gravação para e o áudio não vai à transcrição.
const discardCapture = async (jobId: string) => {
  try {
    await bridge.cancelAudioCapture(jobId);
  } catch (error) {
    console.error('[ChatInput] Não foi possível cancelar a gravação:', error);
  }
};

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

const HINT_EXTRACTIVE = 'Mostra as frases dos seus trechos. Nenhum modelo é chamado.';
const HINT_AI = 'A IA escreve a resposta a partir dos trechos e marca as fontes. Se ela não responder com texto, você vê o trecho original.';

// Props do componente de input de chat
interface ChatInputProps {
  onSendMessage: (text: string) => void;
  /** Campo de mensagem ganhou foco (a tela aquece o modelo de resposta). */
  onFocus?: () => void;
  isLoading?: boolean;
  /** Provedor e modelo de resposta salvos; com onAnswerSaved, a barra mostra o seletor de resposta. */
  answerProvider?: string;
  answerModel?: string | null;
  onAnswerSaved?: (settings: BackendSettings) => void;
  /** Pastas indexadas; o seletor de pasta só aparece com duas ou mais. */
  corpusRoots?: CorpusRoot[];
  /** Caminho da pasta escolhida, ou null para "Todas as pastas". */
  sourceRoot?: string | null;
  onSourceRootChange?: (root: string | null) => void;
  /** Vault que vai responder: aparece no placeholder, na dica e num chip com o seletor de vault. */
  vault?: Vault | null;
  vaults?: Vault[];
  onVaultChange?: (vaultId: string) => void;
}

const folderName = (path: string): string => path.split(/[\\/]/).filter(Boolean).pop() ?? path;

// Troca a vault da pergunta num menu ancorado no próprio chip.
const VaultPicker = ({
  vaults,
  value,
  onChange,
}: {
  vaults: Vault[];
  value: Vault;
  onChange: (vaultId: string) => void;
}) => {
  const [open, setOpen] = useState(false);
  const wrapRef = useRef<HTMLDivElement>(null);
  useDismissOnOutside(open, wrapRef, () => setOpen(false));

  return (
    <div className="strategy" ref={wrapRef}>
      <button
        type="button"
        className="strategy__chip composer__vault"
        aria-haspopup="menu"
        aria-expanded={open}
        aria-label={`Vault da pergunta: ${value.name}. Trocar vault`}
        onClick={() => setOpen((prev) => !prev)}
      >
        <VaultGlyph icon={value.icon} color={value.color} size={11} />
        <span className="composer__vault-name">{value.name}</span>
        <ChevronDownIcon size={13} />
      </button>
      {open && (
        <div className="strategy__menu" role="menu" aria-label="Vault da pergunta">
          {vaults.map((vault) => (
            <button
              key={vault.id}
              type="button"
              role="menuitemradio"
              aria-checked={vault.id === value.id}
              className="strategy__item"
              onClick={() => {
                setOpen(false);
                if (vault.id !== value.id) onChange(vault.id);
              }}
            >
              <CheckIcon size={15} />
              <span className="strategy__vault">
                <VaultGlyph icon={vault.icon} color={vault.color} size={13} />
                <span>
                  {vault.name}
                  <small className="mono">{vaultMeta(vault)}</small>
                </span>
              </span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
};

// Escolhe a pasta de origem da pergunta (ou todas), no mesmo estilo dos outros seletores da barra.
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
  onFocus,
  isLoading = false,
  answerProvider,
  answerModel = null,
  onAnswerSaved,
  corpusRoots = [],
  sourceRoot = null,
  onSourceRootChange,
  vault = null,
  vaults = [],
  onVaultChange,
}: ChatInputProps) => {
  const [text, setText] = useState('');
  const [micStatus, setMicStatus] = useState<'idle' | 'recording' | 'processing'>('idle');
  const [micError, setMicError] = useState('');
  const [recordingSeconds, setRecordingSeconds] = useState(0);

  const textareaRef = useRef<HTMLTextAreaElement>(null);
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

  // Sair do chat no meio de uma gravação: para o polling e cancela a captura em andamento.
  const unmountedRef = useRef(false);
  useEffect(() => {
    unmountedRef.current = false;
    return () => {
      unmountedRef.current = true;
      stopPolling();
      if (audioJobIdRef.current) void discardCapture(audioJobIdRef.current);
    };
  }, [stopPolling]);

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
    if (!trimmed) return;
    if (isLoading) return;

    onSendMessage(trimmed);
    setText('');

    // Reseta altura do textarea
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
    }
  };

  // Inicia gravação do microfone padrão do sistema via backend Python
  const handleStartRecording = async () => {
    setMicError('');
    try {
      const job = await bridge.startAudioCapture();
      // Saiu do chat enquanto a captura abria: cancela, para o microfone não ficar ligado sem tela.
      if (unmountedRef.current) {
        void discardCapture(job.job_id);
        return;
      }
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

  const canSend = text.trim().length > 0 && !isLoading;

  return (
    <section className="input-area" aria-label="Área de entrada de mensagem">
      <div
        className={`composer${micStatus !== 'idle' ? ' composer--recording' : ''}`}
        role="form"
        aria-label="Formulário de chat"
      >
        <textarea
          ref={textareaRef}
          id="chat-textarea"
          className="chat-input"
          placeholder={vault ? `Pergunte à vault ${vault.name}…` : 'Pergunte ao seu vault…'}
          value={text}
          onChange={handleTextChange}
          onKeyDown={handleKeyDown}
          onFocus={onFocus}
          rows={2}
          autoComplete="off"
          aria-label="Campo de mensagem"
          aria-multiline="true"
          disabled={isLoading}
        />

        <div className="composer__row">
          {vault && onVaultChange && <VaultPicker vaults={vaults.length ? vaults : [vault]} value={vault} onChange={onVaultChange} />}
          {answerProvider && onAnswerSaved && <AnswerPicker provider={answerProvider} model={answerModel} onSaved={onAnswerSaved} />}
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
          (micError || (answerProvider && answerProvider !== 'extractive' ? HINT_AI : HINT_EXTRACTIVE))}
      </p>
    </section>
  );
};

export default ChatInput;
