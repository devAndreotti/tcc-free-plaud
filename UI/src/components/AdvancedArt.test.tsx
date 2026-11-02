import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';
import { SearchArt } from './AdvancedArt';

describe('SearchArt: as três buscas do Avançado', () => {
  afterEach(() => cleanup());

  it.each([
    ['lexical', 'Lexical', /palavras exatas/],
    ['vector', 'Vetorial', /por significado/],
    ['hybrid', 'Híbrida', /junta a busca/],
  ])('%s fica em destaque e explicada, com as outras duas ainda à vista', (strategy, label, text) => {
    const { container } = render(<SearchArt strategy={strategy} />);

    expect(container.querySelectorAll('.adv-search__kind')).toHaveLength(3);
    expect(container.querySelector('.adv-search__kind.is-on')?.textContent).toBe(label);
    expect(screen.getByText(text)).toBeTruthy();
  });

  it('valor desconhecido cai na híbrida, o padrão do app', () => {
    const { container } = render(<SearchArt strategy="outra" />);
    expect(container.querySelector('.adv-search__kind.is-on')?.textContent).toBe('Híbrida');
  });
});
