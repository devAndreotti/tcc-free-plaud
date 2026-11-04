import { useRef, type KeyboardEvent } from 'react';
import type { MessageData } from '../components/MessageBubble';

/** Prompts já enviados, do mais recente para o mais antigo: primeiro a aba ativa, depois as outras. */
export const buildPromptHistory = (
  tabIds: string[],
  activeTabId: string | null | undefined,
  tabMessages: Record<string, MessageData[]>,
): string[] => {
  const order = [
    ...(activeTabId ? [activeTabId] : []),
    ...tabIds.filter((id) => id !== activeTabId).reverse(),
  ];
  const seen = new Set<string>();
  const history: string[] = [];
  for (const id of order) {
    const messages = tabMessages[id] ?? [];
    for (let i = messages.length - 1; i >= 0; i -= 1) {
      const text = messages[i].role === 'user' ? messages[i].content.trim() : '';
      if (text && !seen.has(text)) {
        seen.add(text);
        history.push(text);
      }
    }
  }
  return history;
};

// O cursor está na primeira linha que aparece na tela? Numa linha longa quebrada, só no começo dela,
// para a seta continuar subindo o cursor como sempre.
const caretOnFirstLine = (field: HTMLTextAreaElement): boolean => {
  const start = field.selectionStart ?? 0;
  if (start === 0) return true;
  if (field.value.slice(0, start).includes('\n')) return false;
  const style = window.getComputedStyle(field);
  const lineHeight = Number.parseFloat(style.lineHeight);
  if (!lineHeight) return true;
  const padding = Number.parseFloat(style.paddingTop) + Number.parseFloat(style.paddingBottom);
  const shownLines = Math.round((field.scrollHeight - (padding || 0)) / lineHeight);
  return shownLines <= field.value.split('\n').length;
};

interface Browsing {
  index: number;
  draft: string;
  text: string;
}

/** Devolve o tratador das setas: ↑ puxa o prompt anterior, ↓ volta até o que você estava escrevendo. */
export const usePromptHistory = (history: string[], onChange: (text: string) => void) => {
  const browsing = useRef<Browsing | null>(null);

  const show = (field: HTMLTextAreaElement, next: Browsing | null, text: string) => {
    browsing.current = next;
    onChange(text);
    requestAnimationFrame(() => field.setSelectionRange(text.length, text.length));
  };

  return (event: KeyboardEvent<HTMLTextAreaElement>): boolean => {
    if (event.key !== 'ArrowUp' && event.key !== 'ArrowDown') return false;
    if (event.shiftKey || event.altKey || event.ctrlKey || event.metaKey || event.nativeEvent.isComposing) return false;
    const field = event.currentTarget;
    // Editou o texto ou trocou de aba: a navegação acabou, e o campo volta a ser um rascunho.
    if (browsing.current && browsing.current.text !== field.value) browsing.current = null;
    const current = browsing.current;

    if (event.key === 'ArrowUp') {
      if (!current && (field.selectionStart !== field.selectionEnd || !caretOnFirstLine(field))) return false;
      const index = current ? current.index + 1 : 0;
      if (index >= history.length) {
        if (current) event.preventDefault(); // já no mais antigo: fica nele
        return Boolean(current);
      }
      event.preventDefault();
      show(field, { index, draft: current?.draft ?? field.value, text: history[index] }, history[index]);
      return true;
    }

    if (!current) return false;
    event.preventDefault();
    if (current.index === 0) show(field, null, current.draft);
    else {
      const text = history[current.index - 1] ?? current.draft;
      show(field, { ...current, index: current.index - 1, text }, text);
    }
    return true;
  };
};
