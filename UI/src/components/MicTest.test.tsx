import { act, cleanup, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { bridge, type AudioJobSnapshot } from '../services/bridge';
import MicTest from './MicTest';

const snapshot = (level: number, status = 'recording'): AudioJobSnapshot => ({
  job_id: 'mic-1', status, source_path: '', samples_captured: 0, level, error_code: null, message: null, result: null,
});

describe('MicTest', () => {
  afterEach(() => {
    cleanup();
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  const run = async (levels: number[]) => {
    vi.useFakeTimers();
    vi.spyOn(bridge, 'startAudioCapture').mockResolvedValue(snapshot(0));
    let call = 0;
    vi.spyOn(bridge, 'getAudioCapture').mockImplementation(async () => snapshot(levels[Math.min(call++, levels.length - 1)]));
    const cancel = vi.spyOn(bridge, 'cancelAudioCapture').mockResolvedValue(snapshot(0, 'cancelled'));
    render(<MicTest />);
    await act(async () => {
      screen.getByRole('button', { name: 'Testar' }).click();
    });
    expect(screen.getByRole('button', { name: 'Ouvindo…' })).toBeTruthy();
    for (let i = 0; i < 34; i += 1) {
      await act(async () => {
        await vi.advanceTimersByTimeAsync(120);
      });
    }
    return cancel;
  };

  it('mostra o volume real e descarta a gravação no fim', async () => {
    const cancel = await run([0.1, 0.6, 0.9]);

    expect(screen.getByRole('status').textContent).toBe('O microfone está captando sua voz.');
    expect(cancel).toHaveBeenCalledWith('mic-1');
    expect(screen.getByRole('img', { name: 'Nível do microfone: 90%' })).toBeTruthy();
  });

  it('avisa quando nenhum som chega', async () => {
    await run([0, 0.01]);

    expect(screen.getByRole('status').textContent).toContain('Nenhum som captado');
  });
});
