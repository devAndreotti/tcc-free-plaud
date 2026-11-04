import { beforeAll, describe, expect, it } from 'vitest';
import { iconBody, loadNoteIcons, splitEmoji, stripEmoji, titleParts } from './noteIcons';

beforeAll(() => loadNoteIcons());

const keys = (text: string) => splitEmoji(text).flatMap((part) => (typeof part === 'string' ? [] : [part.key]));

describe('noteIcons', () => {
  it('acha emoji simples, com seletor de variação, tom de pele, junção, bandeira e tecla', () => {
    expect(keys('❤️ Saúde')).toEqual(['2764']);
    expect(keys('❤ Saúde')).toEqual(['2764']);
    expect(keys('🔒📁 Área de TI')).toEqual(['1f512', '1f4c1']);
    expect(keys('👍🏽 Ok')).toEqual(['1f44d-1f3fd']);
    expect(keys('🧑‍🎨 Arte')).toEqual(['1f9d1-200d-1f3a8']);
    expect(keys('🇬🇧 Inglês')).toEqual(['1f1ec-1f1e7']);
    expect(keys('1️⃣ Primeiro')).toEqual(['0031-20e3']);
  });

  it('não confunde texto com emoji: números, © ® ™ e setas de texto ficam', () => {
    for (const text of ['Aula 1 de 3', 'Marca© e Nome® e Coisa™', 'Notion → Obsidian', 'C# e C++']) {
      expect(splitEmoji(text)).toEqual([text]);
      expect(stripEmoji(text)).toBe(text);
    }
  });

  it('sem ícone: tira só o emoji, sem deixar espaço sobrando', () => {
    expect(stripEmoji('🔒📁 Área de TI')).toBe('Área de TI');
    expect(stripEmoji('Plano ❤️ de vida')).toBe('Plano de vida');
    expect(stripEmoji('❤️')).toBe('Sem título');
  });

  it('cada modo devolve o que exibir, e título sem emoji fica igual', () => {
    expect(titleParts('❤️ Saúde', 'original')).toEqual(['❤️ Saúde']);
    expect(titleParts('❤️ Saúde', 'none')).toEqual(['Saúde']);
    expect(titleParts('❤️ Saúde', 'svg')).toEqual([{ emoji: '❤️', key: '2764' }, ' Saúde']);
    expect(titleParts('Roadmap', 'svg')).toEqual(['Roadmap']);
    expect(titleParts('Roadmap', 'none')).toEqual(['Roadmap']);
  });

  it('todo emoji dos títulos reais tem SVG, com queda para o desenho base', () => {
    expect(iconBody('2764')).toContain('<path');

    const titulos = ['⚡', '🔄', '📖', '👔', '🎮', '🇬🇧', '👤', '🎯', '💪', '📦', '♟️', '🔒', '📁', '🏙️', '🎪', '🧠', '📸', '🏁', '🧱', '🥽', '🏢', '📚', '🌱', '💻', '🔁'];
    const semIcone = titulos.flatMap((emoji) => keys(emoji)).filter((key) => !iconBody(key));
    expect(semIcone).toEqual([]);

    expect(iconBody('1f44d-1f3fd')).toBe(iconBody('1f44d'));
    expect(iconBody('1f1ec-1f1e7')).toBe(iconBody('1f3f3'));
    expect(iconBody('ffffff')).toBeNull();
  });
});
