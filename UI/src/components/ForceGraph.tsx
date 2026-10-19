/**
 * ForceGraph.tsx — Grafo de forças em Canvas 2D (sem dependências externas)
 *
 * Desenha o grafo de src/lib/vaultGraph.ts. A câmera se ajusta ao grafo enquanto o usuário
 * não arrasta nem dá zoom. Canvas em pixels físicos (DPR) e desenho em pixels lógicos.
 */

import { useEffect, useRef, useCallback, useState } from 'react';
import type { GraphMode, MarkdownNode, VaultLink } from '../lib/vaultGraph';
import {
  GRAPH_FOCUS_EVENT,
  buildGraph,
  fitCamera,
  nodeRadius,
  pathToRoot,
  tick,
  type Camera,
  type SimEdge,
  type SimNode,
} from '../lib/vaultGraph';
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
    link: v('--accent-blue-light'),
    focus: v('--accent-blue-light'),
    bg: v('--bg-primary'),
    tipBg: v('--tip-bg'),
    tipFg: v('--tip-fg'),
  };
}

type Colors = ReturnType<typeof themeColors>;
type Ctx = CanvasRenderingContext2D;

// ─── Desenho de um frame (funções internas, fora do componente) ──────────────

function nodeColor(n: SimNode, colors: Colors, hoveredId: string | null): string {
  if (n.id === hoveredId) return colors.hover;
  if (n.kind === 'folder') return colors.folder;
  return colors.node;
}

function drawEdges(ctx: Ctx, nodes: SimNode[], edges: SimEdge[], colors: Colors, cam: Camera) {
  const map = new Map(nodes.map((n) => [n.id, n]));
  const stroke = (isLink: boolean) => {
    ctx.beginPath();
    for (const e of edges) {
      if ((e.kind === 'link') !== isLink) continue;
      const a = map.get(e.source), b = map.get(e.target);
      if (!a || !b) continue;
      ctx.moveTo(a.x, a.y);
      ctx.lineTo(b.x, b.y);
    }
    ctx.stroke();
  };
  // Árvore em cinza; ligações [[...]] por cima, um pouco mais grossas e em azul claro transparente
  ctx.strokeStyle = colors.edge;
  ctx.lineWidth   = 0.8 / cam.scale;
  stroke(false);

  const alpha = ctx.globalAlpha;
  ctx.strokeStyle = colors.link;
  ctx.lineWidth   = 1.2 / cam.scale;
  ctx.globalAlpha = alpha * 0.35;
  stroke(true);
  ctx.globalAlpha = alpha;
}

function drawNodes(ctx: Ctx, nodes: SimNode[], colors: Colors, hoveredId: string | null) {
  for (const n of nodes) {
    ctx.beginPath();
    ctx.arc(n.x, n.y, nodeRadius(n), 0, Math.PI * 2);
    ctx.fillStyle = nodeColor(n, colors, hoveredId);
    ctx.fill();
  }
}

// Rótulos das pastas só com zoom suficiente para não se sobreporem (1º nível antes dos demais)
function drawFolderLabels(ctx: Ctx, nodes: SimNode[], colors: Colors, cam: Camera) {
  ctx.fillStyle = colors.label;
  ctx.font = `${11 / cam.scale}px sans-serif`;
  ctx.textAlign = 'center';
  for (const n of nodes) {
    if (n.kind !== 'folder' || n.depth === 0) continue;
    const minScale = n.depth === 1 ? 0.45 : 1.2;
    if (cam.scale < minScale) continue;
    ctx.fillText(n.label, n.x, n.y - (nodeRadius(n) + 4) / cam.scale);
  }
}

