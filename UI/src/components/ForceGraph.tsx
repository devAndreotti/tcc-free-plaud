/**
 * ForceGraph.tsx — Grafo de forças em Canvas 2D (sem dependências externas)
 *
 * Correções aplicadas:
 *   1. DPR (devicePixelRatio): canvas dimensionado em pixels físicos, desenho
 *      em pixels lógicos → sem blur em telas HiDPI/Retina.
 *   2. Dimensões reais: o grafo só é construído dentro do ResizeObserver,
 *      onde já temos width/height corretos (não mais 0×0 no primeiro render).
 *   3. Loop finito: a animação para após MAX_ITER ticks; eventos chamam
 *      draw() diretamente — sem loop infinito a 60fps depois de estabilizar.
 */

import { useEffect, useRef, useCallback, useState } from 'react';
import type { MarkdownNode } from '../hooks/useVault';
import { GraphIcon } from './Icons';

// ─── Tipos internos ──────────────────────────────────────────────────────────

interface SimNode {
  id: string;
  label: string;
  folder: string;
  x: number;   // pixels lógicos (CSS px)
  y: number;
  vx: number;
  vy: number;
  degree: number;
}

interface SimEdge { source: string; target: string }
interface Tooltip  { label: string; x: number; y: number }

// ─── Constantes ──────────────────────────────────────────────────────────────

const REPULSION     = 4200;
const ATTRACTION    = 0.038;
const DAMPING       = 0.82;
const CENTER_PULL   = 0.011;
const EDGE_REST_LEN = 85;
const MAX_ITER      = 280;

// Cores vêm dos tokens do tema (index.css); o fundo é o do próprio painel.
function themeColors(el: Element) {
  const css = getComputedStyle(el);
  const v = (name: string) => css.getPropertyValue(name).trim();
  return {
    edge: v('--border-color'),
    node: v('--text-muted'),
    hub: v('--text-secondary'),
    hover: v('--accent-blue-light'),
  };
}

// ─── Helpers ─────────────────────────────────────────────────────────────────

function folder(path: string): string {
  const parts = path.replace(/\\/g, '/').split('/');
  return parts.length > 1 ? parts[parts.length - 2] : '__root__';
}

function nodeRadius(degree: number): number {
  return degree >= 5 ? 6.5 : degree >= 3 ? 5 : degree >= 1 ? 4 : 3.5;
}

// ─── Constrói grafo a partir dos nós do vault ────────────────────────────────

function buildGraph(
  vaultNodes: MarkdownNode[],
  logW: number,
  logH: number,
): { nodes: SimNode[]; edges: SimEdge[] } {
  const cx = logW / 2;
  const cy = logH / 2;

  const nodes: SimNode[] = vaultNodes.map((n) => ({
    id: n.id, label: n.name, folder: folder(n.path),
    x: cx + (Math.random() - 0.5) * logW * 0.65,
    y: cy + (Math.random() - 0.5) * logH * 0.65,
    vx: 0, vy: 0, degree: 0,
  }));

  // Arestas: estrela por pasta (primeiro nó = hub)
  const edges: SimEdge[] = [];
  const byFolder = new Map<string, string[]>();
  for (const n of nodes) {
    const g = byFolder.get(n.folder) ?? [];
    g.push(n.id);
    byFolder.set(n.folder, g);
  }
  for (const group of byFolder.values()) {
    const [hub, ...members] = group;
    for (const m of members.slice(0, 10))
      edges.push({ source: hub, target: m });
  }

  // Grau
  const deg = new Map<string, number>();
  for (const e of edges) {
    deg.set(e.source, (deg.get(e.source) ?? 0) + 1);
    deg.set(e.target, (deg.get(e.target) ?? 0) + 1);
  }
  for (const n of nodes) n.degree = deg.get(n.id) ?? 0;

  return { nodes, edges };
}

// ─── Um tick da simulação ────────────────────────────────────────────────────

