import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import Dropzone from './Dropzone';

const bridgeMock = vi.hoisted(() => ({
  pollWatcherEvents: vi.fn(),
}));

vi.mock('../services/bridge', () => ({
  bridge: bridgeMock,
}));

const buildFile = (name: string) => new File(['conteudo'], name, { type: 'text/plain' });

const buildDataTransfer = (files: File[]) => ({
  dataTransfer: {
    files: {
      length: files.length,
      item: (index: number) => files[index] ?? null,
      [Symbol.iterator]: function* iterate() {
        yield* files;
      },
    } as unknown as FileList,
  },
});

describe('Dropzone', () => {
  afterEach(() => {
    cleanup();
  });

  beforeEach(() => {
    bridgeMock.pollWatcherEvents.mockReset();
    bridgeMock.pollWatcherEvents.mockResolvedValue([]);
  });

  it('lista apenas arquivos com extensão aceita ao soltar', () => {
    render(<Dropzone />);
    const region = screen.getByRole('region', { name: 'Área de arrastar e soltar arquivos' });

    fireEvent.drop(region, buildDataTransfer([buildFile('audio.wav'), buildFile('planilha.xlsx')]));

    expect(screen.getByText('audio.wav')).toBeTruthy();
    expect(screen.queryByText('planilha.xlsx')).toBeNull();
  });

  it('remove um arquivo da lista ao clicar no botão de remover', () => {
    render(<Dropzone />);
    const region = screen.getByRole('region', { name: 'Área de arrastar e soltar arquivos' });

    fireEvent.drop(region, buildDataTransfer([buildFile('nota.pdf')]));
    expect(screen.getByText('nota.pdf')).toBeTruthy();

    fireEvent.click(screen.getByRole('button', { name: 'Remover nota.pdf' }));
    expect(screen.queryByText('nota.pdf')).toBeNull();
  });

  it('marca dragging ativo durante drag over e desativa ao sair', () => {
    render(<Dropzone />);
    const region = screen.getByRole('region', { name: 'Área de arrastar e soltar arquivos' });

    fireEvent.dragEnter(region);
    expect(region.className).toContain('dropzone--active');

    fireEvent.dragLeave(region);
    expect(region.className).not.toContain('dropzone--active');
  });
});
