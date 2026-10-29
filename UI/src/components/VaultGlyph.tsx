import type { ComponentType } from 'react';
import type { VaultColor, VaultIconId } from '../services/bridge';
import {
  AskIcon,
  BarChartIcon,
  CodeIcon,
  FileIcon,
  FolderIcon,
  GraphIcon,
  LayersIcon,
  MicIcon,
  NoteIcon,
  SparkleIcon,
  StarsIcon,
  VaultIcon,
} from './Icons';

type IconType = ComponentType<{ size?: number }>;

export const VAULT_ICON_COMPONENTS: Record<VaultIconId, IconType> = {
  notes: NoteIcon,
  ask: AskIcon,
  graph: GraphIcon,
  layers: LayersIcon,
  chart: BarChartIcon,
  sparkle: SparkleIcon,
  stars: StarsIcon,
  code: CodeIcon,
  folder: FolderIcon,
  mic: MicIcon,
  vault: VaultIcon,
  file: FileIcon,
};

/** Ícone da vault na cor dela (tokens --vault-* em App.css). */
export function VaultGlyph({ icon, color, size = 16 }: Readonly<{ icon: VaultIconId; color: VaultColor; size?: number }>) {
  const Icon = VAULT_ICON_COMPONENTS[icon];
  return (
    <span className={`vault-glyph vault-glyph--${color}`} aria-hidden="true">
      <Icon size={size} />
    </span>
  );
}
