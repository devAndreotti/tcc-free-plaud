import { afterEach, describe, expect, it } from 'vitest';
import { bridge } from './bridge';

describe('bridge watcher (mock mode)', () => {
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
      'listNotes',
      'getNoteDetail',
      'deleteNote',
      'reindexNote',
      'selectBenchmarkSuite',
      'runBenchmarkCompare',
    ]);
  });
});
