import { useEffect, type RefObject } from 'react';

/** Fecha um menu flutuante ao clicar fora dele ou apertar Esc. */
export const useDismissOnOutside = (open: boolean, wrapRef: RefObject<HTMLDivElement | null>, close: () => void) => {
  useEffect(() => {
    if (!open) return undefined;
    const onDown = (event: MouseEvent) => {
      if (!wrapRef.current?.contains(event.target as Node)) close();
    };
    const onKey = (event: globalThis.KeyboardEvent) => {
      if (event.key === 'Escape') close();
    };
    document.addEventListener('mousedown', onDown);
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('mousedown', onDown);
      document.removeEventListener('keydown', onKey);
    };
  }, [open, wrapRef, close]);
};
