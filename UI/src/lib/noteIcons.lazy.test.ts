import { describe, expect, it, vi } from 'vitest';
import { iconBody, loadNoteIcons, subscribeNoteIcons } from './noteIcons';

// Arquivo próprio: o mapa de ícones é estado do módulo, e aqui ele começa sem carregar.
describe('ícones sob demanda', () => {
  it('antes do mapa chegar o emoji fica de fora; quando chega, quem assina é avisado', async () => {
    const listener = vi.fn();
    const unsubscribe = subscribeNoteIcons(listener);
    expect(iconBody('2764')).toBeNull();
    await loadNoteIcons();
    expect(listener).toHaveBeenCalled();
    expect(iconBody('2764')).toContain('<path');
    unsubscribe();
  });
});
