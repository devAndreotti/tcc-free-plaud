import { act, renderHook } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { CORPUS_CHANGED, CORPUS_PROGRESS_EVENT } from '../lib/corpusEvents';
import { bridge } from '../services/bridge';
import { useIndexJob } from './useIndexJob';

vi.mock('../services/bridge', () => ({
  bridge: { startIndexJob: vi.fn(), getIndexJob: vi.fn(), selectFolder: vi.fn(), startWatcher: vi.fn(), stopWatcher: vi.fn() },
}));

const start = vi.mocked(bridge.startIndexJob);
const poll = vi.mocked(bridge.getIndexJob);
const snapshot = (committed: number, status = 'running') =>
  ({ job_id: 'j1', status, progress: { committed_count: committed } }) as never;

describe('useIndexJob: avisos do corpus durante o job', () => {
  const progress = vi.fn();
  const changed = vi.fn();

  beforeEach(() => {
    vi.useFakeTimers();
    vi.clearAllMocks();
    window.addEventListener(CORPUS_PROGRESS_EVENT, progress);
    window.addEventListener(CORPUS_CHANGED, changed);
    start.mockResolvedValue(snapshot(0));
    // startJob já consulta o job uma vez, logo depois de criá-lo.
    poll.mockResolvedValue(snapshot(0));
  });

  afterEach(() => {
    window.removeEventListener(CORPUS_PROGRESS_EVENT, progress);
    window.removeEventListener(CORPUS_CHANGED, changed);
    vi.useRealTimers();
  });

  const tick = async (next: never) => {
    poll.mockResolvedValue(next);
    await act(async () => { await vi.advanceTimersByTimeAsync(1000); });
  };

  it('avisa só quando um lote novo é gravado; o fim do job continua avisando corpus-changed', async () => {
    const { result } = renderHook(() => useIndexJob());
    await act(async () => { await result.current.startJob('C:\\Vault'); });

    await tick(snapshot(0));
    expect(progress).not.toHaveBeenCalled();

    await tick(snapshot(32));
    expect(progress).toHaveBeenCalledTimes(1);

    await tick(snapshot(32));
    expect(progress).toHaveBeenCalledTimes(1);

    await tick(snapshot(64));
    expect(progress).toHaveBeenCalledTimes(2);
    expect(changed).not.toHaveBeenCalled();

    await tick(snapshot(70, 'completed'));
    expect(progress).toHaveBeenCalledTimes(2);
    expect(changed).toHaveBeenCalledTimes(1);
  });
});
