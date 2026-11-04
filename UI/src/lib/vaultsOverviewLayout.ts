/**
 * vaultsOverviewLayout.ts
 * Posições do grafo de todas as vaults (sem React, testável). Sem simulação de forças: a posição sai de contas
 * determinísticas, então milhares de notas não custam nada a cada quadro, e a mesma nota fica sempre no mesmo lugar.
 */
import type { VaultOverview, VaultOverviewNote } from '../services/bridge';
import { vaultMeta } from './vaultVisuals';

export const VIEW_W = 780;
export const VIEW_H = 620;
const HUB = { x: VIEW_W / 2, y: VIEW_H / 2 };
const PALETTE = ['#a590f6', '#5cc8e0', '#f2c45a', '#5ccf96', '#f48aa0', '#7aa7ff', '#fb923c', '#e879f9', '#a3e635'];
const GOLDEN = Math.PI * (3 - Math.sqrt(5));

export interface OverviewHit {
  vaultId: string;
  vaultName: string;
  note: VaultOverviewNote;
}

/** Busca no título e na pasta de cada nota, em todas as vaults. */
export const searchOverview = (vaults: VaultOverview[], term: string): OverviewHit[] => {
  const needle = term.trim().toLowerCase();
  if (!needle) return [];
  return vaults.flatMap((vault) => vault.notes
    .filter((note) => note.title.toLowerCase().includes(needle) || note.folder.toLowerCase().includes(needle))
    .map((note) => ({ vaultId: vault.id, vaultName: vault.name, note })));
};

export const buildOverviewLayout = (vaults: VaultOverview[], openId: string | null, hits: OverviewHit[] | null) => {
  const hitIds = hits ? new Set(hits.map((hit) => `${hit.vaultId}:${hit.note.id}`)) : null;
  const shownByHit = hits ? new Set(hits.map((hit) => hit.vaultId)) : null;
  const total = Math.max(vaults.length, 1);
  const radius = total <= 2 ? 200 : 215;
  const startAngle = total === 2 ? -Math.PI * 0.85 : -Math.PI / 2;

  const nodes = vaults.map((vault, index) => {
    const angle = startAngle + (index / total) * Math.PI * 2;
    return {
      vault,
      angle,
      x: HUB.x + Math.cos(angle) * radius,
      y: HUB.y + Math.sin(angle) * radius * 0.8,
      size: Math.round(44 + Math.min(Math.log10(Math.max(vault.note_count, 1)) * 14, 42)),
      dim: hits ? !shownByHit?.has(vault.id) : Boolean(openId && openId !== vault.id),
    };
  });

  const spokes = nodes.map((node) => ({ id: node.vault.id, x1: HUB.x, y1: HUB.y, x2: node.x, y2: node.y, color: vaultMeta(node.vault.color).hex, dim: node.dim }));
  const edges: { id: string; x1: number; y1: number; x2: number; y2: number; color: string; dim: boolean }[] = [];
  const dots: { key: string; x: number; y: number; r: number; color: string; dim: boolean; note: VaultOverviewNote; vaultId: string }[] = [];
  const folders: { key: string; name: string; count: number; x: number; y: number; r: number; color: string; right: boolean; dim: boolean }[] = [];

  for (const node of nodes) {
    const open = hits ? shownByHit?.has(node.vault.id) : node.vault.id === openId;
    if (!open) continue;
    const list = node.vault.folders;
    // As pastas abrem para fora, no leque oposto ao centro.
    const fan = Math.min(Math.PI * 1.15, 0.5 + list.length * 0.32);
    list.forEach((folder, index) => {
      const angle = node.angle - fan / 2 + (list.length > 1 ? (index / (list.length - 1)) * fan : fan / 2);
      const reach = (folder.name ? 118 : 74) + (index % 2) * 26;
      const fx = clampX(node.x + Math.cos(angle) * reach);
      const fy = clampY(node.y + Math.sin(angle) * reach);
      const color = folder.name ? PALETTE[index % PALETTE.length] : vaultMeta(node.vault.color).hex;
      const notes = node.vault.notes.filter((note) => note.folder === folder.name);
      const anyHit = hitIds ? notes.some((note) => hitIds.has(`${node.vault.id}:${note.id}`)) : true;
      if (folder.name) {
        edges.push({ id: `${node.vault.id}:${folder.name}`, x1: node.x, y1: node.y, x2: fx, y2: fy, color, dim: !anyHit });
        folders.push({ key: `${node.vault.id}:${folder.name}`, name: folder.name, count: folder.count, x: fx, y: fy, r: 5 + Math.sqrt(folder.count) * 0.6, color, right: Math.cos(angle) >= 0, dim: !anyHit });
      }
      // Girassol: distribui as notas sem sobrepor, com a densidade igual em qualquer tamanho de pasta.
      notes.forEach((note, order) => {
        const spread = 5 + Math.sqrt(order + 1) * 4.6;
        const x = clampX(fx + Math.cos(order * GOLDEN) * spread);
        const y = clampY(fy + Math.sin(order * GOLDEN) * spread);
        const dim = hitIds ? !hitIds.has(`${node.vault.id}:${note.id}`) : false;
        dots.push({ key: `${node.vault.id}:${note.id}`, x, y, r: folder.name ? 2.2 : 4, color, dim, note, vaultId: node.vault.id });
      });
    });
  }
  return { hub: HUB, vaults: nodes, spokes, edges, dots, folders };
};

const clampX = (x: number) => Math.min(VIEW_W - 6, Math.max(6, x));
const clampY = (y: number) => Math.min(VIEW_H - 6, Math.max(6, y));