// Nota em foco (hover numa fonte do chat) e o caminho de pastas até a raiz. Tamanhos em px de
// tela (÷ scale) para o destaque aparecer em qualquer zoom; viewW prende a pílula no painel.
function drawFocus(ctx: Ctx, chain: string[], nodes: SimNode[], colors: Colors, cam: Camera, viewW: number) {
  const byId = new Map(nodes.map((n) => [n.id, n]));
  const path = chain.map((id) => byId.get(id)).filter((n): n is SimNode => n !== undefined);
  const [target] = path;
  if (!target) return;
  const px = 1 / cam.scale;
  const radius = (n: SimNode) => Math.max(nodeRadius(n), (n === target ? 6 : 4) * px);

  ctx.strokeStyle = colors.focus;
  ctx.lineWidth = 2 * px;
  ctx.beginPath();
  path.forEach((n, i) => (i === 0 ? ctx.moveTo(n.x, n.y) : ctx.lineTo(n.x, n.y)));
  ctx.stroke();

  ctx.fillStyle = colors.focus;
  ctx.globalAlpha = 0.25;
  ctx.beginPath();
  ctx.arc(target.x, target.y, 14 * px, 0, Math.PI * 2);
  ctx.fill();
  ctx.globalAlpha = 1;
  for (const n of path) {
    ctx.beginPath();
    ctx.arc(n.x, n.y, radius(n), 0, Math.PI * 2);
    ctx.fill();
  }

  // Nomes das pastas do caminho, com contorno da cor do fundo para a linha não cortar a letra
  ctx.font = `${11 * px}px sans-serif`;
  ctx.textAlign = 'center';
  ctx.lineJoin = 'round';
  ctx.lineWidth = 3 * px;
  ctx.strokeStyle = colors.bg;
  for (const n of path.slice(1)) {
    if (n.depth === 0) continue; // a raiz não tem nome
    const y = n.y - radius(n) - 5 * px;
    ctx.strokeText(n.label, n.x, y);
    ctx.fillText(n.label, n.x, y);
  }

  // Nome da nota numa pílula acima dela, sem sair pelas bordas do painel
  const label = target.label.length > 42 ? `${target.label.slice(0, 41)}…` : target.label;
  ctx.font = `600 ${12 * px}px sans-serif`;
  const w = ctx.measureText(label).width + 16 * px;
  const h = 22 * px;
  const minX = (6 - cam.x) * px;
  const maxX = (viewW - 6 - cam.x) * px - w;
  const left = Math.max(minX, Math.min(maxX, target.x - w / 2));
  const top = target.y - 18 * px - h;
  ctx.fillStyle = colors.tipBg;
  ctx.beginPath();
  ctx.roundRect(left, top, w, h, 6 * px);
  ctx.fill();
  ctx.fillStyle = colors.tipFg;
  ctx.textBaseline = 'middle';
  ctx.fillText(label, left + w / 2, top + h / 2);
  ctx.textBaseline = 'alphabetic';
}

// ─── Componente ──────────────────────────────────────────────────────────────

interface ForceGraphProps {
  vaultNodes: MarkdownNode[];
  /** Ligações [[...]] entre notas (arestas de link), usadas nos modos links e ambos */
  links?: VaultLink[];
  /** pastas, links ou ambos (padrão) */
  mode?: GraphMode;
  /** Clique numa nota (sem arrastar) abre a nota; clique em pasta não faz nada */
  onOpenNote?: (noteId: string) => void;
}

// Lista fixa: um array novo a cada render reconstruiria o grafo a cada render
const NO_LINKS: VaultLink[] = [];

// Deslocamento (px na tela) acima do qual o gesto é arrasto, não clique
const CLICK_SLOP = 4;

// Nó sob o ponto (coordenadas de mundo); a folga de 5 px na tela facilita o alvo
function nodeAt(nodes: SimNode[], world: { x: number; y: number }, scale: number): SimNode | null {
  for (const n of nodes) {
    const r = nodeRadius(n) + 5 / scale;
    const dx = n.x - world.x, dy = n.y - world.y;
    if (dx * dx + dy * dy <= r * r) return n;
  }
  return null;
}

