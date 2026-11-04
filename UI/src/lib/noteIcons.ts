/**
 * noteIcons.ts — emojis nos títulos das notas e no grafo: SVG do app, emoji original ou nada.
 *
 * O título guardado não muda; só a exibição. Os SVGs (Fluent Emoji High Contrast, MIT) ficam em
 * assets/emoji-svg.json, por código Unicode.
 */

import { useSyncExternalStore } from 'react';
import { DEFAULT_APPEARANCE, type Appearance } from '../appearance';

export type NoteIconsMode = Appearance['noteIcons'];

/** Um emoji do título: o texto original e a chave do ícone no mapa. */
export interface EmojiPart {
  emoji: string;
  key: string;
}
export type TitlePart = string | EmojiPart;

// Bandeira, tecla (1️⃣) ou pictograma com tom de pele e junções (ZWJ). ©, ® e ™ são pictogramas para o Unicode, mas aqui são texto.
const EMOJI =
  /\p{Regional_Indicator}{2}|[0-9#*]️?⃣|(?![©®™])\p{Extended_Pictographic}[️\p{Emoji_Modifier}]*(?:‍\p{Extended_Pictographic}[️\p{Emoji_Modifier}]*)*/gu;

const emojiKey = (emoji: string) =>
  Array.from(emoji)
    .map((char) => char.codePointAt(0)!.toString(16).padStart(4, '0'))
    .filter((code) => code !== 'fe0f')
    .join('-');

/** Parte o título em texto e emojis, na ordem em que aparecem. */
export function splitEmoji(text: string): TitlePart[] {
  const parts: TitlePart[] = [];
  let last = 0;
  for (const match of text.matchAll(EMOJI)) {
    if (match.index > last) parts.push(text.slice(last, match.index));
    parts.push({ emoji: match[0], key: emojiKey(match[0]) });
    last = match.index + match[0].length;
  }
  if (last < text.length) parts.push(text.slice(last));
  return parts;
}

/** Título sem os emojis; título só de emoji vira "Sem título", para o item não ficar vazio. */
export function stripEmoji(text: string): string {
  return text.replace(EMOJI, '').replace(/\s{2,}/g, ' ').trim() || 'Sem título';
}

const partsCache = new Map<string, TitlePart[]>();

/** Partes a exibir no modo pedido. Com cache, porque o grafo pergunta isso para cada rótulo, a cada frame. */
export function titleParts(text: string, mode: NoteIconsMode): TitlePart[] {
  if (mode === 'original') return [text];
  const key = `${mode}|${text}`;
  let parts = partsCache.get(key);
  if (!parts) {
    const split = splitEmoji(text);
    parts = split.every((part) => typeof part === 'string') ? [text] : mode === 'none' ? [stripEmoji(text)] : split;
    partsCache.set(key, parts);
  }
  return parts;
}

let icons: Record<string, string> | null = null;
let loading: Promise<void> | null = null;
let iconsVersion = 0;
const listeners = new Set<() => void>();
let observer: MutationObserver | null = null;

export const notifyNoteIcons = () => listeners.forEach((listener) => listener());

/**
 * Os 1.595 SVGs (2,6 MB) vêm num arquivo à parte, carregado na primeira vez que alguém pede um ícone:
 * no bundle principal eram 83% do JS da abertura. ?raw: texto, para o TypeScript não inferir 1.595 chaves.
 */
export function loadNoteIcons(): Promise<void> {
  loading ??= import('../assets/emoji-svg.json?raw').then(({ default: raw }) => {
    icons = JSON.parse(raw) as Record<string, string>;
    iconsVersion += 1;
    notifyNoteIcons();
  });
  return loading;
}

/**
 * SVG do emoji (conteúdo do <svg>, viewBox 0 0 32 32) ou null se não houver.
 * O conjunto não tem tons de pele nem bandeiras de país: tom vira o desenho base, bandeira vira a bandeira branca.
 */
export function iconBody(key: string): string | null {
  if (!icons) {
    void loadNoteIcons(); // até chegar, o emoji fica de fora; quem assina redesenha quando o mapa chega
    return null;
  }
  const codes = key.split('-');
  const base = codes.filter((code) => !/^1f3f[b-f]$/.test(code)).join('-');
  const isFlag = /^1f1[e-f]/.test(codes[0]);
  return icons[key] ?? icons[base] ?? icons[codes[0]] ?? (isFlag ? icons['1f3f3'] : null) ?? null;
}

export const readNoteIconsMode = (): NoteIconsMode =>
  (document.documentElement.dataset.noteIcons ?? DEFAULT_APPEARANCE.noteIcons) as NoteIconsMode;

/** Avisa quando a opção muda em Aparência ou quando uma imagem de ícone do grafo termina de carregar. */
export function subscribeNoteIcons(listener: () => void): () => void {
  if (!observer) {
    observer = new MutationObserver(notifyNoteIcons);
    observer.observe(document.documentElement, { attributes: true, attributeFilter: ['data-note-icons'] });
  }
  listeners.add(listener);
  return () => listeners.delete(listener);
}

const readIconsVersion = () => iconsVersion;

export const useNoteIconsMode = (): NoteIconsMode => {
  useSyncExternalStore(subscribeNoteIcons, readIconsVersion); // renderiza de novo quando os ícones chegam
  return useSyncExternalStore(subscribeNoteIcons, readNoteIconsMode);
};
