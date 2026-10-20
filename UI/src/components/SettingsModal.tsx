import { Fragment, useEffect, useMemo, useRef, useState, type ComponentType } from 'react';
import { readThemeChoice, saveThemeChoice, type ThemeChoice } from '../theme';
import { createPortal } from 'react-dom';
import {
  AlertTriangleIcon,
  CheckCircleIcon,
  CodeIcon,
  ContrastIcon,
  DownloadIcon,
  MicIcon,
  RefreshIcon,
  SlidersIcon,
  StarsIcon,
  VaultIcon,
  XCircleIcon,
  XIcon,
} from './Icons';
import MomentumRail from './MomentumRail';
import Select from './Select';
import VaultsTab from './VaultsTab';
import { VaultGlyph } from './VaultGlyph';
import { useVaults } from '../hooks/useVaults';
import { checkLabel, groupChecks } from '../lib/doctorChecks';
import {
  bridge,
  type BackendSettings,
  type ModelDiscoveryResult,
  type SettingOption,
  type SettingRow,
  type VoiceModelDownloadSnapshot,
  type VoiceModelInfo,
} from '../services/bridge';

// Props do modal de configurações
interface SettingsModalProps {
  isOpen: boolean;
  onClose: () => void;
  /** Seção aberta ao abrir o modal (ex.: vinda do flyout da sidebar). */
  initialTab?: SettingsTab;
  /** Fecha o modal e abre a tela Fila (a indexação mora lá). */
  onOpenQueue?: () => void;
}

// Chaves do catálogo que pertencem à aba IA (o resto de layer não-secreto vai para Avançado)
const IA_CATALOG_KEYS = ['answer_provider', 'answer_model', 'answer_base_url'];

// Chaves que o desktop não mostra nem grava: o embedding em uso é o da vault ativa (config.py, _apply_active_vault).
const DESKTOP_HIDDEN_KEYS = ['embedding_model'];

const MODEL_STATUS: Record<string, string> = { offline: 'offline', unauthorized: 'sem autorização', error: 'erro' };

// URL que o backend usa com o campo vazio (providers/answer.py::_default_base_url).
const PROVIDER_DEFAULT_URL: Record<string, string> = {
  ollama: 'http://localhost:11434/v1',
  lmstudio: 'http://localhost:1234/v1',
  'openai-compatible': 'https://api.openai.com/v1',
};
const PROVIDER_LABEL: Record<string, string> = { ollama: 'Ollama', lmstudio: 'LM Studio', 'openai-compatible': 'provedor' };
// IA local: os modelos instalados aparecem sozinhos ao abrir a aba (remoto só lista no botão).
const LOCAL_PROVIDERS = new Set(['ollama', 'lmstudio']);

// "3.1B · Q4_K_M · 2,3 GB" com o que o Ollama informa; o LM Studio não manda esses dados.
const modelDescription = (details: Record<string, unknown>) => {
  const size = typeof details.size === 'number'
    ? `${(details.size / 1e9).toLocaleString('pt-BR', { maximumFractionDigits: 1 })} GB`
    : null;
  return [details.parameter_size, details.quantization_level, size].filter(Boolean).join(' · ') || undefined;
};

export type SettingsTab = 'geral' | 'vaults' | 'ia' | 'voz' | 'avancado' | 'aparencia';

const SETTINGS_TABS: { id: SettingsTab; label: string }[] = [
  { id: 'geral', label: 'Geral' },
  { id: 'vaults', label: 'Vaults' },
  { id: 'ia', label: 'IA' },
  { id: 'voz', label: 'Voz' },
  { id: 'avancado', label: 'Avançado' },
  { id: 'aparencia', label: 'Aparência' },
];

// Avançado fica escondido: "Desbloquear avançado" libera a aba depois de alguns cliques, e a liberação fica gravada.
const ADVANCED_UNLOCK_CLICKS = 5;
const ADVANCED_UNLOCK_KEY = 'escolio.avancadoLiberado';

function readAdvancedUnlocked(): boolean {
  try {
    return window.localStorage.getItem(ADVANCED_UNLOCK_KEY) === '1';
  } catch {
    return false;
  }
}

function saveAdvancedUnlocked(): void {
  try {
    window.localStorage.setItem(ADVANCED_UNLOCK_KEY, '1');
  } catch {
    // Sem storage (modo privado): a liberação vale só até fechar o app.
  }
}

const TAB_ICONS: Record<SettingsTab, ComponentType<{ size?: number }>> = {
  geral: SlidersIcon,
  vaults: VaultIcon,
  ia: StarsIcon,
  voz: MicIcon,
  avancado: CodeIcon,
  aparencia: ContrastIcon,
};

const SPEED_LEVEL: Record<string, number> = { rapido: 3, medio: 2, lento: 1 };
const QUALITY_LEVEL: Record<string, number> = { basica: 1, boa: 2, alta: 3 };

const Meter = ({ level, label }: { level: number; label: string }) => (
  <span className="meter" role="img" aria-label={`${label}: ${level} de 3`}>
    {[1, 2, 3].map((i) => (
      <i key={i} className={i <= level ? 'meter__on' : undefined} />
    ))}
  </span>
);

// Aviso flutuante: sucesso some sozinho; erro fica até fechar.
type Toast = { tone: 'ok' | 'error'; text: string };

const draftsFrom = (settings: BackendSettings) =>
  Object.fromEntries(
    settings.settings_catalog
      .filter((row) => !row.secret)
      .map((row) => [row.key, row.value === null ? '' : String(row.value)])
  );

