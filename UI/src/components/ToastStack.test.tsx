import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import ToastStack from './ToastStack';

describe('ToastStack', () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    cleanup();
    vi.useRealTimers();
  });

  it('nao renderiza nada quando nao ha toasts', () => {
    const { container } = render(<ToastStack toasts={[]} onDismiss={vi.fn()} />);
    expect(container.firstChild).toBeNull();
  });

  it('renderiza toasts e dispensa ao clicar', () => {
    const onDismiss = vi.fn();
    render(
      <ToastStack
        toasts={[{ id: 't1', message: 'nota.md indexado com sucesso.', status: 'success' }]}
        onDismiss={onDismiss}
      />
    );

    expect(screen.getByText('nota.md indexado com sucesso.')).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: 'Fechar notificação' }));
    expect(onDismiss).toHaveBeenCalledWith('t1');
  });

  it('dispensa automaticamente apos o timeout', () => {
    const onDismiss = vi.fn();
    render(
      <ToastStack
        toasts={[{ id: 't2', message: 'Falha ao indexar arquivo.', status: 'failed' }]}
        onDismiss={onDismiss}
      />
    );

    vi.advanceTimersByTime(4000);
    expect(onDismiss).toHaveBeenCalledWith('t2');
  });
});