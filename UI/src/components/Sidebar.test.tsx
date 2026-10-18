import { cleanup, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import Sidebar from './Sidebar';

vi.mock('../hooks/useQueueContext', () => ({
  useQueueContext: () => ({
    job: { status: 'running', progress: { processed_count: 29, total_found: 50 } },
    watcherActive: true,
    folderPath: String.raw`C:\Vault\Obsidian-Core`,
  }),
}));

const obsidian = { id: 'obsidian', name: 'Obsidian', icon: 'notes', color: 'violet', folders: [], embedding_model: null, created_at: '', sqlite_path: null, vector_store_dir: null, note_count: 42 };
vi.mock('../hooks/useVaults', () => ({
  useVaults: () => ({
    vaults: [obsidian],
    active: obsidian,
    version: 0,
    refresh: vi.fn(),
    select: vi.fn(),
    create: vi.fn(),
    update: vi.fn(),
    remove: vi.fn(),
  }),
}));

vi.mock('../hooks/useCorpusHealth', () => ({
  useCorpusHealth: () => ({ notes: 668, chunks: 4195, status: 'error', errorCount: 1, warningCount: 0 }),
}));

describe('Sidebar', () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  afterEach(() => {
    cleanup();
  });

  it('começa recolhida e expande pelo botão, lembrando a escolha', async () => {
    const user = userEvent.setup();
    const { container } = render(
      <Sidebar activeView="chat" onNavigate={vi.fn()} onOpenSettings={vi.fn()} healthKey={0} />
    );
    expect(container.querySelector('.sb')?.classList.contains('sb--collapsed')).toBe(true);

    await user.click(screen.getByRole('button', { name: 'Expandir menu' }));

    expect(container.querySelector('.sb')?.classList.contains('sb--collapsed')).toBe(false);
    expect(window.localStorage.getItem('escolio:sidebar-collapsed')).toBe('false');
  });

  it('migra a preferência antiga free-plaud:sidebar-collapsed', () => {
    window.localStorage.setItem('free-plaud:sidebar-collapsed', 'false');
    const { container } = render(
      <Sidebar activeView="chat" onNavigate={vi.fn()} onOpenSettings={vi.fn()} healthKey={0} />
    );
    expect(container.querySelector('.sb')?.classList.contains('sb--collapsed')).toBe(false);
    expect(window.localStorage.getItem('escolio:sidebar-collapsed')).toBe('false');
  });

  it('navega e abre Configurações direto na seção escolhida', async () => {
    const user = userEvent.setup();
    const onNavigate = vi.fn();
    const onOpenSettings = vi.fn();
    render(<Sidebar activeView="chat" onNavigate={onNavigate} onOpenSettings={onOpenSettings} healthKey={0} />);

    await user.click(screen.getByRole('button', { name: /Notas/ }));
    expect(onNavigate).toHaveBeenCalledWith('notes');

    await user.click(screen.getByRole('menuitem', { name: /Voz/ }));
    expect(onOpenSettings).toHaveBeenCalledWith('voz');
  });

  it('mostra progresso da fila, saúde do corpus e vault monitorado', () => {
    render(<Sidebar activeView="queue" onNavigate={vi.fn()} onOpenSettings={vi.fn()} healthKey={0} />);

    expect(screen.getAllByText('58%').length).toBeGreaterThan(0);
    expect(screen.getByRole('button', { name: /Corpus: 1 erro/ })).toBeTruthy();
    expect(screen.getByText('668 notas · 4.195 chunks')).toBeTruthy();
    expect(screen.getByText('Obsidian-Core')).toBeTruthy();
    expect(screen.getByText('monitorando')).toBeTruthy();
  });
});