const SettingsModal = ({ isOpen, onClose, initialTab, onOpenQueue }: SettingsModalProps) => {
  const modalRef = useRef<HTMLDivElement>(null);
  const [apiKey, setApiKey] = useState('');
  const [backendSettings, setBackendSettings] = useState<BackendSettings | null>(null);
  const [settingDrafts, setSettingDrafts] = useState<Record<string, string>>({});
  const [isSavingApiKey, setIsSavingApiKey] = useState(false);
  const [isConfirmingKeyRemoval, setIsConfirmingKeyRemoval] = useState(false);
  const [isSavingBackendSettings, setIsSavingBackendSettings] = useState(false);
  const [applyingPreset, setApplyingPreset] = useState('');
  const [isTestingProvider, setIsTestingProvider] = useState(false);
  const [isListingModels, setIsListingModels] = useState(false);
  const [modelDiscovery, setModelDiscovery] = useState<ModelDiscoveryResult | null>(null);
  const [activeTab, setActiveTab] = useState<SettingsTab>('voz');
  const [toast, setToast] = useState<Toast | null>(null);
  const [voiceModels, setVoiceModels] = useState<VoiceModelInfo[]>([]);
  const [downloadJob, setDownloadJob] = useState<VoiceModelDownloadSnapshot | null>(null);
  const [downloadError, setDownloadError] = useState('');
  const [theme, setTheme] = useState<ThemeChoice>(readThemeChoice);
  const [advancedUnlocked, setAdvancedUnlocked] = useState(readAdvancedUnlocked);
  const [advancedClicks, setAdvancedClicks] = useState(0);
  // Sem a aba liberada, "Avançado" não aparece e nunca é o painel exibido.
  const currentTab: SettingsTab = activeTab === 'avancado' && !advancedUnlocked ? 'geral' : activeTab;

  const handleAdvancedUnlockClick = () => {
    if (advancedClicks + 1 < ADVANCED_UNLOCK_CLICKS) {
      setAdvancedClicks(advancedClicks + 1);
      return;
    }
    saveAdvancedUnlocked();
    setAdvancedUnlocked(true);
    setAdvancedClicks(0);
  };
  const { active } = useVaults();

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- abre na aba pedida por quem chamou o modal.
    if (isOpen && initialTab) setActiveTab(initialTab);
  }, [isOpen, initialTab]);


  // Fecha o modal ao pressionar Escape
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    if (isOpen) document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, onClose]);

  // Foca o modal quando abre (acessibilidade)
  useEffect(() => {
    if (isOpen) modalRef.current?.focus();
  }, [isOpen]);

  const [isRunningDoctor, setIsRunningDoctor] = useState(false);

  useEffect(() => {
    if (toast?.tone !== 'ok') return undefined;
    const timer = window.setTimeout(() => setToast(null), 3500);
    return () => window.clearTimeout(timer);
  }, [toast]);

  useEffect(() => {
    if (!isOpen) return;
    bridge.getBackendSettings()
      .then((settings) => {
        setBackendSettings(settings);
        setSettingDrafts(draftsFrom(settings));
        setIsConfirmingKeyRemoval(false);
      })
      .catch((error) => {
        console.error('[SettingsModal] Erro ao carregar settings do backend:', error);
      });
  }, [isOpen]);

  // Roda o Doctor de novo sem descartar o que o usuário já editou.
  const handleRerunDoctor = async () => {
    setIsRunningDoctor(true);
    try {
      const settings = await bridge.getBackendSettings();
      setBackendSettings((prev) => (prev ? { ...prev, doctor: settings.doctor, notes_count: settings.notes_count, sqlite_chunks_count: settings.sqlite_chunks_count } : settings));
    } catch (error) {
      setToast({ tone: 'error', text: error instanceof Error ? error.message : 'Falha ao rodar o diagnóstico.' });
    } finally {
      setIsRunningDoctor(false);
    }
  };

  // Provedor e URL que estão na tela (ainda não salvos): Testar e Listar usam estes.
  const draftProvider = settingDrafts.answer_provider || backendSettings?.answer_provider || 'extractive';
  const draftBaseUrl = settingDrafts.answer_base_url ?? '';

  // IA local: lista os modelos instalados ao abrir a aba e ao trocar provedor ou URL.
  useEffect(() => {
    if (!isOpen || activeTab !== 'ia' || !LOCAL_PROVIDERS.has(draftProvider)) return undefined;
    let cancelled = false;
    const timer = window.setTimeout(() => {
      bridge.listAnswerModels({ provider: draftProvider, baseUrl: draftBaseUrl })
        .then((result) => {
          if (!cancelled) setModelDiscovery(result);
        })
        .catch((error) => console.error('[SettingsModal] Erro ao listar modelos:', error));
    }, 300);
    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [isOpen, activeTab, draftProvider, draftBaseUrl]);

  const pendingChanges = useMemo(() => {
    if (!backendSettings) return 0;
    const saved = draftsFrom(backendSettings);
    return Object.keys(saved).filter((key) => (settingDrafts[key] ?? '') !== saved[key]).length;
  }, [backendSettings, settingDrafts]);

  // Carrega o catálogo de modelos de voz (com estado instalado) quando o modal abre.
  useEffect(() => {
    if (!isOpen) return;
    bridge.listVoiceModels()
      .then(setVoiceModels)
      .catch((error) => {
        console.error('[SettingsModal] Erro ao listar modelos de voz:', error);
      });
  }, [isOpen]);

  const selectableVoiceModels = voiceModels.filter((model) => model.selectable);
  const selectedVoiceModel = selectableVoiceModels.find((model) => model.id === settingDrafts.audio_model) ?? null;
  const vadModel = voiceModels.find((model) => model.id === 'silero-vad') ?? null;

  const selectVoiceModel = (value: string) => {
    const nextModel = selectableVoiceModels.find((model) => model.id === value);
    setSettingDrafts((prev) => {
      const next: Record<string, string> = { ...prev, audio_model: value };
      // Se o idioma atual do draft nao existe mais no novo
      // modelo (nem "auto"), corrige para o primeiro idioma
      // valido - so no draft, salvar continua manual.
      const currentLanguage = prev.audio_language;
      const stillValid = nextModel
        ? currentLanguage === 'auto'
          ? nextModel.supports_auto_language
          : nextModel.languages.includes(currentLanguage)
        : true;
      if (nextModel && !stillValid) {
        next.audio_language = nextModel.supports_auto_language
          ? 'auto'
          : (nextModel.languages[0] ?? currentLanguage);
      }
      return next;
    });
    setDownloadJob(null);
    setDownloadError('');
  };

  // Faz polling de um job de download de modelo de voz até ele terminar.
  useEffect(() => {
    if (!downloadJob || !['downloading', 'verifying'].includes(downloadJob.status)) return undefined;
    const jobId = downloadJob.job_id;
    const interval = window.setInterval(() => {
      bridge.getVoiceModelDownload(jobId)
        .then((latest) => {
          setDownloadJob(latest);
          if (latest.status === 'completed') {
            void bridge.listVoiceModels().then(setVoiceModels);
          }
        })
        .catch((error) => {
          console.error('[SettingsModal] Erro ao consultar download de modelo:', error);
        });
    }, 500);
    return () => window.clearInterval(interval);
  }, [downloadJob]);

  const handleDownloadVoiceModel = async (modelId: string) => {
    setDownloadError('');
    try {
      const started = await bridge.startVoiceModelDownload(modelId);
      setDownloadJob(started);
    } catch (error) {
      setDownloadError(error instanceof Error ? error.message : 'Falha ao iniciar download do modelo.');
    }
  };

  const handleCancelVoiceModelDownload = async () => {
    if (!downloadJob) return;
    try {
      const cancelled = await bridge.cancelVoiceModelDownload(downloadJob.job_id);
      setDownloadJob(cancelled);
    } catch (error) {
      setDownloadError(error instanceof Error ? error.message : 'Falha ao cancelar download do modelo.');
    }
  };

  // Vazio apaga a chave no backend: só o botão Remover chave manda campo vazio.
  const handleSaveApiKey = async (value: string) => {
    if (isSavingApiKey) return;
    setIsSavingApiKey(true);
    try {
      const result = await bridge.saveApiKey(value);
      setApiKey('');
      setToast({ tone: 'ok', text: result.configured ? 'API key salva no .env local.' : 'API key removida do .env local.' });
      const settings = await bridge.getBackendSettings();
      setBackendSettings(settings);
    } catch (error) {
      console.error('[SettingsModal] Erro ao salvar API key:', error);
      setToast({ tone: 'error', text: 'Não foi possível salvar a API key.' });
    } finally {
      setIsSavingApiKey(false);
      setIsConfirmingKeyRemoval(false);
    }
  };

  const handleSaveBackendSettings = async () => {
    if (!backendSettings || isSavingBackendSettings) return;
    setIsSavingBackendSettings(true);
    try {
      const editableRows = backendSettings.settings_catalog.filter((row) => !row.secret && !DESKTOP_HIDDEN_KEYS.includes(row.key));
      const values = Object.fromEntries(
        editableRows.map((row) => [row.key, settingDrafts[row.key] ?? ''])
      );
      const settings = await bridge.saveBackendSettings(values);
      setBackendSettings(settings);
      setSettingDrafts(
        Object.fromEntries(
          settings.settings_catalog
            .filter((row) => !row.secret)
            .map((row) => [row.key, row.value === null ? '' : String(row.value)])
        )
      );
      setToast({ tone: 'ok', text: 'Configurações salvas.' });
    } catch (error) {
      console.error('[SettingsModal] Erro ao salvar settings do backend:', error);
      setToast({
        tone: 'error',
        text: error instanceof Error ? `Não foi possível salvar: ${error.message}` : 'Não foi possível salvar as configurações.',
      });
    } finally {
      setIsSavingBackendSettings(false);
    }
  };

  const refreshBackendSettings = async () => {
    const settings = await bridge.getBackendSettings();
    setBackendSettings(settings);
    setSettingDrafts(
      Object.fromEntries(
        settings.settings_catalog
          .filter((row) => !row.secret)
          .map((row) => [row.key, row.value === null ? '' : String(row.value)])
      )
    );
  };

  const handleApplyPreset = async (presetKey: string) => {
    if (applyingPreset) return;
    setApplyingPreset(presetKey);
    try {
      const result = await bridge.applySettingsPreset(presetKey);
      await refreshBackendSettings();
      setToast({ tone: 'ok', text: `Preset ${result.preset.label} aplicado.` });
    } catch (error) {
      console.error('[SettingsModal] Erro ao aplicar preset:', error);
      setToast({ tone: 'error', text: 'Não foi possível aplicar o preset.' });
    } finally {
      setApplyingPreset('');
    }
  };

  const handleTestProvider = async () => {
    if (isTestingProvider) return;
    setIsTestingProvider(true);
    try {
      const result = await bridge.testAnswerProvider({
        provider: draftProvider,
        model: settingDrafts.answer_model ?? '',
        baseUrl: draftBaseUrl,
      });
      const name = PROVIDER_LABEL[result.provider] ?? result.provider;
      setToast(
        result.error
          ? { tone: 'error', text: `O teste do ${name} falhou: ${result.error}` }
          : { tone: 'ok', text: `${name} respondeu em ${result.latency_ms} ms com ${result.model}.` }
      );
    } catch (error) {
      console.error('[SettingsModal] Erro ao testar provider:', error);
      setToast({ tone: 'error', text: 'Não foi possível testar o provedor.' });
    } finally {
      setIsTestingProvider(false);
    }
  };

  const handleListModels = async () => {
    if (isListingModels) return;
    setIsListingModels(true);
    setToast(null);
    try {
      // O resultado vira a lista do campo Modelo; o aviso flutuante fica para erros.
      setModelDiscovery(await bridge.listAnswerModels({ provider: draftProvider, baseUrl: draftBaseUrl }));
    } catch (error) {
      console.error('[SettingsModal] Erro ao listar modelos:', error);
      setToast({ tone: 'error', text: 'Não foi possível listar os modelos.' });
    } finally {
      setIsListingModels(false);
    }
  };

  const discardDrafts = () => {
    if (backendSettings) setSettingDrafts(draftsFrom(backendSettings));
    setDownloadJob(null);
    setDownloadError('');
  };

  // Estado de instalado/baixando/erro de UM modelo de voz - reusado tanto
  // para o modelo de transcricao selecionado quanto para o VAD (componente
  // interno, sempre necessario para gravar audio).
  const renderVoiceModelDownloadStatus = (model: VoiceModelInfo) => {
    const job = downloadJob && downloadJob.model_id === model.id ? downloadJob : null;
    const inProgress = job && !['completed', 'failed', 'cancelled'].includes(job.status);
    if (model.installed) {
      return (
        <div className="voice-dl" aria-live="polite">
          <span className="voice-dl__ok"><CheckCircleIcon size={14} />Instalado.</span>
          <span className="voice-dl__hash mono">SHA-256 ok</span>
        </div>
      );
    }
    if (job && inProgress) {
      const percent = job.bytes_total > 0 ? Math.min(100, (job.bytes_completed / job.bytes_total) * 100) : 0;
      return (
        <div className="voice-dl voice-dl--progress" aria-live="polite">
          <div className="voice-dl__bar" role="progressbar" aria-label="Progresso do download" aria-valuenow={Math.round(percent)} aria-valuemin={0} aria-valuemax={100}>
            <i style={{ width: `${percent}%` }} />
          </div>
          <div className="voice-dl__row mono">
            <span>
              {job.status === 'verifying'
                ? 'verificando SHA-256…'
                : `${(job.bytes_completed / (1024 * 1024)).toFixed(0)} / ${(job.bytes_total / (1024 * 1024)).toFixed(0)} MB`}
            </span>
            <button type="button" className="link-btn" onClick={handleCancelVoiceModelDownload}>
              Cancelar download
            </button>
          </div>
        </div>
      );
    }
    const failed = job?.status === 'failed';
    return (
      <div className="voice-dl" aria-live="polite">
        {failed && <span className="settings-warning">{job?.message ?? 'Falha ao baixar o modelo.'}</span>}
        {downloadError && job && <span className="settings-warning">{downloadError}</span>}
        {!failed && <span className="voice-dl__muted">Não instalado</span>}
        <button type="button" className="btn btn--sm" onClick={() => handleDownloadVoiceModel(model.id)}>
          <DownloadIcon size={14} />
          {failed ? 'Tentar novamente' : 'Baixar modelo'}
        </button>
      </div>
    );
  };

  const renderSettingRow = (row: SettingRow, overrideOptions?: (SettingOption & { disabled?: boolean })[]) => {
    const options = overrideOptions ?? row.options;
    const draft = settingDrafts[row.key] ?? '';
    const recommended =
      row.recommended === null || row.recommended === undefined || row.recommended === ''
        ? null
        : options.find((option) => option.value === String(row.recommended))?.label ?? String(row.recommended);
    const choice = options.find((option) => option.value === draft)?.description;
    return (
    <div key={row.key} className="settings-item settings-item--stacked">
      <div className="settings-item__info">
        <span className="settings-item__head">
          <span className="settings-item__label">{row.label}</span>
          {recommended && <span className="settings-item__rec">Recomendado: {recommended}</span>}
        </span>
        <span className="settings-item__description">{row.description}</span>
        {row.warning && (
          <span className="settings-warning">{row.warning}</span>
        )}
      </div>

      {options.length > 0 ? (
        <Select
          className="settings-control-wide"
          value={draft}
          options={options}
          ariaLabel={row.label}
          onChange={(value) =>
            setSettingDrafts((prev) => ({ ...prev, [row.key]: value }))
          }
        />
      ) : row.value_type === 'bool' ? (
        <Select
          className="settings-control-wide"
          value={settingDrafts[row.key] ?? 'false'}
          options={[
            { value: 'true', label: 'Sim' },
            { value: 'false', label: 'Não' },
          ]}
          ariaLabel={row.label}
          onChange={(value) =>
            setSettingDrafts((prev) => ({ ...prev, [row.key]: value }))
          }
        />
      ) : (
        <input
          type={row.value_type === 'int' || row.value_type === 'float' ? 'number' : 'text'}
          className="vault-picker__input settings-control-wide"
          value={settingDrafts[row.key] ?? ''}
          placeholder={row.placeholder ?? ''}
          aria-label={row.label}
          min={row.min ?? undefined}
          max={row.max ?? undefined}
          step={row.value_type === 'float' ? 'any' : undefined}
          onChange={(event) =>
            setSettingDrafts((prev) => ({ ...prev, [row.key]: event.target.value }))
          }
        />
      )}
      {choice && <p className="settings-item__choice">{choice}</p>}
    </div>
    );
  };

  if (!isOpen) return null;

  const doctor = backendSettings?.doctor;
  const doctorTotal = doctor ? doctor.ok_count + doctor.warning_count + doctor.error_count : 0;
  const audioRows = backendSettings?.settings_catalog.filter((row) => row.group === 'Áudio' && !row.secret) ?? [];
  const audioModelRow = audioRows.find((row) => row.key === 'audio_model') ?? null;
  const audioLanguageRow = audioRows.find((row) => row.key === 'audio_language') ?? null;
  const otherAudioRows = audioRows.filter((row) => row.key !== 'audio_model' && row.key !== 'audio_language');
  // Idioma "auto" e codigos fora de model.languages nao fazem sentido para o
  // modelo selecionado - desabilita em vez de deixar o usuario salvar uma
  // combinacao que o backend vai rejeitar em runtime (audio_runtime.py).
  const audioLanguageOptions = (audioLanguageRow?.options ?? []).map((option) => ({
    ...option,
    disabled: selectedVoiceModel
      ? option.value === 'auto'
        ? !selectedVoiceModel.supports_auto_language
        : !selectedVoiceModel.languages.includes(option.value)
      : false,
  }));
  const catalogLabel = (key: string) =>
    backendSettings?.settings_catalog.find((row) => row.key === key)?.label ?? key;
  // Modelo, URL, API key, Testar e Listar só existem para provedores generativos.
  const isGenerative = draftProvider !== 'extractive';
  const needsApiKey = draftProvider === 'openai-compatible';
  const providerLabel = PROVIDER_LABEL[draftProvider] ?? draftProvider;
  // Lista de modelos só vale para o provedor que está na tela (trocar de provedor descarta a anterior).
  const discovered = modelDiscovery?.provider === draftProvider ? modelDiscovery : null;
  const draftModel = settingDrafts.answer_model ?? '';
  // "qchat" e "qchat:latest" são o mesmo modelo no Ollama: a opção fica com a grafia salva.
  const isDraftModel = (id: string) => id === draftModel || id === `${draftModel}:latest`;
  const modelOptions: SettingOption[] = (discovered?.models ?? []).map((model) => ({
    value: isDraftModel(model.id) ? draftModel : model.id,
    label: model.label,
    description: modelDescription(model.details),
  }));
  if (modelOptions.length > 0 && draftModel && !modelOptions.some((option) => option.value === draftModel)) {
    modelOptions.push({ value: draftModel, label: draftModel, description: `Não está instalado no ${providerLabel}: escolha um da lista.` });
  }
  const iaCatalogRows = backendSettings?.settings_catalog.filter((row) => IA_CATALOG_KEYS.includes(row.key) && !row.secret) ?? [];
  const advancedRows = backendSettings?.settings_catalog.filter(
    (row) => !row.secret && row.group !== 'Áudio' && !IA_CATALOG_KEYS.includes(row.key) && !DESKTOP_HIDDEN_KEYS.includes(row.key)
  ) ?? [];

  // Renderiza diretamente no document.body via Portal.
  // O overlay usa display:flex para centralizar o modal de forma confiável.
  return createPortal(
    <div className="modal-overlay">
      {/* Fundo clicável fecha o modal. Botão nativo atrás do card: arrastar de dentro do card
          para fora não dispara o clique nele (o click cai no overlay, ancestral comum). */}
      <button
        type="button"
        className="modal-backdrop"
        aria-label="Fechar configurações clicando fora"
        tabIndex={-1}
        onClick={onClose}
      />
      {/* Janela do modal — filho direto do overlay flex */}
      <div
        ref={modalRef}
        className="modal modal--wide"
        role="dialog"
        aria-modal="true"
        aria-labelledby="settings-title"
        tabIndex={-1}
      >
        {/* Cabeçalho do modal */}
        <div className="modal__header">
          <h2 id="settings-title" className="modal__title">Configurações</h2>
          <button
            id="btn-close-settings"
            type="button"
            className="modal__close"
            aria-label="Fechar configurações"
            onClick={onClose}
          >
            <XIcon size={16} />
          </button>
        </div>

        {/* Corpo do modal: navegação lateral + painel da aba ativa */}
        <div className="modal__body modal__body--settings">
          <nav className="settings-nav" aria-label="Categorias de configuração">
            {SETTINGS_TABS.filter((tab) => tab.id !== 'avancado' || advancedUnlocked).map((tab) => (
              <button
                key={tab.id}
                type="button"
                className={`settings-nav__item${currentTab ===tab.id ? ' settings-nav__item--active' : ''}`}
                aria-current={currentTab ===tab.id ? 'page' : undefined}
                onClick={() => setActiveTab(tab.id)}
              >
                {(() => {
                  const TabIcon = TAB_ICONS[tab.id];
                  return <TabIcon size={16} />;
                })()}
                <span>{tab.label}</span>
                {tab.id === 'geral' && (backendSettings?.doctor?.error_count ?? 0) > 0 && (
                  <span className="settings-nav__dot" aria-label="Diagnóstico com erro" />
                )}
              </button>
            ))}
            {!advancedUnlocked && (
              <button type="button" className="settings-nav__item settings-nav__unlock" onClick={handleAdvancedUnlockClick}>
                <span>
                  {advancedClicks > 0
                    ? `Desbloquear avançado (${advancedClicks}/${ADVANCED_UNLOCK_CLICKS})`
                    : 'Desbloquear avançado'}
                </span>
              </button>
            )}
          </nav>

          <div className="settings-panel">
            {currentTab ==='geral' && (
              <section className="settings-section" aria-labelledby="settings-doctor">
                <h3 id="settings-doctor" className={`settings-section__title${active ? ' settings-section__title--vault' : ''}`}>
                  {active ? (
                    <>
                      Diagnóstico da vault
                      <VaultGlyph icon={active.icon} color={active.color} size={12} />
                      <span>{active.name}</span>
                    </>
                  ) : (
                    'Diagnóstico'
                  )}
                </h3>
                {backendSettings && doctor ? (
                  <>
                    <div className={`doctor__summary doctor__summary--${doctor.status}`}>
                      <span className="doctor__summary-icon" aria-hidden="true">
                        {doctor.status === 'ok' ? (
                          <CheckCircleIcon size={18} />
                        ) : doctor.status === 'error' ? (
                          <XCircleIcon size={18} />
                        ) : (
                          <AlertTriangleIcon size={18} />
                        )}
                      </span>
                      <div>
                        <b>
                          {doctor.error_count > 0
                            ? `${doctor.error_count} ${doctor.error_count === 1 ? 'verificação com erro' : 'verificações com erro'}`
                            : doctor.warning_count > 0
                              ? `${doctor.warning_count} ${doctor.warning_count === 1 ? 'aviso' : 'avisos'}`
                              : 'Tudo certo'}
                        </b>
                        <span className="doctor__summary-meta">
                          {doctorTotal} {doctorTotal === 1 ? 'verificação' : 'verificações'} · {doctor.latency_ms} ms
                        </span>
                      </div>
                      <button type="button" className="btn" onClick={handleRerunDoctor} disabled={isRunningDoctor}>
                        <RefreshIcon size={14} />
                        {isRunningDoctor ? 'Verificando…' : 'Verificar de novo'}
                      </button>
                    </div>
                    <dl className="doctor__stats">
                      <div className="doctor__stat">
                        <dt>Notas</dt>
                        <dd className="mono">{backendSettings.notes_count.toLocaleString('pt-BR')}</dd>
                      </div>
                      <div className="doctor__stat">
                        <dt>Chunks no SQLite</dt>
                        <dd className="mono">{backendSettings.sqlite_chunks_count.toLocaleString('pt-BR')}</dd>
                      </div>
                      <div className="doctor__stat">
                        <dt>Vetores no Chroma</dt>
                        <dd className="mono">{backendSettings.vector_chunks_count.toLocaleString('pt-BR')}</dd>
                      </div>
                    </dl>
                    {groupChecks(doctor.checks).map((group) => (
                      <Fragment key={group.id}>
                        <h4 className="doctor__group">{group.title}</h4>
                        <ul className="doctor__checks">
                          {group.checks.map((check) => (
                            <li key={check.code} className={`doctor__check doctor__check--${check.status}`}>
                              {check.status === 'ok' ? <CheckCircleIcon size={15} /> : check.status === 'warning' ? <AlertTriangleIcon size={15} /> : <XCircleIcon size={15} />}
                              <div>
                                <span className="doctor__label">{checkLabel(check.code)}</span>
                                <span className="doctor__msg">{check.message}</span>
                                {check.action && check.status !== 'ok' && <span className="doctor__action">{check.action}</span>}
                              </div>
                              <span className="doctor__meta mono">
                                {check.latency_ms != null && check.latency_ms >= 100 ? `${check.code} · ${check.latency_ms} ms` : check.code}
                              </span>
                            </li>
                          ))}
                        </ul>
                      </Fragment>
                    ))}
                  </>
                ) : (
                  <div className="settings-item settings-item--stacked" aria-label="Carregando diagnóstico">
                    <div className="skeleton-box skeleton-box--path" />
                    <div className="skeleton-box skeleton-box--meta" />
                  </div>
                )}
              </section>
            )}

            {currentTab ==='vaults' && <VaultsTab onOpenQueue={() => onOpenQueue?.()} />}

            {currentTab ==='ia' && (
              <section className="settings-section" aria-labelledby="settings-ai">
                <h3 id="settings-ai" className="settings-section__title">
                  IA
                </h3>
                <p className="settings-section__lede">Como a resposta é escrita a partir dos trechos das suas notas.</p>

                {iaCatalogRows
                  .filter((row) => isGenerative || row.key === 'answer_provider')
                  .map((row) => {
                    // Modelo: lista do que está instalado no provedor; URL: o padrão do provedor escolhido.
                    if (row.key === 'answer_model' && modelOptions.length > 0) return renderSettingRow(row, modelOptions);
                    if (row.key === 'answer_base_url') {
                      return renderSettingRow({ ...row, placeholder: PROVIDER_DEFAULT_URL[draftProvider] ?? row.placeholder });
                    }
                    return renderSettingRow(row);
                  })}

                {isGenerative ? (
                    <div className="settings-item settings-item--stacked">
                    <div className="settings-item__info">
                      <span className="settings-item__label">{needsApiKey ? 'API key' : 'Conexão'}</span>
                      <span className="settings-item__description">
                        {needsApiKey
                          ? `${backendSettings?.answer_api_key_configured ? 'Configurada no .env local.' : 'Ausente.'} Teste o provedor ou liste os modelos dele.`
                          : `Roda no seu computador, sem API key. Testar manda uma pergunta curta ao ${providerLabel} com o modelo escolhido.`}
                      </span>
                    </div>

                    <div className="vault-picker" role="group" aria-label={needsApiKey ? 'Salvar API key local' : `Conexão com o ${providerLabel}`}>
                      {needsApiKey && (
                        <>
                          <input
                            id="input-api-key"
                            type="password"
                            className="vault-picker__input"
                            value={apiKey}
                            placeholder="ESCOLIO_ANSWER_API_KEY"
                            aria-label="API key"
                            onChange={(event) => setApiKey(event.target.value)}
                          />
                          <button
                            id="btn-save-api-key"
                            type="button"
                            className="btn"
                            onClick={() => handleSaveApiKey(apiKey)}
                            disabled={isSavingApiKey || !apiKey.trim()}
                            aria-label="Salvar API key"
                          >
                            {isSavingApiKey ? 'Salvando…' : 'Salvar'}
                          </button>
                          {backendSettings?.answer_api_key_configured && (
                            <button
                              id="btn-remove-api-key"
                              type="button"
                              className={`btn${isConfirmingKeyRemoval ? ' btn--danger' : ''}`}
                              onClick={() => {
                                if (isConfirmingKeyRemoval) void handleSaveApiKey('');
                                else setIsConfirmingKeyRemoval(true);
                              }}
                              onBlur={() => setIsConfirmingKeyRemoval(false)}
                              disabled={isSavingApiKey}
                            >
                              {isConfirmingKeyRemoval ? 'Confirmar remoção' : 'Remover chave'}
                            </button>
                          )}
                        </>
                      )}
                      <button
                        id="btn-test-provider"
                        type="button"
                        className="btn"
                        onClick={handleTestProvider}
                        disabled={isTestingProvider}
                        aria-label="Testar provider"
                      >
                        {isTestingProvider ? 'Testando…' : 'Testar'}
                      </button>
                      <button
                        id="btn-list-models"
                        type="button"
                        className="btn"
                        onClick={handleListModels}
                        disabled={isListingModels}
                        aria-label="Listar modelos"
                      >
                        {isListingModels ? 'Listando…' : 'Listar modelos'}
                      </button>
                    </div>
                    {discovered && (
                      <div className="settings-discovery" aria-live="polite">
                        <span className="settings-inline-status">
                          {discovered.models.length} {discovered.models.length === 1 ? 'modelo' : 'modelos'} no {providerLabel} ·{' '}
                          {discovered.latency_ms} ms{discovered.cached ? ' · em cache' : ''}
                          {discovered.status !== 'ok' && ` · ${MODEL_STATUS[discovered.status] ?? discovered.status}`}
                        </span>
                        {discovered.status === 'offline' && LOCAL_PROVIDERS.has(draftProvider) ? (
                          <span className="settings-warning">
                            O {providerLabel} não respondeu em {discovered.base_url}. Abra o {providerLabel} e clique em Listar modelos.
                          </span>
                        ) : (
                          discovered.message && <span className="settings-warning">{discovered.message}</span>
                        )}
                      </div>
                    )}
                  </div>
                ) : null}
              </section>
            )}

            {currentTab ==='voz' && (
              <section className="settings-section" aria-labelledby="settings-voz">
                <h3 id="settings-voz" className="settings-section__title">
                  Voz
                </h3>
                <p className="settings-section__lede">Transcrição local da pergunta falada: nada sai do seu computador.</p>

                <div className="settings-item settings-item--stacked">
                  <div className="settings-item__info">
                    <span className="settings-item__label">
                      {audioModelRow?.label ?? 'Modelo de transcrição (voz)'}
                    </span>
                    <span className="settings-item__description">
                      {audioModelRow?.description ?? 'Modelo local usado para transcrever o áudio gravado no chat.'} Arraste para
                      ver todos.
                    </span>
                  </div>

                  {selectableVoiceModels.length > 0 ? (
                    <MomentumRail className="voice-models" role="radiogroup" aria-label={audioModelRow?.label ?? 'Modelo de transcrição (voz)'}>
                      {selectableVoiceModels.map((model) => {
                        const checked = settingDrafts.audio_model === model.id;
                        const autoLang = model.supports_auto_language;
                        return (
                          <div
                            key={model.id}
                            role="radio"
                            aria-checked={checked}
                            aria-label={model.label}
                            tabIndex={0}
                            className={`voice-model${checked ? ' voice-model--checked' : ''}`}
                            onClick={(event) => {
                              // Os botões de baixar/cancelar ficam no rodapé do cartão e não escolhem o modelo.
                              if (!(event.target as HTMLElement).closest('.voice-model__foot')) selectVoiceModel(model.id);
                            }}
                            onKeyDown={(event) => {
                              if (event.target === event.currentTarget && (event.key === 'Enter' || event.key === ' ')) {
                                event.preventDefault();
                                selectVoiceModel(model.id);
                              }
                            }}
                          >
                            <span className="voice-model__radio" aria-hidden="true" />
                            <span className="voice-model__name">{model.label}</span>
                            <span className="voice-model__badges">
                              {model.recommended && <span className="pill pill--accent">Recomendado</span>}
                              {model.languages.length === 1 && <span className="pill">só {model.languages[0]}</span>}
                            </span>
                            <span className="voice-model__desc">{model.description}</span>
                            <dl className="voice-model__specs">
                              <dt>Tamanho</dt>
                              <dd className="mono">{(model.size_bytes / (1024 * 1024)).toFixed(0)} MB</dd>
                              <dt>Idiomas</dt>
                              <dd className="mono">{model.languages.length}{autoLang ? ' + automático' : ''}</dd>
                              {model.speed_tier && (
                                <>
                                  <dt>Velocidade</dt>
                                  <dd><Meter level={SPEED_LEVEL[model.speed_tier] ?? 2} label="Velocidade" /></dd>
                                </>
                              )}
                              {model.quality_tier && (
                                <>
                                  <dt>Qualidade</dt>
                                  <dd><Meter level={QUALITY_LEVEL[model.quality_tier] ?? 2} label="Qualidade" /></dd>
                                </>
                              )}
                            </dl>
                            <div className="voice-model__foot">
                              {renderVoiceModelDownloadStatus(model)}
                            </div>
                          </div>
                        );
                      })}
                    </MomentumRail>
                  ) : (
                    <Select
                      className="settings-control-wide"
                      value={settingDrafts.audio_model ?? ''}
                      ariaLabel={audioModelRow?.label ?? 'Modelo de transcrição (voz)'}
                      options={audioModelRow?.options ?? []}
                      onChange={selectVoiceModel}
                    />
                  )}
                </div>

                {audioLanguageRow && renderSettingRow(audioLanguageRow, audioLanguageOptions)}
                {otherAudioRows.map((row) => renderSettingRow(row))}

                {vadModel && (
                  <div className="settings-item settings-item--stacked">
                    <div className="settings-item__info">
                      <span className="settings-item__label">Componente do sistema</span>
                      <span className="settings-item__description">{vadModel.description}</span>
                    </div>
                    {renderVoiceModelDownloadStatus(vadModel)}
                  </div>
                )}
              </section>
            )}

            {currentTab ==='avancado' && (
              <>
                <section className="settings-section" aria-labelledby="settings-presets">
                  <h3 id="settings-presets" className="settings-section__title">
                    Presets
                  </h3>
                  <p className="settings-section__lede">Combinações prontas de busca e indexação. Aplicar grava na hora.</p>
                  {backendSettings?.settings_presets.map((preset) => (
                    <div key={preset.key} className="settings-item settings-item--stacked">
                      <div className="settings-item__info">
                        <span className="settings-item__label">{preset.label}</span>
                        <span className="settings-item__description">{preset.description}</span>
                        <dl className="preset__values">
                          {Object.entries(preset.values).map(([key, value]) => (
                            <div key={key}>
                              <dt>{catalogLabel(key)}</dt>
                              <dd className="mono">{String(value)}</dd>
                            </div>
                          ))}
                        </dl>
                      </div>
                      <button
                        type="button"
                        className="btn btn--sm preset__apply"
                        onClick={() => handleApplyPreset(preset.key)}
                        disabled={Boolean(applyingPreset)}
                        aria-label={`Aplicar preset ${preset.label}`}
                      >
                        {applyingPreset === preset.key ? 'Aplicando…' : 'Aplicar'}
                      </button>
                    </div>
                  ))}
                </section>

                <div className="settings-divider" aria-hidden="true" />

                <section className="settings-section" aria-labelledby="settings-advanced">
                  <h3 id="settings-advanced" className="settings-section__title">
                    Avançado
                  </h3>
                  <p className="settings-section__lede">Ajustes finos de busca, chunks e indexação. Mude só se souber o efeito.</p>
                  {advancedRows.map((row) => renderSettingRow(row))}
                </section>
              </>
            )}

            {currentTab ==='aparencia' && (
              <>
                <section className="settings-section" aria-labelledby="settings-appearance">
                  <h3 id="settings-appearance" className="settings-section__title">
                    Aparência
                  </h3>

                  <div className="settings-item">
                    <div className="settings-item__info">
                      <span className="settings-item__label">Tema</span>
                      <span className="settings-item__description">
                        Aparência visual do aplicativo
                      </span>
                    </div>
                    <div className="settings-item__control">
                      <Select
                        id="select-theme"
                        value={theme}
                        onChange={(value) => {
                          const choice = value as ThemeChoice;
                          setTheme(choice);
                          saveThemeChoice(choice);
                        }}
                        ariaLabel="Selecionar tema"
                        options={[
                          { value: 'dark', label: 'Escuro' },
                          { value: 'light', label: 'Claro' },
                          { value: 'system', label: 'Seguir o sistema' },
                        ]}
                      />
                    </div>
                  </div>
                </section>

                <div className="settings-divider" aria-hidden="true" />

                <section className="settings-section" aria-labelledby="settings-about">
                  <h3 id="settings-about" className="settings-section__title">
                    Sobre
                  </h3>

                  <div className="settings-item">
                    <div className="settings-item__info">
                      <span className="settings-item__label">Escólio</span>
                      <span className="settings-item__description">
                        Perguntas sobre o seu vault, respondidas só com as notas indexadas e com a fonte de cada afirmação.
                      </span>
                    </div>
                    <span className="settings-badge mono">v{__APP_VERSION__}</span>
                  </div>
                </section>
              </>
            )}
          </div>
        </div>

        {toast && (
          <div
            className={`settings-toast settings-toast--${toast.tone}${pendingChanges > 0 ? ' settings-toast--raised' : ''}`}
            role={toast.tone === 'error' ? 'alert' : 'status'}
          >
            {toast.tone === 'ok' ? <CheckCircleIcon size={16} /> : <AlertTriangleIcon size={16} />}
            <span>{toast.text}</span>
            {toast.tone === 'error' && (
              <button type="button" className="settings-toast__close" aria-label="Fechar aviso" onClick={() => setToast(null)}>
                <XIcon size={12} />
              </button>
            )}
          </div>
        )}

        {/* Barra de salvar: só existe com alteração pendente (sem "Nenhuma alteração" parado no rodapé). */}
        {pendingChanges > 0 && (
          <div className="modal__footer settings-savebar" role="region" aria-label="Alterações não salvas">
            <span className="modal__pending" aria-live="polite">
              <span className="modal__pending-dot" aria-hidden="true" />
              {pendingChanges} {pendingChanges === 1 ? 'alteração não salva' : 'alterações não salvas'}
            </span>
            <div className="modal__footer-actions">
              <button type="button" className="btn btn--ghost" onClick={discardDrafts}>
                Descartar
              </button>
              <button
                id="btn-save-backend-settings"
                type="button"
                className="btn btn--primary"
                onClick={handleSaveBackendSettings}
                disabled={!backendSettings || isSavingBackendSettings}
                aria-label="Salvar configurações do backend"
              >
                {isSavingBackendSettings ? 'Salvando…' : 'Salvar alterações'}
              </button>
            </div>
          </div>
        )}
      </div>
    </div>,
    document.body
  );
};

export default SettingsModal;
