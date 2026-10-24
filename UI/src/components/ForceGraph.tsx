/**
 * ForceGraph.tsx — Grafo de forças em Canvas 2D (sem dependências externas)
 *
 * Desenha o grafo de src/lib/vaultGraph.ts. A câmera se ajusta ao grafo enquanto o usuário
 * não arrasta nem dá zoom. Canvas em pixels físicos (DPR) e desenho em pixels lógicos.
 * Desenho em components/graphDraw.ts; seleção por clique em lib/graphSelection.ts.
 */

import { useEffect, useRef, useCallback, useState, useMemo } from 'react';
import type { GraphMode, MarkdownNode, VaultLink, Camera, SimEdge, SimNode } from '../lib/vaultGraph';
import {
  GRAPH_FOCUS_EVENT,
  buildGraph,
  fitCamera,
  pathToRoot,
  tick,
  visibleLinks,
} from '../lib/vaultGraph';
import {
  folderSubtreeIds,
  frameCamera,
  hitTest,
  isClick,
  lerpCamera,
  neighborIds,
  selectionAnnouncement,
  selectionSet,
} from '../lib/graphSelection';
import { legendEntries, topFolderOf } from '../lib/graphColors';
import { entryAt, prefersReducedMotion, projectNodes, shouldAnimateEntry } from '../lib/graphMotion';
import { drawEdges, drawFocus, drawLabels, drawNodes, readPalette, tooltipDetail, type Palette } from './graphDraw';
import { GraphIcon } from './Icons';
import GraphNoLinksHint from './GraphNoLinksHint';
import GraphLegend from './GraphLegend';

interface Tooltip  { label: string; detail: string; x: number; y: number }

const MAX_ITER = 300;
// Quadros de uma transição de câmera (enquadrar uma pasta): ~240 ms a 60 Hz
const GLIDE_FRAMES = 14;

// Lista fixa: um array novo a cada render reconstruiria o grafo a cada render
const NO_LINKS: VaultLink[] = [];

interface ForceGraphProps {
  vaultNodes: MarkdownNode[];
  /** Ligações [[...]] entre notas (arestas de link), usadas nos modos links e ambos */
  links?: VaultLink[];
  /** pastas, links ou ambos (padrão) */
  mode?: GraphMode;
  /** Clique numa nota (sem arrastar) abre a nota; clique em pasta enquadra a pasta */
  onOpenNote?: (noteId: string) => void;
}

