import { useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { XIcon } from './Icons';
import { useVaultContext } from '../hooks/useVaultContext';
import { bridge, type BackendSettings, type ModelDiscoveryResult, type SettingRow } from '../services/bridge';

// Props do modal de configurações
interface SettingsModalProps {
  isOpen: boolean;
  onClose: () => void;
}

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
  const [showAdvancedSettings, setShowAdvancedSettings] = useState(false);
  const [operationStatus, setOperationStatus] = useState('');

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
      setOperationStatus('Erro ao salvar configurações do backend.');
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

  const renderSettingRow = (row: SettingRow) => (
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

      {row.options.length > 0 ? (
        <select
          className="settings-select settings-control-wide"
          value={settingDrafts[row.key] ?? ''}
          aria-label={row.label}
          onChange={(event) =>
            setSettingDrafts((prev) => ({ ...prev, [row.key]: event.target.value }))
          }
        >
          {row.options.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
      ) : row.value_type === 'bool' ? (
        <select
          className="settings-select settings-control-wide"
          value={settingDrafts[row.key] ?? 'false'}
          aria-label={row.label}
          onChange={(event) =>
            setSettingDrafts((prev) => ({ ...prev, [row.key]: event.target.value }))
          }
        >
          <option value="true">Sim</option>
          <option value="false">Não</option>
        </select>
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

  const simpleRows = backendSettings?.settings_catalog.filter((row) => row.layer === 'simple' && !row.secret) ?? [];
  const advancedRows = backendSettings?.settings_catalog.filter((row) => row.layer === 'advanced' && !row.secret) ?? [];

  // Renderiza diretamente no document.body via Portal.
  // O overlay usa display:flex para centralizar o modal de forma confiável.
  return createPortal(
    <div className="modal-overlay">
      {/* Janela do modal — filho direto do overlay flex */}
      <div
        ref={modalRef}
        className="modal"
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

        {/* Corpo do modal */}
        <div className="modal__body">

          {/* Seção: Vault */}
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

          <div className="settings-divider" aria-hidden="true" />

          <section className="settings-section" aria-labelledby="settings-doctor">
            <h3 id="settings-doctor" className="settings-section__title">
              Doctor
            </h3>
            <div className="settings-item settings-item--stacked">
              <div className="settings-item__info">
                <span className="settings-item__label">
                  status: {backendSettings?.doctor?.status ?? 'indisponível'}
                </span>
                <span className="settings-item__description">
                  checks: {backendSettings?.doctor?.ok_count ?? 0} ok · {backendSettings?.doctor?.warning_count ?? 0} warning · {backendSettings?.doctor?.error_count ?? 0} error · {backendSettings?.doctor?.latency_ms ?? 0} ms
                </span>
              </div>
              {backendSettings?.doctor?.checks.slice(0, 6).map((check) => (
                <span
                  key={check.code}
                  className={check.status === 'ok' ? 'settings-inline-status' : 'settings-warning'}
                >
                  {check.code}: {check.status} - {check.message}
                </span>
              ))}
            </div>
          </section>

          <div className="settings-divider" aria-hidden="true" />

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

          {/* Seção: Backend simples */}
          <section className="settings-section" aria-labelledby="settings-simple">
            <h3 id="settings-simple" className="settings-section__title">
              Simples
            </h3>

            {simpleRows.map(renderSettingRow)}
          </section>

          <div className="settings-divider" aria-hidden="true" />

          <section className="settings-section" aria-labelledby="settings-advanced">
            <div className="settings-section__header">
              <h3 id="settings-advanced" className="settings-section__title">
                Avançado
              </h3>
              <button
                id="settings-advanced-toggle"
                type="button"
                className="vault-picker__btn"
                onClick={() => setShowAdvancedSettings((value) => !value)}
                aria-expanded={showAdvancedSettings}
              >
                {showAdvancedSettings ? 'Ocultar' : 'Mostrar'}
              </button>
            </div>

            {showAdvancedSettings && advancedRows.map(renderSettingRow)}

            <button
              id="btn-save-backend-settings"
              type="button"
              className="vault-picker__btn settings-save-wide"
              onClick={handleSaveBackendSettings}
              disabled={!backendSettings || isSavingBackendSettings}
              aria-label="Salvar configurações do backend"
            >
              {isSavingBackendSettings ? 'Salvando…' : 'Salvar backend'}
            </button>
          </section>

          <div className="settings-divider" aria-hidden="true" />

          {/* Seção: IA */}
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
              {backendSettings && (
                <span className="settings-inline-status">
                  corpus: {backendSettings.notes_count} notas · {backendSettings.sqlite_chunks_count} chunks
                </span>
              )}
            </div>
          </section>

          {operationStatus && (
            <>
              <div className="settings-divider" aria-hidden="true" />
              <p className="settings-inline-status" role="status">
                {operationStatus}
              </p>
            </>
          )}

          <div className="settings-divider" aria-hidden="true" />

          {/* Seção: Aparência */}
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
                <select
                  id="select-theme"
                  className="settings-select"
                  defaultValue="dark"
                  aria-label="Selecionar tema"
                >
                  <option value="dark">Escuro</option>
                  <option value="light" disabled>Claro (em breve)</option>
                </select>
              </div>
            </div>
          </section>

          <div className="settings-divider" aria-hidden="true" />

          {/* Seção: Sobre */}
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
        </div>

        {/* Rodapé do modal */}
        <div className="modal__footer">
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