const ForceGraph = ({ vaultNodes, links = NO_LINKS, mode = 'ambos', onOpenNote }: ForceGraphProps) => {
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
  const focused    = useRef<string | null>(null); // nota da fonte sob o mouse no chat
  const panRef     = useRef<number>(0);

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

    // Com uma fonte em foco, o resto do grafo recua para o caminho dela aparecer
    const chain = focused.current ? pathToRoot(focused.current, nodes, edges) : [];
    ctx.globalAlpha = chain.length > 0 ? 0.3 : 1;
    drawEdges(ctx, nodes, edges, colors, cam);
    drawNodes(ctx, nodes, colors, hovered.current);
    drawFolderLabels(ctx, nodes, colors, cam);
    ctx.globalAlpha = 1;
    if (chain.length > 0) drawFocus(ctx, chain, nodes, colors, cam, logW.current);

    ctx.restore();
  }, []);

  // ── Nota fora da área visível (após zoom ou arrasto): a câmera desliza até ela, sem mudar o zoom
  const panIntoView = useCallback((n: SimNode) => {
    const cam = camRef.current;
    const margin = 48;
    const sx = n.x * cam.scale + cam.x;
    const sy = n.y * cam.scale + cam.y;
    if (sx > margin && sx < logW.current - margin && sy > margin && sy < logH.current - margin) return;

    const from = { x: cam.x, y: cam.y };
    const to = { x: logW.current / 2 - n.x * cam.scale, y: logH.current / 2 - n.y * cam.scale };
    const duration = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ? 0 : 240;
    const start = performance.now();
    const step = (now: number) => {
      const t = duration ? Math.min(1, (now - start) / duration) : 1;
      const ease = 1 - (1 - t) ** 3;
      camRef.current.x = from.x + (to.x - from.x) * ease;
      camRef.current.y = from.y + (to.y - from.y) * ease;
      draw();
      if (t < 1) panRef.current = requestAnimationFrame(step);
    };
    cancelAnimationFrame(panRef.current);
    panRef.current = requestAnimationFrame(step);
  }, [draw]);

  // ── Hover numa fonte da resposta (MessageBubble) destaca a nota e o caminho dela ──
  useEffect(() => {
    const onFocus = (e: Event) => {
      const id = (e as CustomEvent<string | null>).detail;
      focused.current = id;
      const target = id ? graphRef.current.nodes.find((n) => n.id === id) : undefined;
      // Enquadrando o grafo inteiro, a nota já está na tela; só com zoom ela pode estar fora
      if (target && !autoFitRef.current) panIntoView(target);
      draw();
    };
    window.addEventListener(GRAPH_FOCUS_EVENT, onFocus);
    return () => {
      window.removeEventListener(GRAPH_FOCUS_EVENT, onFocus);
      cancelAnimationFrame(panRef.current);
    };
  }, [draw, panIntoView]);

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
    graphRef.current = buildGraph(vaultNodes, logW.current, logH.current, graphRef.current.nodes, links, mode);
    autoFitRef.current = true;
    startLoop(MAX_ITER);
  }, [vaultNodes, links, mode, startLoop]);

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

    const found = nodeAt(nodes, world, cam.scale);
    canvas.style.cursor = found?.kind === 'note' ? 'pointer' : '';

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

  const handleMouseUp = useCallback((e: React.MouseEvent<HTMLCanvasElement>) => {
    const drag = dragRef.current;
    if (!drag.active) return; // soltou o botão vindo de fora do canvas
    drag.active = false;
    if (Math.hypot(e.clientX - drag.startX, e.clientY - drag.startY) >= CLICK_SLOP) return;

    const canvas = canvasRef.current;
    if (!canvas) return;
    const rect = canvas.getBoundingClientRect();
    const hit = nodeAt(graphRef.current.nodes, toWorld(e.clientX - rect.left, e.clientY - rect.top), camRef.current.scale);
    if (hit?.kind === 'note') onOpenNote?.(hit.id);
  }, [toWorld, onOpenNote]);
  const handleMouseLeave = useCallback(() => {
    dragRef.current.active = false;
    if (hovered.current !== null) { hovered.current = null; setTooltip(null); draw(); }
  }, [draw]);

  // Duplo clique volta a enquadrar o grafo inteiro
  const handleDoubleClick = useCallback(() => { autoFitRef.current = true; draw(); }, [draw]);

  // ── Zoom com scroll ─────────────────────────────────────────────────────
  const handleWheel = useCallback((e: WheelEvent) => {
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

  // Listener nativo e não passivo: o preventDefault do React é ignorado (ele registra wheel como passivo).
  // Com `empty`, o listener é religado quando o canvas aparece (ele não existe no estado vazio).
  const empty = vaultNodes.length === 0;
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return undefined;
    canvas.addEventListener('wheel', handleWheel, { passive: false });
    return () => canvas.removeEventListener('wheel', handleWheel);
  }, [handleWheel, empty]);

  if (vaultNodes.length === 0) {
    return (
      <div className="force-graph force-graph--empty">
        <GraphIcon size={20} />
        <span className="force-graph__empty-msg">Nenhuma nota indexada nesta vault. Indexe uma pasta na Fila.</span>
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
