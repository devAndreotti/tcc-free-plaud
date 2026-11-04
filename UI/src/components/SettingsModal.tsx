import { useCallback, useEffect, useMemo, useRef, useState, useSyncExternalStore, type ComponentType } from 'react';
import { createPortal } from 'react-dom';
import {
  AlertTriangleIcon,
  CheckCircleIcon,
  CodeIcon,
  ContrastIcon,
  DownloadIcon,
  MicIcon,
  SlidersIcon,
  StarsIcon,
  VaultIcon,
  XIcon,
} from './Icons';
import AppearanceFields from './AppearanceFields';
import MomentumRail from './MomentumRail';
import Select from './Select';
import VaultsTab from './VaultsTab';
import { VaultGlyph } from './VaultGlyph';
import { useVaults } from '../hooks/useVaults';
import { AiSourcesPane } from './AiSourcesPane';
import { AdvancedLocked, AdvancedPane } from './AdvancedPane';
import DoctorPanel from './DoctorPanel';
import MicTest from './MicTest';
import { DoctorSkeleton } from './DoctorPanel';
import { getDoctorSnapshot, lastDoctorStats, refreshDoctor, rememberDoctorStats, subscribeDoctor } from '../lib/doctorReport';
import { SettingsTabSkeleton, SkLines } from './ui/Loading';
import { GroupCard, Segmented, SectionHead, Stepper } from './ui/Controls';
import { Glyph, type GlyphName } from './ui/Glyph';
import './settings-redesign.css';
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

// Chaves que o desktop não mostra nem grava: o embedding em uso é o da vault ativa (config.py, _apply_active_vault), e a pasta padrão do corpus só é lida pela TUI.
const DESKTOP_HIDDEN_KEYS = ['embedding_model', 'default_corpus_path'];

const MODEL_STATUS: Record<string, string> = { offline: 'offline', unauthorized: 'sem autorização', error: 'erro' };

// URL que o backend usa com o campo vazio (providers/answer.py::_default_base_url).
const PROVIDER_DEFAULT_URL: Record<string, string> = {
  ollama: 'http://localhost:11434/v1',
  lmstudio: 'http://localhost:1234/v1',
  'openai-compatible': 'https://api.openai.com/v1',
};
const PROVIDER_LABEL: Record<string, string> = { ollama: 'Ollama', lmstudio: 'LM Studio', 'openai-compatible': 'provedor' };
// IA local: os modelos instalados aparecem sozinhos ao abrir a aba (remoto só lista no botão).
const PROVIDER_ICON: Record<string, GlyphName> = { extractive: 'list', ollama: 'cube', lmstudio: 'server', 'openai-compatible': 'cloud' };
const PROVIDER_HOST: Record<string, string> = { extractive: 'sem modelo', ollama: 'localhost:11434', lmstudio: 'localhost:1234', 'openai-compatible': 'URL + chave' };
const LOCAL_PROVIDERS = new Set(['ollama', 'lmstudio']);

// "3.1B · Q4_K_M · 2,3 GB" com o que o Ollama informa; o LM Studio não manda esses dados.
const modelDescription = (details: Record<string, unknown>) => {
  const size = typeof details.size === 'number'
    ? `${(details.size / 1e9).toLocaleString('pt-BR', { maximumFractionDigits: 1 })} GB`
    : null;
  return [details.parameter_size, details.quantization_level, size].filter(Boolean).join(' · ') || undefined;
};

export type SettingsTab = 'geral' | 'vaults' | 'ia' | 'voz' | 'avancado' | 'aparencia';

// Elementos que recebem foco com Tab; o contêiner do modal (tabIndex -1) fica de fora.
const FOCUSABLE_SELECTOR = 'button:not([disabled]), a[href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

const SETTINGS_TABS: { id: SettingsTab; label: string }[] = [
  { id: 'geral', label: 'Diagnóstico' },
  { id: 'vaults', label: 'Vaults' },
  { id: 'ia', label: 'Fontes de IA' },
  { id: 'voz', label: 'Voz' },
  { id: 'avancado', label: 'Avançado' },
  { id: 'aparencia', label: 'Aparência' },
];

