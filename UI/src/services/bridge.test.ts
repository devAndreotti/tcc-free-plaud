import { afterEach, describe, expect, it } from 'vitest';
import { bridge } from './bridge';

describe('bridge watcher and audio (mock mode)', () => {
  afterEach(async () => {
    await bridge.stopWatcher();
  });

  it('reports inactive status before starting', async () => {
    expect(await bridge.getWatcherStatus()).toEqual({ active: false, directory: null });
  });

  it('starts watcher and reflects active status', async () => {
    const result = await bridge.startWatcher('C:\\Vault');
    expect(result).toEqual({ ok: true, active: true, directory: 'C:\\Vault' });
    expect(await bridge.getWatcherStatus()).toEqual({ active: true, directory: 'C:\\Vault' });
  });

  it('stops watcher and clears directory', async () => {
    await bridge.startWatcher('C:\\Vault');
    const result = await bridge.stopWatcher();
    expect(result).toEqual({ ok: true, active: false, directory: null });
    expect(await bridge.getWatcherStatus()).toEqual({ active: false, directory: null });
  });

  it('returns empty ingestion events by default', async () => {
    expect(await bridge.pollWatcherEvents()).toEqual([]);
  });

  it('exercises audio capture mock methods', async () => {
    const started = await bridge.startAudioCapture();
    expect(started.status).toBe('recording');

    const polled = await bridge.getAudioCapture(started.job_id);
    expect(polled.job_id).toBe(started.job_id);

    const stopped = await bridge.stopAudioCapture(started.job_id);
    expect(stopped.status).toBe('completed');
    expect(stopped.result?.text).toBeTruthy();

    const cancelled = await bridge.cancelAudioCapture(started.job_id);
    expect(cancelled.status).toBe('cancelled');
  });

  it('exercises voice model download and catalog mock methods', async () => {
    const models = await bridge.listVoiceModels();
    expect(models.length).toBeGreaterThan(0);

    const started = await bridge.startVoiceModelDownload('whisper-small');
    expect(started.model_id).toBe('whisper-small');
    expect(started.status).toBe('downloading');

    const polled = await bridge.getVoiceModelDownload(started.job_id);
    expect(polled.status).toBe('completed');

    const cancelled = await bridge.cancelVoiceModelDownload(started.job_id);
    expect(cancelled.status).toBe('cancelled');
  });

  it('exercises batch saveBackendSettings mock method', async () => {
    const settings = await bridge.saveBackendSettings({ audio_language: 'pt' });
    expect(settings).toBeDefined();
    expect(settings.settings_catalog.length).toBeGreaterThan(0);
  });
});

describe('isDesktopApp (lazy PyWebView detection)', () => {
  afterEach(() => {
    delete (window as unknown as { pywebview?: unknown }).pywebview;
  });

  it('falls back to mock when window.pywebview is absent', async () => {
    expect(await bridge.selectFolder()).toContain('mock');
  });

  it('delegates every bridge method to window.pywebview.api once it becomes available', async () => {
    const calls: string[] = [];
    const stubApi = new Proxy(
      {},
      {
        get: (_target, prop: string) => {
          return (...args: unknown[]) => {
            calls.push(prop);
            return Promise.resolve(args[0] ?? { ok: true, active: false, directory: null });
          };
        },
      }
    );
    (window as unknown as { pywebview: { api: unknown } }).pywebview = { api: stubApi };

    await bridge.sendMessage('oi');
    await bridge.selectFolder();
    await bridge.scanVault('C:\\Vault');
    await bridge.saveVaultPath('C:\\Vault');
    await bridge.loadVaultPath();
    await bridge.indexVault('C:\\Vault');
    await bridge.startIndexJob('C:\\Vault', false);
    await bridge.getIndexJob('job-1');
    await bridge.cancelIndexJob('job-1');
    await bridge.startAudioCapture();
    await bridge.getAudioCapture('job-audio-1');
    await bridge.stopAudioCapture('job-audio-1');
    await bridge.cancelAudioCapture('job-audio-1');
    await bridge.listVoiceModels();
    await bridge.startVoiceModelDownload('whisper-small');
    await bridge.getVoiceModelDownload('job-dl-1');
    await bridge.cancelVoiceModelDownload('job-dl-1');
    await bridge.startWatcher('C:\\Vault');
    await bridge.stopWatcher();
    await bridge.getWatcherStatus();
    await bridge.pollWatcherEvents();
    await bridge.getBackendSettings();
    await bridge.getDoctor();
    await bridge.listSettingsPresets();
    await bridge.previewSettingsPreset('preset');
    await bridge.applySettingsPreset('preset');
    await bridge.testAnswerProvider();
    await bridge.listAnswerModels();
    await bridge.saveApiKey('key');
    await bridge.saveBackendSetting('key', 'value');
    await bridge.saveBackendSettings({ audio_language: 'pt' });
    await bridge.listNotes();
    await bridge.getNoteDetail('note-1');
    await bridge.deleteNote('note-1', 'APAGAR');
    await bridge.reindexNote('note-1');
    await bridge.selectBenchmarkSuite();
    await bridge.runBenchmarkCompare('suite.json');

    expect(calls).toEqual([
      'sendMessage',
      'selectFolder',
      'scanVault',
      'saveVaultPath',
      'loadVaultPath',
      'indexVault',
      'startIndexJob',
      'getIndexJob',
      'cancelIndexJob',
      'startAudioCapture',
      'getAudioCapture',
      'stopAudioCapture',
      'cancelAudioCapture',
      'listVoiceModels',
      'startVoiceModelDownload',
      'getVoiceModelDownload',
      'cancelVoiceModelDownload',
      'startWatcher',
      'stopWatcher',
      'getWatcherStatus',
      'pollWatcherEvents',
      'getBackendSettings',
      'getDoctor',
      'listSettingsPresets',
      'previewSettingsPreset',
      'applySettingsPreset',
      'testAnswerProvider',
      'listAnswerModels',
      'saveApiKey',
      'saveBackendSetting',
      'saveBackendSettings',
      'listNotes',
      'getNoteDetail',
      'deleteNote',
      'reindexNote',
      'selectBenchmarkSuite',
      'runBenchmarkCompare',
    ]);
  });
});

describe('askCorpus', () => {
  afterEach(() => {
    delete (window as unknown as { pywebview?: unknown }).pywebview;
  });

  it('usa askCorpus do backend quando existe, repassando a estratégia', async () => {
    const calls: unknown[][] = [];
    (window as unknown as { pywebview: { api: unknown } }).pywebview = {
      api: {
        askCorpus: (...args: unknown[]) => {
          calls.push(args);
          return Promise.resolve({ query: 'q', status: 'answer', claims: [], citations: [] });
        },
      },
    };
    await bridge.askCorpus('q', 'lexical');
    expect(calls).toEqual([['q', 'lexical']]);
  });

  it('cai para sendMessage quando o backend não tem askCorpus', async () => {
    (window as unknown as { pywebview: { api: unknown } }).pywebview = {
      api: { sendMessage: () => Promise.resolve('texto simples') },
    };
    const result = await bridge.askCorpus('q');
    expect(result.answer).toBe('texto simples');
    expect(result.claims).toEqual([]);
    expect(result.no_answer).toBe(false);
  });
});
