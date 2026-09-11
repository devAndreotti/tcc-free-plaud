import { useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { XIcon } from './Icons';
import Select from './Select';
import { useVaultContext } from '../hooks/useVaultContext';
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
}

// Chaves do catálogo que pertencem à aba IA (o resto de layer não-secreto vai para Avançado)
const IA_CATALOG_KEYS = ['answer_provider', 'answer_model', 'answer_base_url'];

type SettingsTab = 'geral' | 'vault' | 'ia' | 'voz' | 'avancado' | 'aparencia';

const SETTINGS_TABS: { id: SettingsTab; label: string }[] = [
  { id: 'geral', label: 'Geral' },
  { id: 'vault', label: 'Vault' },
  { id: 'ia', label: 'IA' },
  { id: 'voz', label: 'Voz' },
  { id: 'avancado', label: 'Avançado' },
  { id: 'aparencia', label: 'Aparência' },
];

const SettingsModal = ({ isOpen, onClose }: SettingsModalProps) => {
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
  const [isIndexingVault, setIsIndexingVault] = useState(false);
  const [activeTab, setActiveTab] = useState<SettingsTab>('voz');
  const [operationStatus, setOperationStatus] = useState('');
  const [voiceModels, setVoiceModels] = useState<VoiceModelInfo[]>([]);
  const [downloadJob, setDownloadJob] = useState<VoiceModelDownloadSnapshot | null>(null);
  const [downloadError, setDownloadError] = useState('');
  const [theme, setTheme] = useState('dark');

  // Consome o contexto global do vault
  const { vaultPath, selectVault, isScanning } = useVaultContext();
  const isSelectingVault = isScanning;

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

  useEffect(() => {
    if (!isOpen) return;
    bridge.getBackendSettings()
      .then((settings) => {
        setBackendSettings(settings);
        setSettingDrafts(
          Object.fromEntries(
            settings.settings_catalog
              .filter((row) => !row.secret)
              .map((row) => [row.key, row.value === null ? '' : String(row.value)])
          )
        );
      })
      .catch((error) => {
        console.error('[SettingsModal] Erro ao carregar settings do backend:', error);
      });
  }, [isOpen]);

  // Carrega o catálogo de modelos de voz (com estado instalado) quando o modal abre.
  useEffect(() => {
    if (!isOpen) return;
    bridge.listVoiceModels()
      .then(setVoiceModels)
      .catch((error) => {
        console.error('[SettingsModal] Erro ao listar modelos de voz:', error);
      });
  }, [isOpen]);

  const selectedVoiceModel = voiceModels.find((model) => model.id === settingDrafts.audio_model) ?? null;

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

  // Chama o contexto para abrir o seletor e escanear automaticamente
  const handleSelectVault = async () => {
    await selectVault();
  };

  const handleIndexVault = async () => {
    if (!vaultPath || isIndexingVault) return;
    setIsIndexingVault(true);
    setOperationStatus('Indexando corpus...');
    try {
      const result = await bridge.indexVault(vaultPath);
      setOperationStatus(
        `Indexação: ${result.status} | encontrados=${result.total_found} | indexados=${result.indexed_count} | inalterados=${result.unchanged_count} | falhas=${result.failed_count}`
      );
      const settings = await bridge.getBackendSettings();
      setBackendSettings(settings);
      setSettingDrafts(
        Object.fromEntries(
          settings.settings_catalog
            .filter((row) => !row.secret)
            .map((row) => [row.key, row.value === null ? '' : String(row.value)])
        )
      );
    } catch (error) {
      console.error('[SettingsModal] Erro ao indexar vault:', error);
      setOperationStatus('Erro ao indexar corpus.');
    } finally {
      setIsIndexingVault(false);
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
      await Promise.all(
        editableRows.map((row) =>
          bridge.saveBackendSetting(row.key, settingDrafts[row.key] ?? '')
        )
      );
      const settings = await bridge.getBackendSettings();
      setBackendSettings(settings);
      setSettingDrafts(
        Object.fromEntries(
          settings.settings_catalog
            .filter((row) => !row.secret)
            .map((row) => [row.key, row.value === null ? '' : String(row.value)])
        )
      );
      setOperationStatus('Configurações do backend salvas.');
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
      setOperationStatus(`Preset ${result.preset.key} aplicado.`);
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
        `Provider: ${result.provider} | status=${result.status} | latencia_ms=${result.latency_ms}${result.error ? ` | erro=${result.error}` : ''}`
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
    setOperationStatus('Listando modelos do provider...');
    try {
      const result = await bridge.listAnswerModels();
      setModelDiscovery(result);
      const messageSuffix = result.message ? ` | ${result.message}` : '';
      setOperationStatus(
        `Modelos: ${result.status} | provider=${result.provider} | encontrados=${result.models.length} | latencia_ms=${result.latency_ms}${messageSuffix}`
      );
    } catch (error) {
      console.error('[SettingsModal] Erro ao listar modelos:', error);
      setOperationStatus('Erro ao listar modelos.');
    } finally {
      setIsListingModels(false);
    }
  };

  const handleSelectModel = (modelId: string) => {
    setSettingDrafts((prev) => ({ ...prev, answer_model: modelId }));
    setOperationStatus(`Modelo selecionado no draft: ${modelId}. Clique Salvar backend para gravar.`);
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
  const iaCatalogRows = backendSettings?.settings_catalog.filter((row) => IA_CATALOG_KEYS.includes(row.key) && !row.secret) ?? [];
  const advancedRows = backendSettings?.settings_catalog.filter(
    (row) => !row.secret && row.group !== 'Áudio' && !IA_CATALOG_KEYS.includes(row.key)
  ) ?? [];

  // Renderiza diretamente no document.body via Portal.
  // O overlay usa display:flex para centralizar o modal de forma confiável.
  return createPortal(
    <div className="modal-overlay">
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
                {tab.label}
              </button>
            ))}
          </nav>

          <div className="settings-panel">
            {activeTab === 'geral' && (
              <section className="settings-section" aria-labelledby="settings-doctor">
                <h3 id="settings-doctor" className="settings-section__title">
                  Doctor
                </h3>
                {backendSettings ? (
                  <div className="settings-item settings-item--stacked">
                    <div className="settings-item__info">
                      <span className="settings-item__label">
                        status: {backendSettings.doctor?.status ?? 'indisponível'}
                      </span>
                      <span className="settings-item__description">
                        checks: {backendSettings.doctor?.ok_count ?? 0} ok · {backendSettings.doctor?.warning_count ?? 0} warning · {backendSettings.doctor?.error_count ?? 0} error · {backendSettings.doctor?.latency_ms ?? 0} ms
                      </span>
                    </div>
                    {backendSettings.doctor?.checks.slice(0, 6).map((check) => (
                      <span
                        key={check.code}
                        className={check.status === 'ok' ? 'settings-inline-status' : 'settings-warning'}
                      >
                        {check.code}: {check.status} - {check.message}
                      </span>
                    ))}
                    <span className="settings-inline-status">
                      corpus: {backendSettings.notes_count} notas · {backendSettings.sqlite_chunks_count} chunks
                    </span>
                  </div>
                ) : (
                  <div className="settings-item settings-item--stacked" aria-label="Carregando diagnóstico">
                    <div className="skeleton-box skeleton-box--path" />
                    <div className="skeleton-box skeleton-box--meta" />
                  </div>
                )}
              </section>
            )}

            {activeTab === 'vault' && (
              <section className="settings-section" aria-labelledby="settings-vault">
                <h3 id="settings-vault" className="settings-section__title">
                  Vault
                </h3>

                <div className="settings-item" style={{ flexDirection: 'column', alignItems: 'flex-start' }}>
                  <div className="settings-item__info">
                    <span className="settings-item__label">Pasta de destino</span>
                    <span className="settings-item__description">
                      Diretório onde os arquivos gerados serão salvos
                    </span>
                  </div>

                  {/* Campo de caminho + botão de seleção */}
                  <div className="vault-picker" role="group" aria-label="Selecionar pasta de destino">
                    <input
                      id="input-vault-path"
                      type="text"
                      className="vault-picker__input"
                      value={vaultPath}
                      placeholder="Nenhuma pasta selecionada"
                      readOnly
                      aria-label="Caminho da pasta de destino"
                      title={vaultPath || 'Nenhuma pasta selecionada'}
                    />
                    <button
                      id="btn-select-vault"
                      type="button"
                      className="vault-picker__btn"
                      onClick={handleSelectVault}
                      disabled={isSelectingVault}
                      aria-label="Selecionar pasta de destino"
                    >
                      {isSelectingVault ? 'Selecionando…' : 'Selecionar'}
                    </button>
                    <button
                      id="btn-index-vault"
                      type="button"
                      className="vault-picker__btn"
                      onClick={handleIndexVault}
                      disabled={!vaultPath || isIndexingVault}
                      aria-label="Indexar corpus"
                    >
                      {isIndexingVault ? 'Indexando…' : 'Indexar'}
                    </button>
                  </div>
                </div>
              </section>
            )}

            {activeTab === 'ia' && (
              <section className="settings-section" aria-labelledby="settings-ai">
                <h3 id="settings-ai" className="settings-section__title">
                  IA
                </h3>

                <div className="settings-item" style={{ flexDirection: 'column', alignItems: 'flex-start' }}>
                  <div className="settings-item__info">
                    <span className="settings-item__label">API key</span>
                    <span className="settings-item__description">
                      {backendSettings?.answer_api_key_configured ? 'Configurada' : 'Ausente'} · {backendSettings?.answer_provider ?? 'extractive'} · {backendSettings?.answer_model ?? 'modelo local'}
                    </span>
                  </div>

                  <div className="vault-picker" role="group" aria-label="Salvar API key local">
                    <input
                      id="input-api-key"
                      type="password"
                      className="vault-picker__input"
                      value={apiKey}
                      placeholder="FREE_PLAUD_ANSWER_API_KEY"
                      aria-label="API key"
                      onChange={(event) => setApiKey(event.target.value)}
                    />
                    <button
                      id="btn-save-api-key"
                      type="button"
                      className="vault-picker__btn"
                      onClick={handleSaveApiKey}
                      disabled={isSavingApiKey}
                      aria-label="Salvar API key"
                    >
                      {isSavingApiKey ? 'Salvando…' : 'Salvar'}
                    </button>
                    <button
                      id="btn-test-provider"
                      type="button"
                      className="vault-picker__btn"
                      onClick={handleTestProvider}
                      disabled={isTestingProvider}
                      aria-label="Testar provider"
                    >
                      {isTestingProvider ? 'Testando…' : 'Testar'}
                    </button>
                    <button
                      id="btn-list-models"
                      type="button"
                      className="vault-picker__btn"
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
                        modelos: {modelDiscovery.status} · {modelDiscovery.provider} · {modelDiscovery.latency_ms} ms
                        {modelDiscovery.cached ? ' · cache' : ''}
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
                                className="vault-picker__btn settings-model-option"
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

                {iaCatalogRows.map((row) => renderSettingRow(row))}
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

                  <Select
                    className="settings-control-wide"
                    value={settingDrafts.audio_model ?? ''}
                    ariaLabel={audioModelRow?.label ?? 'Modelo de transcrição (voz)'}
                    options={
                      voiceModels.length > 0
                        ? voiceModels.map((model) => ({
                            value: model.id,
                            label: model.label,
                            hint: model.installed
                              ? 'instalado'
                              : `${(model.size_bytes / (1024 * 1024)).toFixed(0)} MB`,
                          }))
                        : (audioModelRow?.options ?? [])
                    }
                    onChange={(value) => {
                      const nextModel = voiceModels.find((model) => model.id === value);
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
                    }}
                  />

                  {selectedVoiceModel && (
                    <div className="settings-item settings-item--stacked" aria-live="polite">
                      <span className="settings-inline-status">
                        {selectedVoiceModel.description} · {selectedVoiceModel.speed_tier ?? '?'} ·{' '}
                        {selectedVoiceModel.quality_tier ?? '?'} ·{' '}
                        {(selectedVoiceModel.size_bytes / (1024 * 1024)).toFixed(0)} MB
                      </span>

                      {selectedVoiceModel.installed ? (
                        <span className="settings-inline-status">Modelo instalado.</span>
                      ) : downloadJob && downloadJob.model_id === selectedVoiceModel.id && !['completed', 'failed', 'cancelled'].includes(downloadJob.status) ? (
                        <div className="settings-item settings-item--stacked">
                          <span className="settings-inline-status">
                            {downloadJob.status === 'verifying'
                              ? 'Verificando arquivos baixados...'
                              : `Baixando... ${(downloadJob.bytes_completed / (1024 * 1024)).toFixed(0)} / ${(downloadJob.bytes_total / (1024 * 1024)).toFixed(0)} MB`}
                          </span>
                          <div className="queue-panel__progress" role="progressbar" aria-label="Progresso do download">
                            <div
                              className="queue-panel__progress-bar"
                              style={{
                                width: `${downloadJob.bytes_total > 0 ? Math.min(100, (downloadJob.bytes_completed / downloadJob.bytes_total) * 100) : 0}%`,
                              }}
                            />
                          </div>
                          <button
                            type="button"
                            className="vault-picker__btn"
                            onClick={handleCancelVoiceModelDownload}
                          >
                            Cancelar download
                          </button>
                        </div>
                      ) : (
                        <div className="settings-item settings-item--stacked">
                          {downloadJob?.model_id === selectedVoiceModel.id && downloadJob.status === 'failed' && (
                            <span className="settings-warning">
                              {downloadJob.message ?? 'Falha ao baixar o modelo.'}
                            </span>
                          )}
                          {downloadError && <span className="settings-warning">{downloadError}</span>}
                          <button
                            type="button"
                            className="vault-picker__btn"
                            onClick={() => handleDownloadVoiceModel(selectedVoiceModel.id)}
                          >
                            {downloadJob?.model_id === selectedVoiceModel.id && downloadJob.status === 'failed'
                              ? 'Tentar novamente'
                              : 'Baixar modelo'}
                          </button>
                        </div>
                      )}
                    </div>
                  )}
                </div>

                {audioLanguageRow && renderSettingRow(audioLanguageRow, audioLanguageOptions)}
                {otherAudioRows.map((row) => renderSettingRow(row))}
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
                        <span className="settings-inline-status">
                          {Object.entries(preset.values).map(([key, value]) => `${key}=${String(value)}`).join(' · ')}
                        </span>
                      </div>
                      <button
                        type="button"
                        className="vault-picker__btn settings-save-wide"
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
                        onChange={setTheme}
                        ariaLabel="Selecionar tema"
                        options={[
                          { value: 'dark', label: 'Escuro' },
                          { value: 'light', label: 'Claro (em breve)', disabled: true },
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
                      <span className="settings-item__label">Assistente IA</span>
                      <span className="settings-item__description">
                        Interface de chat com inteligência artificial
                      </span>
                    </div>
                    <span className="settings-badge">v0.1.0</span>
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
          <button
            id="btn-save-backend-settings"
            type="button"
            className="btn-modal-primary"
            onClick={handleSaveBackendSettings}
            disabled={!backendSettings || isSavingBackendSettings}
            aria-label="Salvar configurações do backend"
          >
            {isSavingBackendSettings ? 'Salvando…' : 'Salvar configurações'}
          </button>
          <button
            id="btn-settings-close"
            type="button"
            className="btn-modal-primary"
            onClick={onClose}
          >
            Fechar
          </button>
        </div>
      </div>
    </div>,
    document.body
  );
};

export default SettingsModal;