const ForceGraph = ({ vaultNodes, links = NO_LINKS, mode = 'ambos', onOpenNote }: ForceGraphProps) => {
  const canvasRef  = useRef<HTMLCanvasElement>(null);
  const animRef    = useRef<number>(0);

  // Dimensões lógicas (CSS px) e DPR, atualizadas no ResizeObserver
  const logW = useRef(0);
  const logH = useRef(0);
  const dpr  = useRef(window.devicePixelRatio || 1);

  const camRef     = useRef<Camera>({ x: 0, y: 0, scale: 1 });
  const autoFitRef = useRef(true); // desliga quando o usuário arrasta, dá zoom ou enquadra uma pasta
  const graphRef   = useRef<{ nodes: SimNode[]; edges: SimEdge[] }>({ nodes: [], edges: [] });
  const dragRef    = useRef({ active: false, startX: 0, startY: 0, camX: 0, camY: 0 });
  const hovered    = useRef<string | null>(null);
  const focused    = useRef<string | null>(null); // nota da fonte sob o mouse no chat
  const selectedRef = useRef<string | null>(null); // nó selecionado por clique
  const panRef     = useRef<number>(0);
  const entryStartRef = useRef<number | null>(null); // início da abertura (null = grafo já aberto)
  const modeRef    = useRef<GraphMode>(mode);        // modo do último build (troca de modo reabre)

  const [tooltip, setTooltip] = useState<Tooltip | null>(null);
  // Texto da região aria-live: "Selecionado: <nome>, N ligações" (vazio sem seleção)
  const [announcement, setAnnouncement] = useState('');

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
    const pal: Palette = readPalette(canvas);

    ctx.save();
    ctx.scale(dpr.current, dpr.current);
    ctx.translate(cam.x, cam.y);
    ctx.scale(cam.scale, cam.scale);

    // Com uma fonte em foco, o resto do grafo recua para o caminho dela aparecer
    const chain = focused.current ? pathToRoot(focused.current, nodes, edges) : [];
    const sel = selectionSet(selectedRef.current, edges);
    // Posições exibidas: a abertura radial do centro até a simulação (ver graphMotion.ts)
    const shown = projectNodes(nodes, logW.current / 2, logH.current / 2, entryAt(entryStartRef.current, performance.now()));
    ctx.globalAlpha = chain.length > 0 ? 0.3 : 1;
    const hl = { hoveredId: hovered.current, selectedId: selectedRef.current, sel, scale: cam.scale };
    drawEdges(ctx, shown, edges, pal, cam, sel);
    drawNodes(ctx, shown, pal, hl);
    drawLabels(ctx, shown, pal, cam, sel);
    ctx.globalAlpha = 1;
    if (chain.length > 0) drawFocus(ctx, chain, shown, pal, cam, logW.current);

    ctx.restore();
  }, []);

  // ── Transição suave da câmera (quadros, não tempo: sem loop infinito quando rAF é síncrono) ──
  const glideTo = useCallback((to: Camera) => {
    autoFitRef.current = false;
    cancelAnimationFrame(panRef.current);
    const from = { ...camRef.current };
    const reduce = prefersReducedMotion();
    let frame = 0;
    const step = () => {
      frame += 1;
      const t = reduce || frame >= GLIDE_FRAMES ? 1 : 1 - (1 - frame / GLIDE_FRAMES) ** 3;
      camRef.current = lerpCamera(from, to, t);
      draw();
      if (t < 1) panRef.current = requestAnimationFrame(step);
    };
    step();
  }, [draw]);

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

    // Com movimento reduzido a simulação roda inteira de uma vez e o grafo aparece já posicionado
    if (prefersReducedMotion()) {
      for (let i = 0; i < iters; i++) tick(nodes, edges, cx, cy);
      entryStartRef.current = null;
      draw();
      return;
    }

    const loop = (i: number) => {
      if (i > 0) {
        tick(nodes, edges, cx, cy);
        draw();
        animRef.current = requestAnimationFrame(() => loop(i - 1));
      } else {
        // Simulação terminada: a abertura de 600 ms já acabou (são centenas de quadros)
        entryStartRef.current = null;
        draw();
      }
    };
    loop(iters);
  }, [draw]);

  // ── Reconstrói o grafo quando os nós do vault mudam ────────────────────
  const rebuild = useCallback(() => {
    if (logW.current === 0 || logH.current === 0) return;
    const prevIds = new Set(graphRef.current.nodes.map((n) => n.id));
    const modeChanged = modeRef.current !== mode;
    modeRef.current = mode;
    graphRef.current = buildGraph(vaultNodes, logW.current, logH.current, graphRef.current.nodes, links, mode);
    autoFitRef.current = true;
    const animate = shouldAnimateEntry(prevIds, graphRef.current.nodes.map((n) => n.id), modeChanged);
    entryStartRef.current = animate ? performance.now() : null;
    // Seleção que sumiu com o grafo (nota apagada, outro modo sem ela) não fica anunciada
    if (selectedRef.current !== null && !graphRef.current.nodes.some((n) => n.id === selectedRef.current)) {
      selectedRef.current = null;
      setAnnouncement('');
    }
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

  // Nó sob o ponteiro (coordenadas da janela), ou null
  const nodeUnder = useCallback((clientX: number, clientY: number) => {
    const canvas = canvasRef.current;
    if (!canvas) return null;
    const rect = canvas.getBoundingClientRect();
    // Acerta onde o nó está desenhado agora (durante a abertura ele ainda está perto do centro)
    const shown = projectNodes(graphRef.current.nodes, logW.current / 2, logH.current / 2, entryAt(entryStartRef.current, performance.now()));
    return hitTest(shown, toWorld(clientX - rect.left, clientY - rect.top), camRef.current.scale);
  }, [toWorld]);

  // ── Seleção: nó (ou null para limpar) e o anúncio para leitores de tela ──
  const selectNode = useCallback((n: SimNode | null) => {
    selectedRef.current = n?.id ?? null;
    setAnnouncement(n ? selectionAnnouncement(n.label, neighborIds(n.id, graphRef.current.edges).size) : '');
    draw();
  }, [draw]);

  // Enquadra a pasta e tudo abaixo dela (a câmera desliza até lá)
  const frameFolder = useCallback((n: SimNode) => {
    const { nodes, edges } = graphRef.current;
    glideTo(frameCamera(nodes, folderSubtreeIds(n.id, edges), logW.current, logH.current));
  }, [glideTo]);

  // ── Hover + pan ─────────────────────────────────────────────────────────
  const handleMouseMove = useCallback((e: React.MouseEvent<HTMLCanvasElement>) => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const found = nodeUnder(e.clientX, e.clientY);
    const cam = camRef.current;
    canvas.style.cursor = found ? 'pointer' : '';

    if (found) {
      if (hovered.current !== found.id) {
        hovered.current = found.id;
        setTooltip({
          label: found.label,
          detail: tooltipDetail(found),
          x: found.x * cam.scale + cam.x,
          y: found.y * cam.scale + cam.y,
        });
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
  }, [nodeUnder, draw]);

  const handleMouseDown = useCallback((e: React.MouseEvent<HTMLCanvasElement>) => {
    dragRef.current = { active: true, startX: e.clientX, startY: e.clientY, camX: camRef.current.x, camY: camRef.current.y };
  }, []);

  // Soltar sem ter arrastado é clique: seleciona o nó (nota abre; pasta enquadra) ou limpa no vazio
  const handleMouseUp = useCallback((e: React.MouseEvent<HTMLCanvasElement>) => {
    const drag = dragRef.current;
    if (!drag.active) return; // soltou o botão vindo de fora do canvas
    drag.active = false;
    if (!isClick({ x: drag.startX, y: drag.startY }, { x: e.clientX, y: e.clientY })) return;

    const hit = nodeUnder(e.clientX, e.clientY);
    if (!hit) {
      selectNode(null);
      return;
    }
    selectNode(hit);
    if (hit.kind === 'note') onOpenNote?.(hit.id);
    else frameFolder(hit);
  }, [nodeUnder, selectNode, frameFolder, onOpenNote]);

  const handleMouseLeave = useCallback(() => {
    dragRef.current.active = false;
    if (hovered.current !== null) { hovered.current = null; setTooltip(null); draw(); }
  }, [draw]);

  // Esc limpa a seleção (o canvas tem foco de teclado)
  const handleKeyDown = useCallback((e: React.KeyboardEvent<HTMLCanvasElement>) => {
    if (e.key === 'Escape' && selectedRef.current !== null) {
      e.preventDefault();
      selectNode(null);
    }
  }, [selectNode]);

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
  // Modo Links sem nenhuma ligação desenhável: aviso sobre o painel (as notas seguem soltas por baixo)
  const linkCount = useMemo(() => visibleLinks(vaultNodes, links).length, [vaultNodes, links]);
  // Legenda: pastas de 1º nível presentes no vault (a mesma cor que o desenho usa)
  const legend = useMemo(() => legendEntries(vaultNodes.map((n) => topFolderOf(n.path))), [vaultNodes]);
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
        tabIndex={0}
        onMouseMove={handleMouseMove}
        onMouseDown={handleMouseDown}
        onMouseUp={handleMouseUp}
        onMouseLeave={handleMouseLeave}
        onKeyDown={handleKeyDown}
        onDoubleClick={handleDoubleClick}
        aria-label="Visualização de grafo — clique num nó para selecionar (nota abre, pasta enquadra), arraste para mover, scroll para zoom, duplo clique para enquadrar, Esc limpa a seleção"
      />
      {mode === 'links' && linkCount === 0 && <GraphNoLinksHint noteCount={vaultNodes.length} />}
      {mode !== 'links' && legend.total > 0 && (
        <GraphLegend entries={legend.shown} overflow={legend.overflow} total={legend.total} />
      )}
      <div className="sr-only" aria-live="polite">{announcement}</div>
      {tooltip && (
        <div
          className="force-graph__tooltip"
          style={{ left: tooltip.x, top: tooltip.y }}
          aria-hidden="true"
        >
          <span className="force-graph__tooltip-label">{tooltip.label}</span>
          <span className="force-graph__tooltip-detail">{tooltip.detail}</span>
        </div>
      )}
    </div>
  );
};

export default ForceGraph;
