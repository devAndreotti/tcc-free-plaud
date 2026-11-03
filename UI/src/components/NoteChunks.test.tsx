import { cleanup, render } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { NoteChunks } from './NoteChunks';
import type { NoteChunkSummary } from '../services/bridge';

describe('NoteChunks: trechos sem Markdown cru', () => {
  afterEach(() => cleanup());

  it('mostra o texto limpo e não altera o dado nem os offsets', () => {
    // jsdom não implementa scrollIntoView
    Element.prototype.scrollIntoView = vi.fn();
    const chunk: NoteChunkSummary = {
      chunk_id: 'c1',
      chunk_index: 0,
      char_start: 10,
      char_end: 90,
      token_count: 12,
      snippet: '## Título\n\n**forte** e [guia](https://x.dev)\n|---|---|\n| a | b |',
    };
    const original = { ...chunk };
    const { container } = render(<NoteChunks chunks={[chunk]} highlightChunkId={null} />);

    const texto = container.querySelector('.reader__chunk p')?.textContent ?? '';
    expect(texto).toBe('Título\n\nforte e guia\na · b');
    expect(texto).not.toMatch(/##|\*\*|\|---/);
    expect(chunk).toEqual(original);
    expect(container.querySelector('.reader__chunk-head')?.textContent).toContain('10–90');
  });
});
