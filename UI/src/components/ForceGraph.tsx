/**
 * ForceGraph.tsx — Grafo de forças em Canvas 2D (sem dependências externas)
 *
 * Desenha o grafo de src/lib/vaultGraph.ts. A câmera se ajusta ao grafo enquanto o usuário
 * não arrasta nem dá zoom. Canvas em pixels físicos (DPR) e desenho em pixels lógicos.
 */

import { useEffect, useRef, useCallback, useState } from 'react';
import type { MarkdownNode } from '../hooks/useVault';
import { buildGraph, fitCamera, nodeRadius, tick, type Camera, type SimEdge, type SimNode } from '../lib/vaultGraph';
import { GraphIcon } from './Icons';

interface Tooltip  { label: string; x: number; y: number }

const MAX_ITER = 300;

// Cores vêm dos tokens do tema (index.css); o fundo é o do próprio painel.
function themeColors(el: Element) {
  const css = getComputedStyle(el);
  const v = (name: string) => css.getPropertyValue(name).trim();
  return {
    edge: v('--border-color'),
    node: v('--text-muted'),
    folder: v('--accent-blue'),
    label: v('--text-secondary'),
    hover: v('--accent-blue-light'),
  };
}

// ─── Componente ──────────────────────────────────────────────────────────────

interface ForceGraphProps { vaultNodes: MarkdownNode[] }

