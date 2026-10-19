import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import MomentumRail from './MomentumRail';

// jsdom não tem layout: a faixa ganha largura, conteúdo e scrollLeft de verdade (limitado às bordas).
const withLayout = (rail: HTMLElement, { client = 300, content = 900, start = 0 } = {}) => {
  let left = start;
  Object.defineProperty(rail, 'clientWidth', { configurable: true, value: client });
  Object.defineProperty(rail, 'scrollWidth', { configurable: true, value: content });
  Object.defineProperty(rail, 'scrollLeft', {
    configurable: true,
    get: () => left,
    set: (value: number) => {
      left = Math.max(0, Math.min(content - client, value));
    },
  });
  return rail;
};

const wait = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

const renderRail = (onCard = vi.fn(), onButton = vi.fn()) => {
  render(
    <MomentumRail className="trilho" role="radiogroup" aria-label="Modelos">
      <div role="radio" aria-checked={false} aria-label="Cartão" onClick={onCard}>
        cartão
        <button type="button" onClick={onButton}>Baixar</button>
      </div>
    </MomentumRail>
  );
  return withLayout(screen.getByRole('radiogroup', { name: 'Modelos' }), { start: 300 });
};

describe('MomentumRail (arrastar, inércia e roda)', () => {
  afterEach(() => cleanup());

  it('arrastar move a faixa e não seleciona o cartão ao soltar', () => {
    const onCard = vi.fn();
    const rail = renderRail(onCard);
    const card = screen.getByRole('radio', { name: 'Cartão' });

    fireEvent.pointerDown(card, { button: 0, pointerId: 1, clientX: 200 });
    fireEvent.pointerMove(card, { pointerId: 1, clientX: 140 });
    expect(rail.scrollLeft).toBe(360);
    fireEvent.pointerUp(card, { pointerId: 1, clientX: 140 });
    fireEvent.click(card);

    expect(onCard).not.toHaveBeenCalled();
  });

  it('clique simples (sem arrasto) continua selecionando o cartão e acionando o botão', () => {
    const onCard = vi.fn();
    const onButton = vi.fn();
    renderRail(onCard, onButton);
    const card = screen.getByRole('radio', { name: 'Cartão' });

    fireEvent.pointerDown(card, { button: 0, pointerId: 1, clientX: 200 });
    fireEvent.pointerMove(card, { pointerId: 1, clientX: 202 });
    fireEvent.pointerUp(card, { pointerId: 1, clientX: 202 });
    fireEvent.click(card);
    fireEvent.click(screen.getByRole('button', { name: 'Baixar' }));

    expect(onCard).toHaveBeenCalledTimes(2); // o clique no botão também sobe até o cartão
    expect(onButton).toHaveBeenCalledTimes(1);
  });

  it('arrastar a partir de um botão não move a faixa', () => {
    const rail = renderRail();
    const button = screen.getByRole('button', { name: 'Baixar' });

    fireEvent.pointerDown(button, { button: 0, pointerId: 1, clientX: 200 });
    fireEvent.pointerMove(button, { pointerId: 1, clientX: 100 });

    expect(rail.scrollLeft).toBe(300);
  });

  it('soltar depois de arrastar continua rolando por inércia', async () => {
    const rail = renderRail();
    const card = screen.getByRole('radio', { name: 'Cartão' });

    fireEvent.pointerDown(card, { button: 0, pointerId: 1, clientX: 300 });
    await wait(8);
    fireEvent.pointerMove(card, { pointerId: 1, clientX: 260 });
    await wait(8);
    fireEvent.pointerMove(card, { pointerId: 1, clientX: 220 });
    fireEvent.pointerUp(card, { pointerId: 1, clientX: 220 });
    const released = rail.scrollLeft;
    await wait(80);

    expect(rail.scrollLeft).toBeGreaterThan(released);
  });

  it('a roda rola a faixa enquanto há espaço e devolve a rolagem vertical na borda', () => {
    const rail = renderRail();

    const inside = new WheelEvent('wheel', { deltaY: 100, bubbles: true, cancelable: true });
    rail.dispatchEvent(inside);
    expect(inside.defaultPrevented).toBe(true);
    expect(rail.scrollLeft).toBe(400);

    rail.scrollLeft = 600; // fim da faixa
    const atEnd = new WheelEvent('wheel', { deltaY: 100, bubbles: true, cancelable: true });
    rail.dispatchEvent(atEnd);
    expect(atEnd.defaultPrevented).toBe(false);

    rail.scrollLeft = 0; // início: rolar para cima também volta para a página
    const atStart = new WheelEvent('wheel', { deltaY: -100, bubbles: true, cancelable: true });
    rail.dispatchEvent(atStart);
    expect(atStart.defaultPrevented).toBe(false);
  });
});
