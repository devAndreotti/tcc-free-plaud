import { useEffect, useRef, useState } from 'react';
import { Glyph } from './ui/Glyph';

interface CopyActionProps {
  text: string;
  ariaLabel: string;
  className?: string;
}

/** Botão Copiar do chat: confirma por um instante e devolve o rótulo. */
const CopyAction = ({ text, ariaLabel, className }: CopyActionProps) => {
  const [copied, setCopied] = useState(false);
  const timer = useRef<number | null>(null);
  useEffect(() => () => {
    if (timer.current !== null) window.clearTimeout(timer.current);
  }, []);

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      timer.current = window.setTimeout(() => setCopied(false), 1600);
    } catch {
      setCopied(false);
    }
  };

  const classes = ['msg__action', copied ? 'is-copied' : '', className ?? ''].filter(Boolean).join(' ');
  return (
    <button type="button" className={classes} onClick={copy} aria-label={ariaLabel}>
      {copied ? (
        <span className="msg__action-ok pop"><Glyph name="check" size={14} strokeWidth={2.2} /></span>
      ) : (
        <Glyph name="copy" size={14} />
      )}
      <span>{copied ? 'Copiado' : 'Copiar'}</span>
    </button>
  );
};

export default CopyAction;
