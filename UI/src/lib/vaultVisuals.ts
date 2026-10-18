import type { Vault, VaultColor, VaultIconId } from '../services/bridge';

/** Ordem e rótulos dos ícones e cores de vault (ids espelham escolio/app/vaults.py). */
export const VAULT_ICON_OPTIONS: { id: VaultIconId; label: string }[] = [
  { id: 'notes', label: 'Notas' },
  { id: 'ask', label: 'Pergunta' },
  { id: 'graph', label: 'Grafo' },
  { id: 'layers', label: 'Camadas' },
  { id: 'chart', label: 'Gráfico' },
  { id: 'sparkle', label: 'Brilho' },
  { id: 'stars', label: 'Estrelas' },
  { id: 'code', label: 'Código' },
  { id: 'folder', label: 'Pasta' },
  { id: 'mic', label: 'Voz' },
  { id: 'vault', label: 'Cofre' },
  { id: 'file', label: 'Arquivo' },
];

export const VAULT_COLOR_OPTIONS: { id: VaultColor; label: string }[] = [
  { id: 'violet', label: 'Violeta' },
  { id: 'blue', label: 'Azul' },
  { id: 'green', label: 'Verde' },
  { id: 'amber', label: 'Âmbar' },
  { id: 'rose', label: 'Rosa' },
  { id: 'teal', label: 'Turquesa' },
  { id: 'slate', label: 'Ardósia' },
];

const plural = (n: number, one: string, many: string) => `${n.toLocaleString('pt-BR')} ${n === 1 ? one : many}`;

/** "12 notas · 2 pastas": resumo da vault no seletor, na aba Vaults e na tela inicial. */
export const vaultMeta = (vault: Vault): string =>
  `${plural(vault.note_count ?? 0, 'nota', 'notas')} · ${plural(vault.roots?.length ?? vault.folders.length, 'pasta', 'pastas')}`;