const ForceGraph = ({ vaultNodes }: ForceGraphProps) => {
  const canvasRef  = useRef<HTMLCanvasElement>(null);
  const animRef    = useRef<number>(0);

  // Dimensões lógicas (CSS px) e DPR, atualizadas no ResizeObserver
  const logW = useRef(0);
  const logH = useRef(0);
  const dpr  = useRef(window.devicePixelRatio || 1);

  const camRef     = useRef<Camera>({ x: 0, y: 0, scale: 1 });
  const autoFitRef = useRef(true); // desliga quando o usuário arrasta ou dá zoom
  const graphRef   = useRef<{ nodes: SimNode[]; edges: SimEdge[] }>({ nodes: [], edges: [] });
  const dragRef    = useRef({ active: false, startX: 0, startY: 0, camX: 0, camY: 0 });
  const hovered    = useRef<string | null>(null);

  const [tooltip, setTooltip] = useState<Tooltip | null>(null);

  // ── Desenha um frame ────────────────────────────────────────────────────
  const draw = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const { nodes, edges } = graphRef.current;
    if (autoFitRef.current) camRef.current = fitCamera(nodes, logW.current, logH.current);
    const cam = camRef.current;

    ctx.clearRect(0, 0, canvas.width, canvas.height);
    const colors = themeColors(canvas);

    ctx.save();
    ctx.scale(dpr.current, dpr.current);
    ctx.translate(cam.x, cam.y);
    ctx.scale(cam.scale, cam.scale);

    const map = new Map(nodes.map((n) => [n.id, n]));

    ctx.strokeStyle = colors.edge;
    ctx.lineWidth   = 0.8 / cam.scale;
    ctx.beginPath();
    for (const e of edges) {
      const a = map.get(e.source), b = map.get(e.target);
      if (!a || !b) continue;
      ctx.moveTo(a.x, a.y);
      ctx.lineTo(b.x, b.y);
    }
    ctx.stroke();

    for (const n of nodes) {
      ctx.beginPath();
      ctx.arc(n.x, n.y, nodeRadius(n), 0, Math.PI * 2);
      ctx.fillStyle = n.id === hovered.current ? colors.hover : n.kind === 'folder' ? colors.folder : colors.node;
      ctx.fill();
    }

    // Rótulos das pastas só com zoom suficiente para não se sobreporem (1º nível antes dos demais)
    ctx.fillStyle = colors.label;
    ctx.font = `${11 / cam.scale}px sans-serif`;
    ctx.textAlign = 'center';
    for (const n of nodes) {
      if (n.kind !== 'folder' || n.depth === 0) continue;
      if (cam.scale < (n.depth === 1 ? 0.45 : 1.2)) continue;
      ctx.fillText(n.label, n.x, n.y - (nodeRadius(n) + 4) / cam.scale);
    }

    ctx.restore();
  }, []);

  // ── Loop de simulação (finito) ──────────────────────────────────────────
  const startLoop = useCallback((iters: number) => {
    cancelAnimationFrame(animRef.current);
    const { nodes, edges } = graphRef.current;
    const cx = logW.current / 2;
    const cy = logH.current / 2;

    const loop = (i: number) => {
      if (i > 0) {
        tick(nodes, edges, cx, cy);
        draw();
        animRef.current = requestAnimationFrame(() => loop(i - 1));
      } else {
        draw();
      }
    };
    loop(iters);
  }, [draw]);

  // ── Reconstrói o grafo quando os nós do vault mudam ────────────────────
  const rebuild = useCallback(() => {
    if (logW.current === 0 || logH.current === 0) return;
    graphRef.current = buildGraph(vaultNodes, logW.current, logH.current, graphRef.current.nodes);
    autoFitRef.current = true;
    startLoop(MAX_ITER);
  }, [vaultNodes, startLoop]);

  // ── ResizeObserver: redimensiona o canvas; só monta o grafo na 1ª medida ─
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ro = new ResizeObserver((entries) => {
      for (const entry of entries) {
        const { width, height } = entry.contentRect;
        if (width === 0 || height === 0) continue;

        const firstMeasure = logW.current === 0;
        const d = window.devicePixelRatio || 1;
        dpr.current    = d;
        logW.current   = width;
        logH.current   = height;
        canvas.width   = Math.round(width  * d);
        canvas.height  = Math.round(height * d);

        if (firstMeasure || graphRef.current.nodes.length === 0) rebuild();
        else draw(); // arrastar a borda do painel não embaralha o grafo
      }
    });

    ro.observe(canvas);
    return () => { ro.disconnect(); cancelAnimationFrame(animRef.current); };
  }, [rebuild, draw]);

  useEffect(() => { rebuild(); }, [rebuild]);

  // ── Redesenha quando o tema troca (as cores vêm dos tokens) ────────────
  useEffect(() => {
    const mo = new MutationObserver(() => draw());
    mo.observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] });
    return () => mo.disconnect();
  }, [draw]);

  // ── Coordenadas canvas → mundo ──────────────────────────────────────────
  const toWorld = useCallback((cx: number, cy: number) => {
    const cam = camRef.current;
    return { x: (cx - cam.x) / cam.scale, y: (cy - cam.y) / cam.scale };
  }, []);

  // ── Hover + pan ─────────────────────────────────────────────────────────
  const handleMouseMove = useCallback((e: React.MouseEvent<HTMLCanvasElement>) => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const rect  = canvas.getBoundingClientRect();
    const world = toWorld(e.clientX - rect.left, e.clientY - rect.top);
    const { nodes } = graphRef.current;
    const cam = camRef.current;

    let found: SimNode | null = null;
    for (const n of nodes) {
      const r = nodeRadius(n) + 5 / cam.scale;
      const dx = n.x - world.x, dy = n.y - world.y;
      if (dx * dx + dy * dy <= r * r) { found = n; break; }
    }

    if (found) {
      if (hovered.current !== found.id) {
        hovered.current = found.id;
        setTooltip({ label: found.label, x: found.x * cam.scale + cam.x, y: found.y * cam.scale + cam.y });
        draw();
      }
    } else if (hovered.current !== null) {
      hovered.current = null;
      setTooltip(null);
      draw();
    }

    if (dragRef.current.active) {
      autoFitRef.current = false;
      camRef.current.x = dragRef.current.camX + (e.clientX - dragRef.current.startX);
      camRef.current.y = dragRef.current.camY + (e.clientY - dragRef.current.startY);
      draw();
    }
  }, [toWorld, draw]);

  const handleMouseDown = useCallback((e: React.MouseEvent<HTMLCanvasElement>) => {
    dragRef.current = { active: true, startX: e.clientX, startY: e.clientY, camX: camRef.current.x, camY: camRef.current.y };
  }, []);

  const handleMouseUp    = useCallback(() => { dragRef.current.active = false; }, []);
  const handleMouseLeave = useCallback(() => {
    dragRef.current.active = false;
    if (hovered.current !== null) { hovered.current = null; setTooltip(null); draw(); }
  }, [draw]);

  // Duplo clique volta a enquadrar o grafo inteiro
  const handleDoubleClick = useCallback(() => { autoFitRef.current = true; draw(); }, [draw]);

  // ── Zoom com scroll ─────────────────────────────────────────────────────
  const handleWheel = useCallback((e: React.WheelEvent<HTMLCanvasElement>) => {
    e.preventDefault();
    const canvas = canvasRef.current;
    if (!canvas) return;
    autoFitRef.current = false;
    const rect   = canvas.getBoundingClientRect();
    const mx     = e.clientX - rect.left;
    const my     = e.clientY - rect.top;
    const cam    = camRef.current;
    const factor = e.deltaY < 0 ? 1.12 : 0.89;
    const ns     = Math.max(0.05, Math.min(5, cam.scale * factor));
    cam.x = mx - (mx - cam.x) * (ns / cam.scale);
    cam.y = my - (my - cam.y) * (ns / cam.scale);
    cam.scale = ns;
    draw();
  }, [draw]);

  if (vaultNodes.length === 0) {
    return (
      <div className="force-graph force-graph--empty">
        <GraphIcon size={20} />
        <b>Nenhuma nota no grafo</b>
        <span className="force-graph__empty-msg">Indexe uma pasta na Fila para ver as notas e as pastas que as ligam.</span>
      </div>
    );
  }

  return (
    <div className="force-graph" aria-label="Grafo de notas">
      <canvas
        ref={canvasRef}
        className="force-graph__canvas"
        onMouseMove={handleMouseMove}
        onMouseDown={handleMouseDown}
        onMouseUp={handleMouseUp}
        onMouseLeave={handleMouseLeave}
        onDoubleClick={handleDoubleClick}
        onWheel={handleWheel}
        aria-label="Visualização de grafo — arraste para mover, scroll para zoom, duplo clique para enquadrar"
      />
      {tooltip && (
        <div
          className="force-graph__tooltip"
          style={{ left: tooltip.x, top: tooltip.y }}
          aria-hidden="true"
        >
          {tooltip.label}
        </div>
      )}
    </div>
  );
};

export default ForceGraph;
