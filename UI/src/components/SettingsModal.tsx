import { useEffect, useMemo, useRef, useState, type ComponentType } from 'react';
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
import Select from './Select';
import VaultsTab from './VaultsTab';
import {
  bridge,
  type BackendSettings,
  type ModelDiscoveryResult,
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

// Chaves de preset que não são editáveis e por isso não estão no catálogo.
const PRESET_KEY_LABELS: Record<string, string> = { embedding_model: 'Modelo de embedding' };

const MODEL_STATUS: Record<string, string> = { offline: 'offline', unauthorized: 'sem autorização', error: 'erro' };

export type SettingsTab = 'geral' | 'vaults' | 'ia' | 'voz' | 'avancado' | 'aparencia';

const SETTINGS_TABS: { id: SettingsTab; label: string }[] = [
  { id: 'geral', label: 'Geral' },
  { id: 'vaults', label: 'Vaults' },
  { id: 'ia', label: 'IA' },
  { id: 'voz', label: 'Voz' },
  { id: 'avancado', label: 'Avançado' },
  { id: 'aparencia', label: 'Aparência' },
];

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
  const [isSavingBackendSettings, setIsSavingBackendSettings] = useState(false);
  const [applyingPreset, setApplyingPreset] = useState('');
  const [isTestingProvider, setIsTestingProvider] = useState(false);
  const [isListingModels, setIsListingModels] = useState(false);
  const [modelDiscovery, setModelDiscovery] = useState<ModelDiscoveryResult | null>(null);
  const [activeTab, setActiveTab] = useState<SettingsTab>('voz');
  const [operationStatus, setOperationStatus] = useState('');
  const [voiceModels, setVoiceModels] = useState<VoiceModelInfo[]>([]);
  const [downloadJob, setDownloadJob] = useState<VoiceModelDownloadSnapshot | null>(null);
  const [downloadError, setDownloadError] = useState('');
  const [theme, setTheme] = useState<ThemeChoice>(readThemeChoice);

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
    if (!isOpen) return;
    bridge.getBackendSettings()
      .then((settings) => {
        setBackendSettings(settings);
        setSettingDrafts(draftsFrom(settings));
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
      setOperationStatus(error instanceof Error ? error.message : 'Falha ao rodar o diagnóstico.');
    } finally {
      setIsRunningDoctor(false);
    }
  };

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

  const handleSaveApiKey = async () => {
    if (isSavingApiKey) return;
    setIsSavingApiKey(true);
    try {
      const result = await bridge.saveApiKey(apiKey);
      setApiKey('');
      setOperationStatus(result.configured ? `API key salva em ${result.local_env_path}` : `API key removida de ${result.local_env_path}`);
      const settings = await bridge.getBackendSettings();
      setBackendSettings(settings);
    } catch (error) {
      console.error('[SettingsModal] Erro ao salvar API key:', error);
      setOperationStatus('Erro ao salvar API key.');
    } finally {
      setIsSavingApiKey(false);
    }
  };

  const handleSaveBackendSettings = async () => {
    if (!backendSettings || isSavingBackendSettings) return;
    setIsSavingBackendSettings(true);
    try {
      const editableRows = backendSettings.settings_catalog.filter((row) => !row.secret);
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
      setOperationStatus('Configurações salvas.');
    } catch (error) {
      console.error('[SettingsModal] Erro ao salvar settings do backend:', error);
      setOperationStatus(
        error instanceof Error
          ? `Erro ao salvar configurações: ${error.message}`
          : 'Erro ao salvar configurações do backend.'
      );
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
      setOperationStatus(`Preset ${result.preset.label} aplicado.`);
    } catch (error) {
      console.error('[SettingsModal] Erro ao aplicar preset:', error);
      setOperationStatus('Erro ao aplicar preset.');
    } finally {
      setApplyingPreset('');
    }
  };

  const handleTestProvider = async () => {
    if (isTestingProvider) return;
    setIsTestingProvider(true);
    try {
      const result = await bridge.testAnswerProvider();
      setOperationStatus(
        result.error
          ? `O teste do ${result.provider} falhou: ${result.error}`
          : `${result.provider} respondeu em ${result.latency_ms} ms.`
      );
    } catch (error) {
      console.error('[SettingsModal] Erro ao testar provider:', error);
      setOperationStatus('Erro ao testar provider.');
    } finally {
      setIsTestingProvider(false);
    }
  };

  const handleListModels = async () => {
    if (isListingModels) return;
    setIsListingModels(true);
    setOperationStatus('');
    try {
      // O resultado aparece logo abaixo dos botões; a barra de status fica para erros.
      setModelDiscovery(await bridge.listAnswerModels());
    } catch (error) {
      console.error('[SettingsModal] Erro ao listar modelos:', error);
      setOperationStatus('Erro ao listar modelos.');
    } finally {
      setIsListingModels(false);
    }
  };

  const handleSelectModel = (modelId: string) => {
    setSettingDrafts((prev) => ({ ...prev, answer_model: modelId }));
    setOperationStatus(`Modelo ${modelId} escolhido. Clique em Salvar para gravar.`);
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

  const renderSettingRow = (row: SettingRow, overrideOptions?: { value: string; label: string; disabled?: boolean }[]) => (
    <div key={row.key} className="settings-item settings-item--stacked">
      <div className="settings-item__info">
        <span className="settings-item__label">{row.label}</span>
        <span className="settings-item__description">
          {row.description}
          {row.recommended !== null && ` · recomendado: ${row.recommended}`}
        </span>
        {row.warning && (
          <span className="settings-warning">{row.warning}</span>
        )}
      </div>

      {(overrideOptions ?? row.options).length > 0 ? (
        <Select
          className="settings-control-wide"
          value={settingDrafts[row.key] ?? ''}
          options={overrideOptions ?? row.options}
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
    </div>
  );

  if (!isOpen) return null;

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
    backendSettings?.settings_catalog.find((row) => row.key === key)?.label ?? PRESET_KEY_LABELS[key] ?? key;
  // Modelo, URL, API key, Testar e Listar só existem para provedores generativos.
  const isGenerative = (settingDrafts.answer_provider || backendSettings?.answer_provider || 'extractive') !== 'extractive';
  const iaCatalogRows = backendSettings?.settings_catalog.filter((row) => IA_CATALOG_KEYS.includes(row.key) && !row.secret) ?? [];
  const advancedRows = backendSettings?.settings_catalog.filter(
    (row) => !row.secret && row.group !== 'Áudio' && !IA_CATALOG_KEYS.includes(row.key)
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
            {SETTINGS_TABS.map((tab) => (
              <button
                key={tab.id}
                type="button"
                className={`settings-nav__item${activeTab === tab.id ? ' settings-nav__item--active' : ''}`}
                aria-current={activeTab === tab.id ? 'page' : undefined}
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
          </nav>

          <div className="settings-panel">
            {activeTab === 'geral' && (
              <section className="settings-section" aria-labelledby="settings-doctor">
                <h3 id="settings-doctor" className="settings-section__title">
                  Diagnóstico
                </h3>
                {backendSettings?.doctor ? (
                  <>
                    <div className={`doctor__summary doctor__summary--${backendSettings.doctor.status}`}>
                      <span className="doctor__summary-icon" aria-hidden="true">
                        {backendSettings.doctor.status === 'ok' ? <CheckCircleIcon size={17} /> : <AlertTriangleIcon size={17} />}
                      </span>
                      <div>
                        <b>
                          {backendSettings.doctor.error_count > 0
                            ? `${backendSettings.doctor.error_count} ${backendSettings.doctor.error_count === 1 ? 'verificação com erro' : 'verificações com erro'}`
                            : backendSettings.doctor.warning_count > 0
                              ? `${backendSettings.doctor.warning_count} ${backendSettings.doctor.warning_count === 1 ? 'aviso' : 'avisos'}`
                              : 'Tudo certo'}
                        </b>
                        <span className="mono">
                          {backendSettings.doctor.ok_count} ok · {backendSettings.doctor.warning_count} {backendSettings.doctor.warning_count === 1 ? 'aviso' : 'avisos'} · {backendSettings.doctor.error_count} {backendSettings.doctor.error_count === 1 ? 'erro' : 'erros'} · {backendSettings.doctor.latency_ms} ms
                        </span>
                      </div>
                      <button type="button" className="btn btn--sm" onClick={handleRerunDoctor} disabled={isRunningDoctor}>
                        <RefreshIcon size={14} />
                        {isRunningDoctor ? 'Verificando…' : 'Verificar de novo'}
                      </button>
                    </div>
                    <ul className="doctor__checks">
                      {[...backendSettings.doctor.checks]
                        .sort((a, b) => (a.status === 'ok' ? 1 : 0) - (b.status === 'ok' ? 1 : 0))
                        .map((check) => (
                          <li key={check.code} className={`doctor__check doctor__check--${check.status}`}>
                            {check.status === 'ok' ? <CheckCircleIcon size={15} /> : check.status === 'warning' ? <AlertTriangleIcon size={15} /> : <XCircleIcon size={15} />}
                            <div>
                              <code>{check.code}</code>
                              <span className="doctor__msg">{check.message}</span>
                              {check.action && check.status !== 'ok' && <span className="doctor__action">{check.action}</span>}
                            </div>
                            {check.latency_ms != null && <span className="doctor__lat mono">{check.latency_ms} ms</span>}
                          </li>
                        ))}
                    </ul>
                    <p className="settings-inline-status">
                      Corpus: {backendSettings.notes_count.toLocaleString('pt-BR')} notas · {backendSettings.sqlite_chunks_count.toLocaleString('pt-BR')} chunks no SQLite · {backendSettings.vector_chunks_count.toLocaleString('pt-BR')} vetores no Chroma
                    </p>
                  </>
                ) : (
                  <div className="settings-item settings-item--stacked" aria-label="Carregando diagnóstico">
                    <div className="skeleton-box skeleton-box--path" />
                    <div className="skeleton-box skeleton-box--meta" />
                  </div>
                )}
              </section>
            )}

            {activeTab === 'vaults' && <VaultsTab onOpenQueue={() => onOpenQueue?.()} />}

            {activeTab === 'ia' && (
              <section className="settings-section" aria-labelledby="settings-ai">
                <h3 id="settings-ai" className="settings-section__title">
                  IA
                </h3>

                {iaCatalogRows.filter((row) => isGenerative || row.key === 'answer_provider').map((row) => renderSettingRow(row))}

                {isGenerative ? (
                    <div className="settings-item settings-item--stacked">
                    <div className="settings-item__info">
                      <span className="settings-item__label">API key</span>
                      <span className="settings-item__description">
                        {backendSettings?.answer_api_key_configured ? 'Configurada no .env local.' : 'Ausente.'} Teste o provedor ou liste os modelos dele.
                      </span>
                    </div>

                    <div className="vault-picker" role="group" aria-label="Salvar API key local">
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
                        onClick={handleSaveApiKey}
                        disabled={isSavingApiKey}
                        aria-label="Salvar API key"
                      >
                        {isSavingApiKey ? 'Salvando…' : 'Salvar'}
                      </button>
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
                    {modelDiscovery && (
                      <div className="settings-item settings-item--stacked" aria-live="polite">
                        <span className="settings-inline-status">
                          {modelDiscovery.models.length} {modelDiscovery.models.length === 1 ? 'modelo' : 'modelos'} no{' '}
                          {modelDiscovery.provider} · {modelDiscovery.latency_ms} ms{modelDiscovery.cached ? ' · em cache' : ''}
                          {modelDiscovery.status !== 'ok' && ` · ${MODEL_STATUS[modelDiscovery.status] ?? modelDiscovery.status}`}
                        </span>
                        {modelDiscovery.message && (
                          <span className="settings-warning">{modelDiscovery.message}</span>
                        )}
                        {modelDiscovery.models.length > 0 && (
                          <ul className="settings-model-list" aria-label="Modelos encontrados">
                            {modelDiscovery.models.map((model) => (
                              <li key={model.id} className="settings-model-list__item">
                                <button
                                  type="button"
                                  className="btn btn--sm settings-model-option"
                                  onClick={() => handleSelectModel(model.id)}
                                  aria-label={`Selecionar ${model.label}`}
                                >
                                  {model.label}
                                </button>
                              </li>
                            ))}
                          </ul>
                        )}
                      </div>
                    )}
                  </div>
                ) : (
                  <p className="settings-inline-status">
                    O extractive responde só com trechos das notas: não usa LLM, modelo nem API key.
                  </p>
                )}
              </section>
            )}

            {activeTab === 'voz' && (
              <section className="settings-section" aria-labelledby="settings-voz">
                <h3 id="settings-voz" className="settings-section__title">
                  Voz
                </h3>

                <div className="settings-item settings-item--stacked">
                  <div className="settings-item__info">
                    <span className="settings-item__label">
                      {audioModelRow?.label ?? 'Modelo de transcrição (voz)'}
                    </span>
                    <span className="settings-item__description">
                      {audioModelRow?.description ?? 'Modelo local usado para transcrever o áudio gravado no chat.'}
                      {audioModelRow?.recommended !== null && audioModelRow?.recommended !== undefined &&
                        ` · recomendado: ${audioModelRow.recommended}`}
                    </span>
                  </div>

                  {selectableVoiceModels.length > 0 ? (
                    <div className="voice-models" role="radiogroup" aria-label={audioModelRow?.label ?? 'Modelo de transcrição (voz)'}>
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
                    </div>
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

            {activeTab === 'avancado' && (
              <>
                <section className="settings-section" aria-labelledby="settings-presets">
                  <h3 id="settings-presets" className="settings-section__title">
                    Presets
                  </h3>
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
                  {advancedRows.map((row) => renderSettingRow(row))}
                </section>
              </>
            )}

            {activeTab === 'aparencia' && (
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

        {operationStatus && (
          <p className="settings-inline-status settings-status-bar" role="status">
            {operationStatus}
          </p>
        )}

        {/* Rodapé do modal */}
        <div className="modal__footer">
          <span className="modal__pending" aria-live="polite">
            {pendingChanges > 0 ? (
              <>
                <span className="modal__pending-dot" aria-hidden="true" />
                {pendingChanges} {pendingChanges === 1 ? 'alteração não salva' : 'alterações não salvas'}
              </>
            ) : (
              'Nenhuma alteração'
            )}
          </span>
          <div className="modal__footer-actions">
            <button id="btn-settings-close" type="button" className="btn btn--ghost" onClick={onClose}>
              Cancelar
            </button>
            <button
              id="btn-save-backend-settings"
              type="button"
              className="btn btn--primary"
              onClick={handleSaveBackendSettings}
              disabled={!backendSettings || isSavingBackendSettings}
              aria-label="Salvar configurações do backend"
            >
              {isSavingBackendSettings ? 'Salvando…' : 'Salvar'}
            </button>
          </div>
        </div>
      </div>
    </div>,
    document.body
  );
};

export default SettingsModal;
