import { useEffect, useRef, useState } from 'react';
import { bridge } from '../services/bridge';
import { Glyph } from './ui/Glyph';

const BARS = 18;
const TEST_MS = 3500;

/** Testa o microfone salvo: grava uns segundos, mostra o volume real que chega e descarta a gravação. */
const MicTest = () => {
  const [levels, setLevels] = useState<number[]>(() => Array(BARS).fill(0));
  const [state, setState] = useState<'idle' | 'listening' | 'done' | 'error'>('idle');
  const [message, setMessage] = useState('');
  const job = useRef<string | null>(null);
  const timer = useRef<number | undefined>(undefined);
  const peak = useRef(0);

  const release = async () => {
    window.clearInterval(timer.current);
    const id = job.current;
    job.current = null;
    if (id) {
      try {
        await bridge.cancelAudioCapture(id);
      } catch {
        // A gravação já tinha terminado: nada a descartar.
      }
    }
  };

  useEffect(() => () => void release(), []);

  const start = async () => {
    setMessage('');
    setLevels(Array(BARS).fill(0));
    peak.current = 0;
    setState('listening');
    try {
      const snapshot = await bridge.startAudioCapture();
      job.current = snapshot.job_id;
      const started = Date.now();
      timer.current = window.setInterval(async () => {
        const id = job.current;
        if (!id) return;
        const current = await bridge.getAudioCapture(id);
        if (current.status === 'failed') {
          await release();
          setState('error');
          setMessage(current.message ?? 'O microfone falhou.');
          return;
        }
        const level = current.level ?? 0;
        peak.current = Math.max(peak.current, level);
        setLevels((prev) => [...prev.slice(1), level]);
        if (Date.now() - started >= TEST_MS) {
          await release();
          setState('done');
          setMessage(peak.current > 0.04 ? 'O microfone está captando sua voz.' : 'Nenhum som captado. Confira o microfone escolhido e o volume do Windows.');
        }
      }, 120);
    } catch (error) {
      await release();
      setState('error');
      setMessage(error instanceof Error ? error.message : 'Não foi possível abrir o microfone.');
    }
  };

  const listening = state === 'listening';
  return (
    <div className={`settings-item settings-item--stacked mic-test${listening ? ' mic-test--on' : ''}`}>
      <div className="settings-item__info">
        <span className="settings-item__label">Testar microfone</span>
        <span className="settings-item__description">Grava 3 segundos com o microfone salvo e mostra o volume que chega. Nada é guardado nem transcrito.</span>
      </div>
      <div className="mic-test__row">
        <span className="mic-test__bars" role="img" aria-label={`Nível do microfone: ${Math.round((levels[BARS - 1] ?? 0) * 100)}%`}>
          {levels.map((level, i) => (
            <i key={i} style={{ transform: `scaleY(${0.12 + level * 0.88})` }} />
          ))}
        </span>
        <button type="button" className="btn ui-press" onClick={() => void start()} disabled={listening}>
          <span className={listening ? 'ui-pulse' : undefined} style={{ display: 'inline-flex' }}>
            <Glyph name="mic" size={15} />
          </span>
          {listening ? 'Ouvindo…' : 'Testar'}
        </button>
      </div>
      {message && (
        <p key={message} className={`mic-test__msg pop${state === 'error' || (state === 'done' && peak.current <= 0.04) ? ' mic-test__msg--warn' : ''}`} role="status">
          {message}
        </p>
      )}
    </div>
  );
};

export default MicTest;