// Avançado começa bloqueado: a aba explica o que tem dentro e libera depois da confirmação; a liberação fica gravada.
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
  const [isConfirmingClose, setIsConfirmingClose] = useState(false);
  const [isSavingBackendSettings, setIsSavingBackendSettings] = useState(false);
  const [applyingPreset, setApplyingPreset] = useState('');
  const [isTestingProvider, setIsTestingProvider] = useState(false);
  const [isListingModels, setIsListingModels] = useState(false);
  const [modelDiscovery, setModelDiscovery] = useState<ModelDiscoveryResult | null>(null);
  const [activeTab, setActiveTab] = useState<SettingsTab>('geral');
  const [toast, setToast] = useState<Toast | null>(null);
  const [voiceModels, setVoiceModels] = useState<VoiceModelInfo[]>([]);
  const [voiceLoaded, setVoiceLoaded] = useState(false);
  const [settingsLoaded, setSettingsLoaded] = useState(false);
  const [downloadJob, setDownloadJob] = useState<VoiceModelDownloadSnapshot | null>(null);
  const [downloadError, setDownloadError] = useState('');
  const [advancedUnlocked, setAdvancedUnlocked] = useState(readAdvancedUnlocked);
  const currentTab: SettingsTab = activeTab;

  // Liberar o Avançado: a aba bloqueada explica o que tem dentro e o usuário confirma; fica gravado.
  const handleUnlockAdvanced = () => {
    saveAdvancedUnlocked();
    setAdvancedUnlocked(true);
  };

  // Esconde o Avançado de novo e apaga a liberação gravada.
  const handleHideAdvanced = () => {
    try {
      window.localStorage.removeItem(ADVANCED_UNLOCK_KEY);
    } catch {
      // Sem storage não há liberação gravada para apagar.
    }
    setAdvancedUnlocked(false);
  };

  const { active } = useVaults();

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- abre na aba pedida por quem chamou o modal.
    if (isOpen && initialTab) setActiveTab(initialTab);
  }, [isOpen, initialTab]);


  const pendingChanges = useMemo(() => {
    if (!backendSettings) return 0;
    const saved = draftsFrom(backendSettings);
    return Object.keys(saved).filter((key) => (settingDrafts[key] ?? '') !== saved[key]).length;
  }, [backendSettings, settingDrafts]);

  // Com rascunho pendente, fechar pede confirmação antes de descartar.
  const requestClose = useCallback(() => {
    if (pendingChanges > 0) setIsConfirmingClose(true);
    else onClose();
  }, [pendingChanges, onClose]);

  // Fecha o modal ao pressionar Escape
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') requestClose();
    };
    if (isOpen) document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, requestClose]);

  // Foca o modal quando abre (acessibilidade) e devolve o foco a quem abriu ao fechar.
  useEffect(() => {
    if (!isOpen) return undefined;
    const opener = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    modalRef.current?.focus();
    return () => {
      if (opener?.isConnected) opener.focus();
    };
  }, [isOpen]);

  // Tab e Shift+Tab circulam dentro do modal: no último vai ao primeiro, no primeiro vai ao último.
  useEffect(() => {
    if (!isOpen) return undefined;
    const handleTab = (e: KeyboardEvent) => {
      const modal = modalRef.current;
      if (e.key !== 'Tab' || !modal) return;
      const items = Array.from(modal.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR));
      if (items.length === 0) return;
      const first = items[0];
      const last = items[items.length - 1];
      const active = document.activeElement;
      const inside = active instanceof Node && modal.contains(active);
      if (e.shiftKey && (!inside || active === first || active === modal)) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && (!inside || active === last)) {
        e.preventDefault();
        first.focus();
      }
    };
    document.addEventListener('keydown', handleTab);
    return () => document.removeEventListener('keydown', handleTab);
  }, [isOpen]);

  const [isRunningDoctor, setIsRunningDoctor] = useState(false);
  const { report: doctorReport, running: doctorRunning } = useSyncExternalStore(subscribeDoctor, getDoctorSnapshot);

  useEffect(() => {
    if (toast?.tone !== 'ok') return undefined;
    const timer = window.setTimeout(() => setToast(null), 3500);
    return () => window.clearTimeout(timer);
  }, [toast]);

  useEffect(() => {
    if (!isOpen) return;
    // O Diagnóstico leva segundos: as abas não esperam por ele, e a dele mostra o último resultado enquanto atualiza.
    refreshDoctor().catch((error) => {
      console.error('[SettingsModal] Erro ao rodar o diagnóstico:', error);
    });
    bridge.getBackendSettings({ doctor: false })
      .then((settings) => {
        rememberDoctorStats(settings);
        setBackendSettings(settings);
        setSettingDrafts(draftsFrom(settings));
        setIsConfirmingKeyRemoval(false);
        setIsConfirmingClose(false);
      })
      .catch((error) => {
        console.error('[SettingsModal] Erro ao carregar settings do backend:', error);
      })
      .finally(() => setSettingsLoaded(true));
  }, [isOpen]);

  // Roda o Doctor de novo sem descartar o que o usuário já editou.
  const handleRerunDoctor = async () => {
    setIsRunningDoctor(true);
    try {
      const [settings] = await Promise.all([bridge.getBackendSettings({ doctor: false }), refreshDoctor()]);
      rememberDoctorStats(settings);
      setBackendSettings((prev) => (prev ? { ...prev, doctor: settings.doctor ?? prev.doctor, notes_count: settings.notes_count, sqlite_chunks_count: settings.sqlite_chunks_count } : settings));
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

  // Carrega o catálogo de modelos de voz (com estado instalado) quando o modal abre.
  useEffect(() => {
    if (!isOpen) return;
    bridge.listVoiceModels()
      .then(setVoiceModels)
      .catch((error) => {
        console.error('[SettingsModal] Erro ao listar modelos de voz:', error);
      })
      .finally(() => setVoiceLoaded(true));
  }, [isOpen]);

  // Antes de os ajustes chegarem, as abas que dependem deles mostram o esqueleto; Aparência e Avançado bloqueado não esperam nada.
  const skeletonTab = !backendSettings && !settingsLoaded && (currentTab === 'ia' || currentTab === 'voz' || (currentTab === 'avancado' && advancedUnlocked)) ? currentTab : null;
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

      {options.length >= 2 && options.length <= 4 && !overrideOptions && options.every((option) => option.label.length <= 18 && !option.description) ? (
        <Segmented
          label={row.label}
          value={draft}
          options={options.map((option) => ({ value: option.value, label: option.label }))}
          onChange={(value) => setSettingDrafts((prev) => ({ ...prev, [row.key]: value }))}
        />
      ) : options.length > 0 ? (
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
        <label className="switch settings-switch">
          <input
            type="checkbox"
            checked={settingDrafts[row.key] === 'true'}
            aria-label={row.label}
            onChange={(event) => setSettingDrafts((prev) => ({ ...prev, [row.key]: event.target.checked ? 'true' : 'false' }))}
          />
          <span className="switch__track" aria-hidden="true" />
          <span>{settingDrafts[row.key] === 'true' ? 'Sim' : 'Não'}</span>
        </label>
      ) : row.value_type === 'int' ? (
        <Stepper
          label={row.label}
          value={settingDrafts[row.key] ?? ''}
          min={row.min ?? 0}
          max={row.max ?? undefined}
          onChange={(value) => setSettingDrafts((prev) => ({ ...prev, [row.key]: value }))}
        />
      ) : (
        <input
          type={row.value_type === 'float' ? 'number' : 'text'}
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

  const doctor = doctorReport ?? backendSettings?.doctor;
  const doctorStats = backendSettings
    ? { notes: backendSettings.notes_count, sqlite: backendSettings.sqlite_chunks_count, vectors: backendSettings.vector_chunks_count }
    : lastDoctorStats();
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
  const providerRow = backendSettings?.settings_catalog.find((row) => row.key === 'answer_provider') ?? null;
  const modelRow = backendSettings?.settings_catalog.find((row) => row.key === 'answer_model') ?? null;
  const urlRow = backendSettings?.settings_catalog.find((row) => row.key === 'answer_base_url') ?? null;
  const providerRecommended = providerRow?.options.find((option) => option.value === String(providerRow.recommended))?.label;
  const providerChoice = providerRow?.options.find((option) => option.value === draftProvider)?.description;
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
        onClick={requestClose}
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
            onClick={requestClose}
          >
            <XIcon size={16} />
          </button>
        </div>

        {/* Corpo do modal: navegação lateral + painel da aba ativa */}
        <div className="modal__body modal__body--settings">
          <nav className="settings-nav" aria-label="Categorias de configuração">
            {SETTINGS_TABS.map((tab) => (
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
                {tab.id === 'geral' && (doctor?.error_count ?? 0) > 0 && (
                  <span className="settings-nav__dot" aria-label="Diagnóstico com erro" />
                )}
                {tab.id === 'avancado' && !advancedUnlocked && (
                  <span className="settings-nav__lock" aria-hidden="true">
                    <Glyph name="lock" size={13} />
                  </span>
                )}
              </button>
            ))}
          </nav>

          <div className="settings-panel">
            {currentTab === 'geral' &&
              (doctorStats && doctor ? (
                <DoctorPanel
                  title={
                    active ? (
                      <span className="doctor-title">
                        Diagnóstico da vault
                        <VaultGlyph icon={active.icon} color={active.color} size={12} />
                        <span>{active.name}</span>
                      </span>
                    ) : (
                      'Diagnóstico'
                    )
                  }
                  doctor={doctor}
                  stats={doctorStats}
                  running={isRunningDoctor || doctorRunning}
                  onRerun={handleRerunDoctor}
                />
              ) : (
                <section className="settings-section" aria-labelledby="settings-doctor">
                  <SectionHead icon="pulse" id="settings-doctor" title="Diagnóstico" lede="Confere índice, IA e voz da vault ativa." />
                  <DoctorSkeleton />
                </section>
              ))}

            {currentTab ==='vaults' && <VaultsTab onOpenQueue={() => onOpenQueue?.()} />}

            {skeletonTab && <SettingsTabSkeleton tab={skeletonTab} />}

            {currentTab ==='ia' && !skeletonTab && (
              <section className="settings-section" aria-labelledby="settings-ai">
                <SectionHead icon="stars" id="settings-ai" title="Fontes de IA" lede="Quem escreve a resposta a partir dos trechos das suas notas. A busca e a transcrição ficam sempre no seu computador." />

                <AiSourcesPane
                  provider={draftProvider}
                  baseUrl={draftBaseUrl}
                  keysConfigured={backendSettings?.cloud_keys_configured ?? {}}
                  onUse={(values) => setSettingDrafts((prev) => ({ ...prev, ...values }))}
                  onKeySaved={async () => {
                    setBackendSettings(await bridge.getBackendSettings());
                    setToast({ tone: 'ok', text: 'Chave salva no .env local.' });
                  }}
                />

                <div className="ui-grid ai-manual">
                  {providerRow && (
                    <GroupCard
                      icon="server"
                      title="Provedor de resposta"
                      desc="Quem transforma os trechos em resposta."
                      right={providerRecommended && <span className="pill pill--accent">Recomendado: {providerRecommended}</span>}
                    >
                      <div className="ai-manual__tiles" role="radiogroup" aria-label={providerRow.label}>
                        {providerRow.options.map((option) => (
                          <button
                            key={option.value}
                            type="button"
                            role="radio"
                            aria-checked={draftProvider === option.value}
                            className="ai-manual__tile ui-tile"
                            onClick={() => setSettingDrafts((prev) => ({ ...prev, answer_provider: option.value }))}
                          >
                            <span className="glyph-badge ai-manual__icon" aria-hidden="true">
                              <Glyph name={PROVIDER_ICON[option.value] ?? 'server'} size={15} />
                            </span>
                            <span className="ai-manual__name">
                              <strong>{option.label}</strong>
                              <small className="mono">{PROVIDER_HOST[option.value] ?? ''}</small>
                            </span>
                          </button>
                        ))}
                      </div>
                      {providerChoice && <p className="ai-manual__desc">{providerChoice}</p>}
                    </GroupCard>
                  )}
                  {isGenerative && modelRow && (
                    <GroupCard icon="cube" title="Modelo de resposta" desc="Modelo que escreve a resposta." delay={60} region={false}>
                      {renderSettingRow(modelRow, modelOptions.length > 0 ? modelOptions : undefined)}
                    </GroupCard>
                  )}
                  {isGenerative && urlRow && (
                    <GroupCard icon="link" title="Endereço do servidor" desc="Vazio usa o padrão do provedor." delay={120} region={false}>
                      {renderSettingRow({ ...urlRow, placeholder: PROVIDER_DEFAULT_URL[draftProvider] ?? urlRow.placeholder })}
                      <button type="button" className="ai-manual__reset" onClick={() => setSettingDrafts((prev) => ({ ...prev, answer_base_url: '' }))}>
                        Restaurar padrão
                      </button>
                    </GroupCard>
                  )}
                {isGenerative ? (
                  <GroupCard icon="pulse" title="Conexão" desc={needsApiKey ? 'Com a sua chave de API.' : 'Sem chave: roda no seu computador.'} delay={180} className="ai-manual__conn">
                    <div
                      className={`settings-item settings-item--stacked conn-card${isTestingProvider || isListingModels ? ' conn-card--testing' : discovered?.status === 'ok' ? ' conn-card--ok' : discovered ? ' conn-card--offline' : ''}`}
                    >
                    <div className="settings-item__info">
                      <span className="settings-item__label">{needsApiKey ? 'API key' : 'Conexão'}</span>
                      <span className="settings-item__description">
                        {needsApiKey
                          ? `${backendSettings?.answer_api_key_configured ? 'Configurada no .env local.' : 'Ausente.'} Teste o provedor ou liste os modelos dele.`
                          : `Roda no seu computador, sem API key. Testar manda uma pergunta curta ao ${providerLabel} com o modelo escolhido.`}
                      </span>
                    </div>

                    <svg key={discovered ? `${discovered.status}-${discovered.latency_ms}` : 'idle'} className="conn-art" viewBox="0 0 300 56" fill="none" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                      <g className="conn-art__pc"><rect x="18" y="6" width="52" height="32" rx="5" /><path d="M34 50h20M44 38v12" /></g>
                      <path className="conn-art__line" d="M80 22H220" />
                      <circle className="conn-art__probe" cx="80" cy="22" r="4" />
                      <g className="conn-art__x"><circle cx="150" cy="22" r="11" /><path d="M145 17l10 10M155 17l-10 10" /></g>
                      <g className="conn-art__ok"><circle cx="150" cy="22" r="11" /><path d="M145 22l3.5 3.5L155 18" /></g>
                      <g className="conn-art__srv"><rect x="230" y="4" width="52" height="16" rx="4" /><rect x="230" y="24" width="52" height="16" rx="4" /><path d="M238 12h.01M238 32h.01" /></g>
                    </svg>
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
                  </GroupCard>
                ) : null}
                </div>
              </section>
            )}

            {currentTab ==='voz' && !skeletonTab && (
              <section className="settings-section" aria-labelledby="settings-voz">
                <SectionHead icon="mic" id="settings-voz" title="Voz" lede="Transcrição local da pergunta falada: nada sai do seu computador." />

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

                  {!voiceLoaded ? (
                    <div className="load-wait ui-grid" aria-label="Carregando modelos de voz" role="status">
                      {[0, 1, 2].map((key) => <div key={key} className="ui-card" style={{ padding: 14 }}><SkLines widths={['60%', '82%', '30%']} /></div>)}
                    </div>
                  ) : selectableVoiceModels.length > 0 ? (
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

                <div className="ui-grid voz-grid">
                  {audioLanguageRow && renderSettingRow(audioLanguageRow, audioLanguageOptions)}
                  {otherAudioRows.map((row) => renderSettingRow(row))}
                  <MicTest />
                </div>

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

            {currentTab === 'avancado' && !skeletonTab &&
              (advancedUnlocked ? (
                <AdvancedPane
                  presets={backendSettings?.settings_presets ?? []}
                  rows={advancedRows}
                  catalog={backendSettings?.settings_catalog ?? []}
                  strategy={settingDrafts.default_ask_strategy}
                  hiddenKeys={DESKTOP_HIDDEN_KEYS}
                  applyingPreset={applyingPreset}
                  pendingChanges={pendingChanges}
                  catalogLabel={catalogLabel}
                  renderRow={(row) => renderSettingRow(row)}
                  onApplyPreset={(key) => void handleApplyPreset(key)}
                  onHide={handleHideAdvanced}
                />
              ) : (
                <AdvancedLocked onUnlock={handleUnlockAdvanced} />
              ))}

            {currentTab ==='aparencia' && (
              <>
                <section className="settings-section" aria-labelledby="settings-appearance">
                  <SectionHead icon="contrast" id="settings-appearance" title="Aparência" lede="Tema, cor, letra e movimento. Vale na hora, só neste computador." />
                  <AppearanceFields />
                </section>

                <div className="settings-divider" aria-hidden="true" />

                <section className="settings-section" aria-labelledby="settings-about">
                  <SectionHead icon="info" id="settings-about" title="Sobre" />

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

        {/* Fechar com rascunho pendente: confirma antes de descartar. */}
        {pendingChanges > 0 && isConfirmingClose && (
          <div className="modal__footer settings-savebar" role="region" aria-label="Fechar sem salvar">
            <span className="modal__pending">Fechar sem salvar? As alterações serão descartadas.</span>
            <div className="modal__footer-actions">
              <button type="button" className="btn btn--ghost" onClick={() => setIsConfirmingClose(false)}>
                Continuar editando
              </button>
              <button
                type="button"
                className="btn btn--danger"
                onClick={() => {
                  discardDrafts();
                  setIsConfirmingClose(false);
                  onClose();
                }}
              >
                Descartar alterações
              </button>
            </div>
          </div>
        )}

        {/* Barra de salvar: só existe com alteração pendente (sem "Nenhuma alteração" parado no rodapé). */}
        {pendingChanges > 0 && !isConfirmingClose && (
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