function tick(nodes: SimNode[], edges: SimEdge[], cx: number, cy: number) {
  const map = new Map(nodes.map((n) => [n.id, n]));

  // Repulsão entre todos os pares
  for (let i = 0; i < nodes.length; i++) {
    for (let j = i + 1; j < nodes.length; j++) {
      const a = nodes[i], b = nodes[j];
      const dx = b.x - a.x, dy = b.y - a.y;
      const d2 = dx * dx + dy * dy + 0.01;
      const dist = Math.sqrt(d2);
      const f = REPULSION / d2;
      const fx = (dx / dist) * f, fy = (dy / dist) * f;
      a.vx -= fx; a.vy -= fy;
      b.vx += fx; b.vy += fy;
    }
  }

  // Atração pelas arestas
  for (const e of edges) {
    const a = map.get(e.source), b = map.get(e.target);
    if (!a || !b) continue;
    const dx = b.x - a.x, dy = b.y - a.y;
    const dist = Math.sqrt(dx * dx + dy * dy) || 1;
    const delta = (dist - EDGE_REST_LEN) * ATTRACTION;
    const fx = (dx / dist) * delta, fy = (dy / dist) * delta;
    a.vx += fx; a.vy += fy;
    b.vx -= fx; b.vy -= fy;
  }

  // Atração ao centro
  for (const n of nodes) {
    n.vx += (cx - n.x) * CENTER_PULL;
    n.vy += (cy - n.y) * CENTER_PULL;
  }

  // Integração + amortecimento
  for (const n of nodes) {
    n.vx *= DAMPING; n.vy *= DAMPING;
    n.x  += n.vx;   n.y  += n.vy;
  }
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

  const camRef   = useRef({ x: 0, y: 0, scale: 1 });
  const graphRef = useRef<{ nodes: SimNode[]; edges: SimEdge[] }>({ nodes: [], edges: [] });
  const dragRef  = useRef({ active: false, startX: 0, startY: 0, camX: 0, camY: 0 });
  const hovered  = useRef<string | null>(null);

  const [tooltip, setTooltip] = useState<Tooltip | null>(null);

  // ── Desenha um frame ────────────────────────────────────────────────────
  const draw = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const { nodes, edges } = graphRef.current;
    const cam = camRef.current;
    const d   = dpr.current;
    const W   = logW.current;
    const H   = logH.current;

    // Limpa em pixels físicos
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    const colors = themeColors(canvas);

    // Todo desenho em pixels lógicos
    ctx.save();
    ctx.scale(d, d);           // HiDPI
    ctx.translate(cam.x, cam.y);
    ctx.scale(cam.scale, cam.scale);

    const map = new Map(nodes.map((n) => [n.id, n]));

    // Arestas
    ctx.strokeStyle = colors.edge;
    ctx.lineWidth   = 0.9 / cam.scale;
    for (const e of edges) {
      const a = map.get(e.source), b = map.get(e.target);
      if (!a || !b) continue;
      ctx.beginPath();
      ctx.moveTo(a.x, a.y);
      ctx.lineTo(b.x, b.y);
      ctx.stroke();
    }

    // Nós
    for (const n of nodes) {
      const r         = nodeRadius(n.degree);
      const isHovered = n.id === hovered.current;
      const isHub     = n.degree >= 3;

      ctx.beginPath();
      ctx.arc(n.x, n.y, r, 0, Math.PI * 2);

      ctx.fillStyle = isHovered ? colors.hover : isHub ? colors.hub : colors.node;
      ctx.fill();
    }

    ctx.restore();

    // Linha de grade sutil de fundo (opcional — comentar se não quiser)
    void W; void H; // evita TS unused warning
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
        draw(); // frame final sem mais agendamento
      }
    };
    loop(iters);
  }, [draw]);

  // ── Reconstrói o grafo e reinicia a simulação ───────────────────────────
  const rebuild = useCallback(() => {
    if (logW.current === 0 || logH.current === 0) return;
    graphRef.current = buildGraph(vaultNodes, logW.current, logH.current);
    camRef.current   = { x: 0, y: 0, scale: 1 };
    startLoop(MAX_ITER);
  }, [vaultNodes, startLoop]);

  // ── ResizeObserver: dimensiona o canvas com DPR e reconstrói ───────────
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ro = new ResizeObserver((entries) => {
      for (const entry of entries) {
        const { width, height } = entry.contentRect;
        if (width === 0 || height === 0) continue;

        // Atualiza DPR e dimensões físicas do canvas
        const d = window.devicePixelRatio || 1;
        dpr.current    = d;
        logW.current   = width;
        logH.current   = height;
        canvas.width   = Math.round(width  * d);
        canvas.height  = Math.round(height * d);

        rebuild();
      }
    });

    ro.observe(canvas);
    return () => { ro.disconnect(); cancelAnimationFrame(animRef.current); };
  }, [rebuild]);

  // ── Reconstrói quando vaultNodes muda (sem esperar resize) ─────────────
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

    let found: SimNode | null = null;
    for (const n of nodes) {
      const r = nodeRadius(n.degree) + 5;
      const dx = n.x - world.x, dy = n.y - world.y;
      if (dx * dx + dy * dy <= r * r) { found = n; break; }
    }

    if (found) {
      if (hovered.current !== found.id) {
        hovered.current = found.id;
        const cam = camRef.current;
        setTooltip({ label: found.label, x: found.x * cam.scale + cam.x, y: found.y * cam.scale + cam.y });
        draw();
      }
    } else if (hovered.current !== null) {
      hovered.current = null;
      setTooltip(null);
      draw();
    }

    if (dragRef.current.active) {
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

  // ── Zoom com scroll ─────────────────────────────────────────────────────
  const handleWheel = useCallback((e: React.WheelEvent<HTMLCanvasElement>) => {
    e.preventDefault();
    const canvas = canvasRef.current;
    if (!canvas) return;
    const rect   = canvas.getBoundingClientRect();
    const mx     = e.clientX - rect.left;
    const my     = e.clientY - rect.top;
    const cam    = camRef.current;
    const factor = e.deltaY < 0 ? 1.12 : 0.89;
    const ns     = Math.max(0.15, Math.min(5, cam.scale * factor));
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
        onWheel={handleWheel}
        aria-label="Visualização de grafo — arraste para mover, scroll para zoom"
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
