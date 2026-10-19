import { useEffect, useRef, type MouseEvent, type PointerEvent, type ReactNode } from 'react';

// Constantes do arrasto com inércia (contrato da skill horizontal-momentum-scroller).
const DRAG_THRESHOLD_PX = 5; // abaixo disso é clique, não arrasto
const SAMPLE_WINDOW_MS = 120; // janela das amostras que definem a velocidade de soltura
const MAX_VELOCITY = 2.5; // px/ms
const INERTIA_DECAY = 0.92; // fator por quadro de ~16 ms
const MIN_VELOCITY = 0.02; // px/ms: abaixo disso a inércia para
const INTERACTIVE = 'button, a, input, select, textarea, label, [role="button"]';

interface DragState {
  pointerId: number;
  startX: number;
  startScrollLeft: number;
  moved: boolean;
  samples: { x: number; t: number }[];
}

interface MomentumRailProps {
  className: string;
  children: ReactNode;
  role?: string;
  'aria-label'?: string;
}

/**
 * Faixa horizontal que rola arrastando, com inércia ao soltar. A roda do mouse rola a faixa
 * enquanto ainda há para onde ir e devolve a rolagem vertical à página nas bordas. Depois de
 * um arrasto de verdade, o clique de soltura não chega aos cartões.
 */
const MomentumRail = ({ className, children, role, 'aria-label': ariaLabel }: MomentumRailProps) => {
  const railRef = useRef<HTMLDivElement>(null);
  const drag = useRef<DragState | null>(null);
  const inertiaFrame = useRef<number | null>(null);
  const suppressClick = useRef(false);

  const stopInertia = () => {
    if (inertiaFrame.current !== null) cancelAnimationFrame(inertiaFrame.current);
    inertiaFrame.current = null;
  };

  // Roda: rola na horizontal só enquanto a faixa ainda anda nessa direção (listener não passivo).
  useEffect(() => {
    const rail = railRef.current;
    if (!rail) return undefined;
    const onWheel = (event: WheelEvent) => {
      const delta = Math.abs(event.deltaX) > Math.abs(event.deltaY) ? event.deltaX : event.deltaY;
      if (delta === 0) return;
      const max = rail.scrollWidth - rail.clientWidth;
      const canMove = delta > 0 ? rail.scrollLeft < max - 1 : rail.scrollLeft > 1;
      if (!canMove) return; // na borda: a página volta a rolar na vertical
      event.preventDefault();
      if (inertiaFrame.current !== null) cancelAnimationFrame(inertiaFrame.current);
      inertiaFrame.current = null;
      rail.scrollLeft += delta;
    };
    rail.addEventListener('wheel', onWheel, { passive: false });
    return () => {
      rail.removeEventListener('wheel', onWheel);
      if (inertiaFrame.current !== null) cancelAnimationFrame(inertiaFrame.current);
    };
  }, []);

  const startInertia = (rail: HTMLDivElement, pointerVelocity: number) => {
    let velocity = Math.max(-MAX_VELOCITY, Math.min(MAX_VELOCITY, pointerVelocity));
    let last = performance.now();
    const step = (now: number) => {
      const dt = Math.min(Math.max(now - last, 0), 32);
      last = now;
      rail.scrollLeft -= velocity * dt; // ponteiro para a direita mostra o que está à esquerda
      velocity *= Math.pow(INERTIA_DECAY, dt / 16);
      const max = rail.scrollWidth - rail.clientWidth;
      const atEdge = velocity > 0 ? rail.scrollLeft <= 0 : rail.scrollLeft >= max;
      if (Math.abs(velocity) < MIN_VELOCITY || atEdge) {
        inertiaFrame.current = null;
        return;
      }
      inertiaFrame.current = requestAnimationFrame(step);
    };
    inertiaFrame.current = requestAnimationFrame(step);
  };

  const onPointerDown = (event: PointerEvent<HTMLDivElement>) => {
    if (event.button !== 0 || (event.target as Element).closest(INTERACTIVE)) return;
    stopInertia();
    suppressClick.current = false;
    drag.current = {
      pointerId: event.pointerId,
      startX: event.clientX,
      startScrollLeft: event.currentTarget.scrollLeft,
      moved: false,
      samples: [{ x: event.clientX, t: event.timeStamp }],
    };
  };

  const onPointerMove = (event: PointerEvent<HTMLDivElement>) => {
    const state = drag.current;
    if (!state || event.pointerId !== state.pointerId) return;
    const dx = event.clientX - state.startX;
    if (!state.moved) {
      if (Math.abs(dx) < DRAG_THRESHOLD_PX) return;
      state.moved = true;
      // Captura só depois do limiar: um clique simples continua indo para o cartão.
      event.currentTarget.setPointerCapture?.(event.pointerId);
      event.currentTarget.classList.add('momentum-rail--dragging');
    }
    event.preventDefault();
    event.currentTarget.scrollLeft = state.startScrollLeft - dx;
    state.samples.push({ x: event.clientX, t: event.timeStamp });
    const cutoff = event.timeStamp - SAMPLE_WINDOW_MS;
    while (state.samples.length > 2 && state.samples[0].t < cutoff) state.samples.shift();
  };

  const endDrag = (event: PointerEvent<HTMLDivElement>) => {
    const state = drag.current;
    if (!state || event.pointerId !== state.pointerId) return;
    drag.current = null;
    const rail = event.currentTarget;
    if (rail.hasPointerCapture?.(event.pointerId)) rail.releasePointerCapture(event.pointerId);
    rail.classList.remove('momentum-rail--dragging');
    if (!state.moved) return;
    // O clique de soltura vem logo depois do pointerup; a supressão vale só para ele.
    suppressClick.current = true;
    window.setTimeout(() => {
      suppressClick.current = false;
    }, 0);
    const first = state.samples[0];
    const last = state.samples[state.samples.length - 1];
    const dt = last.t - first.t;
    if (event.type === 'pointerup' && dt > 0) startInertia(rail, (last.x - first.x) / dt);
  };

  const onClickCapture = (event: MouseEvent<HTMLDivElement>) => {
    if (!suppressClick.current) return;
    suppressClick.current = false;
    event.preventDefault();
    event.stopPropagation();
  };

  return (
    <div
      ref={railRef}
      className={`momentum-rail ${className}`}
      role={role}
      aria-label={ariaLabel}
      onPointerDown={onPointerDown}
      onPointerMove={onPointerMove}
      onPointerUp={endDrag}
      onPointerCancel={endDrag}
      onClickCapture={onClickCapture}
    >
      {children}
    </div>
  );
};

export default MomentumRail;
