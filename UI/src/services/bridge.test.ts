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