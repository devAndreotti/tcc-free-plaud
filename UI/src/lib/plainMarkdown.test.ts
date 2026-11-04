import { describe, expect, it } from 'vitest';
import { plainMarkdown } from './plainMarkdown';

describe('plainMarkdown', () => {
  it('tira o # dos títulos e o # de fechamento', () => {
    expect(plainMarkdown('## Arquitetura')).toBe('Arquitetura');
    expect(plainMarkdown('### Título ###')).toBe('Título');
    expect(plainMarkdown('#hashtag')).toBe('#hashtag');
  });

  it('tira a ênfase', () => {
    expect(plainMarkdown('um **forte** e __outro__ e *leve*')).toBe('um forte e outro e leve');
    expect(plainMarkdown('**a *b* c**')).toBe('a b c');
  });

  it('mostra só o texto dos links e das imagens', () => {
    expect(plainMarkdown('veja [o guia](https://exemplo.com/a?b=1) agora')).toBe('veja o guia agora');
    expect(plainMarkdown('![diagrama](img/a.png)')).toBe('diagrama');
    expect(plainMarkdown('[sem destino] e (parênteses)')).toBe('[sem destino] e (parênteses)');
  });

  it('remove o separador da tabela e deixa as células legíveis', () => {
    const tabela = '| Modelo | Nota |\n|---|:---:|\n| RRF | 0,9 |';
    expect(plainMarkdown(tabela)).toBe('Modelo · Nota\nRRF · 0,9');
  });

  it('preserva listas', () => {
    expect(plainMarkdown('- um\n* dois\n1. três')).toBe('- um\n* dois\n1. três');
  });

  it('tira as cercas de código e mantém o conteúdo intacto', () => {
    const texto = 'antes\n```python\nx = **y** * 2\n## nada\n```\ndepois';
    expect(plainMarkdown(texto)).toBe('antes\nx = **y** * 2\n## nada\ndepois');
  });

  it('tira as crases de código em linha', () => {
    expect(plainMarkdown('use `uv run` aqui')).toBe('use uv run aqui');
  });

  it('deixa o texto normal idêntico', () => {
    const normal = 'O RRF combina BM25 e vetores, com k=60; a_b e snake_case ficam. (ok) 3 > 2.';
    expect(plainMarkdown(normal)).toBe(normal);
  });

  it('não faz sumir asterisco solto', () => {
    expect(plainMarkdown('2 * 3 * 4')).toBe('2 * 3 * 4');
    expect(plainMarkdown('a*b')).toBe('a*b');
    expect(plainMarkdown('**')).toBe('**');
  });

  it('é linear em linhas longas e repetitivas', () => {
    const casos = ['*a '.repeat(33_334), '**a '.repeat(25_000), '['.repeat(100_000), '[a]('.repeat(25_000), '`'.repeat(100_000), '_'.repeat(100_000), '|'.repeat(100_000), ' '.repeat(100_000) + '|--', 'a*'.repeat(50_000), '#'.repeat(100_000)];
    for (const caso of casos) {
      const inicio = performance.now();
      plainMarkdown(caso);
      const ms = performance.now() - inicio;
      console.info(`plainMarkdown ${JSON.stringify(caso.slice(0, 8))}… (${caso.length} chars): ${ms.toFixed(1)} ms`);
      // Folga para a instrumentação de cobertura (~3 s); um custo quadrático em 100 mil caracteres passaria longe disso.
      expect(ms).toBeLessThan(5000);
    }
  });
});
